"""Cloud runner streaming writer.

Writes simulation results incrementally to avoid holding all data in memory.
One-way dependency: writer -> utils (never the reverse).
"""

from __future__ import annotations

import json
import math
import multiprocessing
import os
import subprocess
from collections import Counter
from typing import Any, Dict, List, Optional

from simulator._cloud_runner_utils import (
    _build_cost_telemetry,
    _normalize_parquet_compression,
    _wilson_interval,
)
from snapshot_schema import JSONISH_COLUMNS


class StreamingWriter:
    """Writes simulation results incrementally to avoid holding all data in memory.

    Training data is flushed to chunk files every `chunk_size` games.
    Analytics counters are accumulated in memory (small footprint).
    Checkpoints are written periodically for resume capability.
    """

    def __init__(
        self,
        output_dir: str,
        chunk_size: int = 100,
        resume_state: Optional[Dict] = None,
        require_parquet: bool = False,
        parquet_compression: str = "uncompressed",
        parquet_use_dictionary: bool = False,
        parquet_write_statistics: bool = False,
        s3_uri: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.chunk_size = chunk_size
        self.require_parquet = require_parquet
        self.parquet_compression = _normalize_parquet_compression(parquet_compression)
        self.parquet_use_dictionary = parquet_use_dictionary
        self.parquet_write_statistics = parquet_write_statistics
        self.s3_uri = s3_uri.rstrip("/") if s3_uri else None
        os.makedirs(output_dir, exist_ok=True)

        # Training row buffer (flushed every chunk_size games)
        self._row_buffer: List[Dict] = []
        self._jsonl_blob_buffer: List[str] = []
        self._parquet_blob_buffer: List[bytes] = []
        self._pending_row_count = 0
        self._games_in_buffer = 0

        # Running analytics (accumulated across all games)
        self._champ_placements: Counter = Counter()
        self._champ_placements_sq: Counter = Counter()
        self._champ_counts: Counter = Counter()
        self._champ_top4_counts: Counter = Counter()
        self._champ_win_counts: Counter = Counter()
        self._aug_placements: Counter = Counter()
        self._aug_placements_sq: Counter = Counter()
        self._aug_counts: Counter = Counter()
        self._aug_top4_counts: Counter = Counter()
        self._aug_win_counts: Counter = Counter()

        # Tracking
        self._completed_seeds: List[int] = []
        self._errors: List[Dict] = []
        self._sum_game_time = 0.0
        self._total_rounds = 0
        self._total_rows = 0
        self._chunk_idx = 0

        # Restore state if resuming
        if resume_state:
            self._completed_seeds = list(resume_state.get("completed_seeds", []))
            self._chunk_idx = resume_state.get("chunks_written", 0)
            self._total_rows = resume_state.get("total_rows", 0)
            self._sum_game_time = resume_state.get("sum_game_time", 0.0)
            self._total_rounds = resume_state.get("total_rounds", 0)
            self._champ_placements = Counter(resume_state.get("champ_placements", {}))
            self._champ_placements_sq = Counter(resume_state.get("champ_placements_sq", {}))
            self._champ_counts = Counter(resume_state.get("champ_counts", {}))
            self._champ_top4_counts = Counter(resume_state.get("champ_top4_counts", {}))
            self._champ_win_counts = Counter(resume_state.get("champ_win_counts", {}))
            self._aug_placements = Counter(resume_state.get("aug_placements", {}))
            self._aug_placements_sq = Counter(resume_state.get("aug_placements_sq", {}))
            self._aug_counts = Counter(resume_state.get("aug_counts", {}))
            self._aug_top4_counts = Counter(resume_state.get("aug_top4_counts", {}))
            self._aug_win_counts = Counter(resume_state.get("aug_win_counts", {}))

    @property
    def num_completed(self) -> int:
        return len(self._completed_seeds)

    @property
    def num_errors(self) -> int:
        return len(self._errors)

    @property
    def games_in_buffer(self) -> int:
        return self._games_in_buffer

    @property
    def next_chunk_name(self) -> str:
        return f"chunk_{self._chunk_idx:04d}"

    def _s3_upload(self, local_path: str) -> None:
        """Upload a local file to S3 if s3_uri is configured."""
        if not self.s3_uri:
            return
        filename = os.path.basename(local_path)
        s3_dest = f"{self.s3_uri}/{filename}"
        try:
            result = subprocess.run(
                ["aws", "s3", "cp", local_path, s3_dest, "--only-show-errors"],
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
            if result.returncode != 0:
                print(f"  [WARN] S3 upload failed for {filename}: {result.stderr.strip()}")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            print(f"  [WARN] S3 upload failed for {filename}: {exc}")

    def add_result(self, result: Dict, *, buffer_training_rows: bool = True):
        """Process a completed game result."""
        if result["status"] == "error":
            self._errors.append(
                {
                    "game_id": result["game_id"],
                    "seed": result["seed"],
                    "error": result["error"],
                }
            )
            return

        self._completed_seeds.append(result["seed"])
        self._sum_game_time += result["elapsed"]
        self._total_rounds += result["rounds"]

        if buffer_training_rows:
            # Buffer training rows
            training_rows = result.get("training_rows", [])
            if training_rows:
                self._row_buffer.extend(training_rows)
                self._pending_row_count += len(training_rows)
            training_rows_jsonl = result.get("training_rows_jsonl", "")
            if training_rows_jsonl:
                self._jsonl_blob_buffer.append(training_rows_jsonl)
                self._pending_row_count += int(result.get("training_row_count", 0))
            training_rows_parquet = result.get("training_rows_parquet", b"")
            if training_rows_parquet:
                self._parquet_blob_buffer.append(training_rows_parquet)
                self._pending_row_count += int(result.get("training_row_count", 0))

        # Accumulate analytics
        analytics = result["analytics"]
        for name, placement in analytics["champion_placements"]:
            self._champ_placements[name] += placement
            self._champ_placements_sq[name] += placement * placement
            self._champ_counts[name] += 1
            if placement <= 4:
                self._champ_top4_counts[name] += 1
            if placement == 1:
                self._champ_win_counts[name] += 1
        for name, placement in analytics["augment_placements"]:
            self._aug_placements[name] += placement
            self._aug_placements_sq[name] += placement * placement
            self._aug_counts[name] += 1
            if placement <= 4:
                self._aug_top4_counts[name] += 1
            if placement == 1:
                self._aug_win_counts[name] += 1

        if buffer_training_rows:
            self._games_in_buffer += 1

            # Flush if buffer is full
            if self._games_in_buffer >= self.chunk_size:
                self._flush_chunk()

    def record_external_parquet_chunk(self, row_count: int):
        """Record a chunk file that was already written outside this writer."""
        # Upload the chunk that was just written by Rust
        chunk_name = f"chunk_{self._chunk_idx:04d}"
        chunk_path = os.path.join(self.output_dir, chunk_name + ".parquet")
        if os.path.exists(chunk_path):
            self._s3_upload(chunk_path)

        self._total_rows += max(0, row_count)
        self._chunk_idx += 1
        self._games_in_buffer = 0

    def _flush_chunk(self):
        """Write buffered training rows to a chunk file."""
        if not self._row_buffer and not self._jsonl_blob_buffer and not self._parquet_blob_buffer:
            return

        chunk_name = f"chunk_{self._chunk_idx:04d}"
        if self._parquet_blob_buffer:
            self._write_parquet_blob_chunk(chunk_name)
        elif self._jsonl_blob_buffer:
            if self.require_parquet:
                self._write_parquet_from_jsonl_blob_chunk(chunk_name)
            else:
                try:
                    self._write_parquet_from_jsonl_blob_chunk(chunk_name)
                except (ImportError, OSError, ValueError, RuntimeError):
                    self._write_jsonl_blob_chunk(chunk_name)
        else:
            if self.require_parquet:
                self._write_parquet_chunk(chunk_name)
            else:
                try:
                    self._write_parquet_chunk(chunk_name)
                except (ImportError, OSError, ValueError, RuntimeError):
                    self._write_jsonl_chunk(chunk_name)

        self._total_rows += self._pending_row_count

        # Stream chunk to S3 immediately
        for ext in (".parquet", ".jsonl"):
            chunk_path = os.path.join(self.output_dir, chunk_name + ext)
            if os.path.exists(chunk_path):
                self._s3_upload(chunk_path)
                break

        self._row_buffer = []
        self._jsonl_blob_buffer = []
        self._parquet_blob_buffer = []
        self._pending_row_count = 0
        self._chunk_idx += 1
        self._games_in_buffer = 0

    def _write_parquet_chunk(self, chunk_name: str):
        """Write chunk as Parquet (requires pyarrow)."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        rows = self._row_buffer
        for row in rows:
            for key in JSONISH_COLUMNS:
                if key in row and isinstance(row[key], (list, dict)):
                    row[key] = json.dumps(row[key])

        table = pa.Table.from_pylist(rows)
        path = os.path.join(self.output_dir, chunk_name + ".parquet")
        pq.write_table(
            table,
            path,
            compression=self.parquet_compression,
            use_dictionary=self.parquet_use_dictionary,
            write_statistics=self.parquet_write_statistics,
        )

    def _write_jsonl_chunk(self, chunk_name: str):
        """Write chunk as JSON Lines (fallback)."""
        path = os.path.join(self.output_dir, chunk_name + ".jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for row in self._row_buffer:
                f.write(json.dumps(row) + "\n")

    def _write_jsonl_blob_chunk(self, chunk_name: str):
        """Write pre-serialized JSONL payloads from Rust."""
        path = os.path.join(self.output_dir, chunk_name + ".jsonl")
        with open(path, "w", encoding="utf-8") as f:
            for blob in self._jsonl_blob_buffer:
                if not blob:
                    continue
                f.write(blob)
                if not blob.endswith("\n"):
                    f.write("\n")

    def _write_parquet_blob_chunk(self, chunk_name: str):
        """Aggregate Rust-prebuilt parquet blobs into one chunk parquet file."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except (ImportError, OSError):
            # Fallback: preserve behavior if pyarrow is unavailable.
            for idx, blob in enumerate(self._parquet_blob_buffer):
                if not blob:
                    continue
                path = os.path.join(self.output_dir, f"{chunk_name}_{idx:04d}.parquet")
                with open(path, "wb") as f:
                    f.write(blob)
            return

        path = os.path.join(self.output_dir, chunk_name + ".parquet")
        writer = None
        schema = None
        try:
            for blob in self._parquet_blob_buffer:
                if not blob:
                    continue
                table = pq.read_table(pa.BufferReader(blob))
                if schema is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(
                        path,
                        schema,
                        compression=self.parquet_compression,
                        use_dictionary=self.parquet_use_dictionary,
                        write_statistics=self.parquet_write_statistics,
                    )
                elif not table.schema.equals(schema, check_metadata=False):
                    table = table.cast(schema)
                writer.write_table(table)
        except (OSError, ValueError, RuntimeError):
            if writer is not None:
                writer.close()
                writer = None
            if os.path.exists(path):
                os.remove(path)
            if self.require_parquet:
                raise
            for idx, blob in enumerate(self._parquet_blob_buffer):
                if not blob:
                    continue
                fallback_path = os.path.join(self.output_dir, f"{chunk_name}_{idx:04d}.parquet")
                with open(fallback_path, "wb") as f:
                    f.write(blob)
            return
        finally:
            if writer is not None:
                writer.close()

    def _write_parquet_from_jsonl_blob_chunk(self, chunk_name: str):
        """Convert pre-serialized JSONL blobs to Parquet with Arrow JSON parser."""
        import pyarrow as pa
        import pyarrow.json as paj
        import pyarrow.parquet as pq

        payload = "".join(blob for blob in self._jsonl_blob_buffer if blob)
        if payload and not payload.endswith("\n"):
            payload += "\n"
        if not payload:
            return

        table = paj.read_json(pa.BufferReader(payload.encode("utf-8")))
        path = os.path.join(self.output_dir, chunk_name + ".parquet")
        pq.write_table(
            table,
            path,
            compression=self.parquet_compression,
            use_dictionary=self.parquet_use_dictionary,
            write_statistics=self.parquet_write_statistics,
        )

    def write_checkpoint(self):
        """Write checkpoint for resume capability."""
        checkpoint = {
            "completed_seeds": sorted(self._completed_seeds),
            "num_completed": len(self._completed_seeds),
            "num_errors": len(self._errors),
            "chunks_written": self._chunk_idx,
            "total_rows": self._total_rows,
            "sum_game_time": self._sum_game_time,
            "total_rounds": self._total_rounds,
            "champ_placements": dict(self._champ_placements),
            "champ_placements_sq": dict(self._champ_placements_sq),
            "champ_counts": dict(self._champ_counts),
            "champ_top4_counts": dict(self._champ_top4_counts),
            "champ_win_counts": dict(self._champ_win_counts),
            "aug_placements": dict(self._aug_placements),
            "aug_placements_sq": dict(self._aug_placements_sq),
            "aug_counts": dict(self._aug_counts),
            "aug_top4_counts": dict(self._aug_top4_counts),
            "aug_win_counts": dict(self._aug_win_counts),
        }
        path = os.path.join(self.output_dir, "checkpoint.json")
        # Write atomically (write to temp, then rename)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f)
        os.replace(tmp_path, path)

    def finalize(
        self, total_time: float, num_workers: int, run_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Flush remaining data, write errors, summary, and final checkpoint."""
        self._flush_chunk()

        # Write errors
        if self._errors:
            error_path = os.path.join(self.output_dir, "errors.json")
            with open(error_path, "w", encoding="utf-8") as f:
                json.dump(self._errors, f, indent=2)
            print(f"  Errors: {error_path} ({len(self._errors)} failures)")
            self._s3_upload(error_path)

        # Compute and write summary
        summary = self._compute_summary(total_time, num_workers, run_metadata or {})
        summary_path = os.path.join(self.output_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"  Summary: {summary_path}")
        self._s3_upload(summary_path)

        # Final checkpoint
        self.write_checkpoint()
        checkpoint_path = os.path.join(self.output_dir, "checkpoint.json")
        self._s3_upload(checkpoint_path)

        if self.s3_uri:
            print(f"  S3: All files uploaded to {self.s3_uri}/")

        return summary

    def _compute_summary(
        self, total_time: float, num_workers: int, run_metadata: Dict[str, Any]
    ) -> Dict:
        """Compute aggregate statistics."""
        num_games = len(self._completed_seeds)
        logical_cpu_count = int(
            run_metadata.get("logical_cpu_count") or multiprocessing.cpu_count()
        )
        instance_hourly_usd = float(run_metadata.get("instance_hourly_usd") or 0.0)
        cpu_util_samples = run_metadata.get("cpu_utilization_samples_pct") or []
        cost_telemetry = _build_cost_telemetry(
            total_time_sec=total_time,
            num_games=num_games,
            total_rounds=self._total_rounds,
            num_workers=num_workers,
            logical_cpu_count=logical_cpu_count,
            instance_hourly_usd=instance_hourly_usd,
            cpu_utilization_samples_pct=cpu_util_samples,
        )
        if num_games == 0:
            return {
                "num_games": 0,
                "num_errors": len(self._errors),
                "num_workers": num_workers,
                "total_time_sec": round(total_time, 1),
                "total_rounds": 0,
                "cost_telemetry": cost_telemetry,
                "run_config": run_metadata,
            }

        # Champion average placements
        champ_avg = {}
        for name in self._champ_counts:
            champ_avg[name] = round(self._champ_placements[name] / self._champ_counts[name], 2)
        aug_avg = {}
        for name in self._aug_counts:
            aug_avg[name] = round(self._aug_placements[name] / self._aug_counts[name], 2)

        top_champs = sorted(champ_avg.items(), key=lambda x: x[1])[:20]
        bot_champs = sorted(champ_avg.items(), key=lambda x: x[1], reverse=True)[:20]
        top_augs = sorted(aug_avg.items(), key=lambda x: x[1])[:20]

        def _build_rate_rows(
            names: List[str],
            counts: Counter,
            placements: Counter,
            placements_sq: Counter,
            top4_counts: Counter,
            win_counts: Counter,
        ) -> List[Dict[str, Any]]:
            rows = []
            for name in names:
                n = int(counts[name])
                if n <= 0:
                    continue
                avg = placements[name] / n
                mean_sq = placements_sq[name] / n
                variance = max(0.0, mean_sq - (avg * avg))
                std_dev = math.sqrt(variance)

                top4 = int(top4_counts[name])
                wins = int(win_counts[name])
                top4_rate = top4 / n
                win_rate = wins / n
                top4_low, top4_high = _wilson_interval(top4, n)
                win_low, win_high = _wilson_interval(wins, n)

                rows.append(
                    {
                        "name": name,
                        "samples": n,
                        "avg_placement": round(avg, 3),
                        "placement_stddev": round(std_dev, 3),
                        "top4_rate": round(top4_rate, 4),
                        "top4_ci95": [round(top4_low, 4), round(top4_high, 4)],
                        "win_rate": round(win_rate, 4),
                        "win_ci95": [round(win_low, 4), round(win_high, 4)],
                    }
                )
            return rows

        champion_metric_rows = _build_rate_rows(
            [name for name, _ in self._champ_counts.most_common(30)],
            self._champ_counts,
            self._champ_placements,
            self._champ_placements_sq,
            self._champ_top4_counts,
            self._champ_win_counts,
        )
        augment_metric_rows = _build_rate_rows(
            [name for name, _ in self._aug_counts.most_common(30)],
            self._aug_counts,
            self._aug_placements,
            self._aug_placements_sq,
            self._aug_top4_counts,
            self._aug_win_counts,
        )

        return {
            "num_games": num_games,
            "num_errors": len(self._errors),
            "num_workers": num_workers,
            "total_time_sec": round(total_time, 1),
            "games_per_sec": round(num_games / total_time, 2) if total_time > 0 else 0,
            "avg_game_time_sec": round(self._sum_game_time / num_games, 3),
            "total_rounds": self._total_rounds,
            "avg_rounds": round(self._total_rounds / num_games, 1),
            "total_training_rows": self._total_rows,
            "total_chunks": self._chunk_idx,
            "top_champions": top_champs,
            "bottom_champions": bot_champs,
            "top_augments": top_augs,
            "champion_pick_rates": dict(self._champ_counts.most_common(20)),
            "confidence_method": "wilson_95",
            "champion_metrics": sorted(champion_metric_rows, key=lambda x: x["avg_placement"])[:20],
            "augment_metrics": sorted(augment_metric_rows, key=lambda x: x["avg_placement"])[:20],
            "cost_telemetry": cost_telemetry,
            "run_config": run_metadata,
        }
