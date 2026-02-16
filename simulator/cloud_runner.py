"""Batch runner for mass TFT game simulations.

Runs N games in parallel across multiple CPU cores, collecting ML training
data and balance analytics. Features:
- Streaming output: writes training data in chunks to avoid OOM
- Checkpoint/resume: saves progress periodically, can resume interrupted batches
- Per-game error handling: one crash doesn't kill the batch
- Agent mixing: configurable distribution of agent types per game

Usage:
    python -m simulator.cloud_runner --games 1000 --workers 8 --output results/run_001
    python -m simulator.cloud_runner --games 10 --workers 1  # Quick test
    python -m simulator.cloud_runner --resume results/run_001  # Resume interrupted batch
    python -m simulator.cloud_runner --games 1000 --agent-mix random:50,econ:30,slam:20
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import multiprocessing
import os
import random
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on path
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from snapshot_schema import JSONISH_COLUMNS
from simulator.game.game import TFTGame
from simulator.game.collector import GameCollector
from simulator.game.actions import MixedLobbyAgent, fast_random_agent

# 95% Wilson interval z-score
WILSON_Z_95 = 1.959963984540054

# Agent profile presets for cloud-scale runs.
# random -> legacy fast_random behavior (no lobby mixing).
AGENT_PROFILES = {
    'random': None,
    'mixed': {'random': 50, 'econ': 30, 'slam': 20},
    'ladder': {'random': 20, 'econ': 45, 'slam': 35},
}

_RUST_FULL_SIMULATOR: Any = None
_RUST_PARQUET_API_VALIDATED: set[str] = set()


class BatchAbort(Exception):
    """Raised when a run should stop early while preserving output state."""


def _pyarrow_available() -> bool:
    try:  # pragma: no cover - optional dependency
        import pyarrow  # noqa: F401
        return True
    except Exception:
        return False


def _normalize_parquet_compression(name: str) -> str:
    value = name.strip().lower()
    mapping = {
        'uncompressed': 'NONE',
        'none': 'NONE',
        'snappy': 'SNAPPY',
        'gzip': 'GZIP',
        'brotli': 'BROTLI',
        'lz4': 'LZ4',
        'zstd': 'ZSTD',
    }
    if value not in mapping:
        valid = ', '.join(sorted(mapping))
        raise ValueError(f"Unsupported parquet compression '{name}'. Valid values: {valid}")
    return mapping[value]


def _rust_extension_rebuild_hint() -> str:
    python_exe = Path(sys.executable)
    cargo_toml = Path(__file__).parent / 'core' / 'rust_engine' / 'Cargo.toml'
    wheel_glob = Path(__file__).parent / 'core' / 'rust_engine' / 'target' / 'wheels' / 'tft_combat_engine-*.whl'
    return (
        f"\"{python_exe}\" -m maturin build --release -m \"{cargo_toml}\" --interpreter \"{python_exe}\"\n"
        f"\"{python_exe}\" -m pip install --force-reinstall \"{wheel_glob}\""
    )


def _extract_signature_parameter_names(method: Any) -> List[str]:
    try:
        return list(inspect.signature(method).parameters.keys())
    except (TypeError, ValueError):
        text_sig = getattr(method, '__text_signature__', None) or ''
        if '(' not in text_sig or ')' not in text_sig:
            return []
        inside = text_sig[text_sig.find('(') + 1:text_sig.rfind(')')]
        names: List[str] = []
        for raw_part in inside.split(','):
            part = raw_part.strip()
            if not part:
                continue
            name = part.split('=')[0].strip()
            if name.startswith('$'):
                name = name[1:]
            names.append(name)
        return names


def _ensure_rust_parquet_method_support(
    rust_simulator: Any,
    method_name: str,
    required_kwargs: Tuple[str, ...] = (
        'compression',
        'use_dictionary',
        'write_statistics',
        'row_group_size',
        'write_batch_size',
    ),
) -> None:
    global _RUST_PARQUET_API_VALIDATED
    if method_name in _RUST_PARQUET_API_VALIDATED:
        return

    method = getattr(rust_simulator, method_name, None)
    if method is None:
        raise RuntimeError(
            f"tft_combat_engine is missing '{method_name}'. Rebuild for the active CPython interpreter:\n"
            f"{_rust_extension_rebuild_hint()}"
        )

    param_names = set(_extract_signature_parameter_names(method))
    missing_kwargs = [name for name in required_kwargs if name not in param_names]
    if missing_kwargs:
        missing_text = ', '.join(missing_kwargs)
        raise RuntimeError(
            f"tft_combat_engine.{method_name} is missing expected kwargs ({missing_text}). "
            f"This usually means the extension was built/installed for a different CPython interpreter than "
            f"the one running this command ({sys.executable}). Rebuild/install into this interpreter:\n"
            f"{_rust_extension_rebuild_hint()}"
        )

    _RUST_PARQUET_API_VALIDATED.add(method_name)


def _wilson_interval(successes: int, trials: int,
                     z: float = WILSON_Z_95) -> Tuple[float, float]:
    """Wilson score interval for Bernoulli metrics."""
    if trials <= 0:
        return 0.0, 0.0

    p = successes / trials
    z2 = z * z
    denom = 1 + (z2 / trials)
    center = (p + (z2 / (2 * trials))) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / trials) + (z2 / (4 * trials * trials)))
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return low, high


def _validate_reference_data_preflight() -> None:
    """Fail-fast if simulator reference data is out of sync."""
    validator = Path(__file__).parent / 'data' / 'validate_reference_data.py'
    if not validator.exists():
        print(f"Warning: reference validator not found at {validator} (skipping)")
        return

    result = subprocess.run(
        [sys.executable, str(validator)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip())
    if result.returncode != 0:
        raise RuntimeError("Simulator reference validation failed before batch run.")


def _compute_seed_end(seed_start: int, num_games: int) -> Optional[int]:
    """Compute inclusive seed end for a [seed_start, num_games] run."""
    if num_games <= 0:
        return None
    return seed_start + num_games - 1


def _resolve_shard_range(
    seed_start: int,
    num_games: int,
    shard_index: Optional[int],
    num_shards: Optional[int],
) -> Tuple[int, int]:
    """Resolve shard-specific seed_start and num_games.

    If shard params are omitted, returns the input values unchanged.
    """
    if shard_index is None and num_shards is None:
        return seed_start, num_games

    if shard_index is None or num_shards is None:
        raise ValueError("Both shard_index and num_shards must be provided together.")

    if num_shards <= 0:
        raise ValueError("num_shards must be > 0.")

    if shard_index < 0 or shard_index >= num_shards:
        raise ValueError(f"shard_index must be in [0, {num_shards - 1}]")

    if num_games < 0:
        raise ValueError("num_games must be >= 0.")

    base = num_games // num_shards
    remainder = num_games % num_shards
    shard_games = base + (1 if shard_index < remainder else 0)
    shard_offset = shard_index * base + min(shard_index, remainder)
    shard_seed_start = seed_start + shard_offset
    return shard_seed_start, shard_games


def _iter_task_batches(tasks: List[Tuple], batch_size: int):
    for start in range(0, len(tasks), batch_size):
        yield tasks[start:start + batch_size]

# ── Per-Game Runner ──────────────────────────────────────────────────────

def run_game(args: Tuple) -> Dict:
    """Run a single game with error handling.

    Args:
        args: (
            game_id,
            seed,
            agent_mix_or_none,
            engine_name,
            include_training_rows,
            rust_full_native_jsonl,
            rust_full_native_parquet,
            parquet_compression,
            parquet_use_dictionary,
            parquet_write_statistics,
            parquet_row_group_size,
            parquet_write_batch_size,
        ) tuple.

    Returns:
        Dict with status='ok' and game data, or status='error' with traceback.
    """
    (
        game_id,
        seed,
        agent_mix,
        engine,
        include_training_rows,
        rust_full_native_jsonl,
        rust_full_native_parquet,
        parquet_compression,
        parquet_use_dictionary,
        parquet_write_statistics,
        parquet_row_group_size,
        parquet_write_batch_size,
    ) = args
    try:
        # Seed before agent assignment for determinism
        random.seed(seed)

        if engine == 'rust_full':
            global _RUST_FULL_SIMULATOR
            global _RUST_PARQUET_API_VALIDATED
            if _RUST_FULL_SIMULATOR is None:
                from tft_combat_engine import RustGameSimulator

                combat_data_path = Path(__file__).parent / 'data' / 'combat_data.json'
                _RUST_FULL_SIMULATOR = RustGameSimulator(str(combat_data_path))
                _RUST_PARQUET_API_VALIDATED.clear()

            start = time.perf_counter()
            if rust_full_native_parquet and include_training_rows:
                _ensure_rust_parquet_method_support(_RUST_FULL_SIMULATOR, 'run_game_parquet')
                rust_result = _RUST_FULL_SIMULATOR.run_game_parquet(
                    game_id,
                    seed,
                    agent_mix,
                    compression=parquet_compression,
                    use_dictionary=parquet_use_dictionary,
                    write_statistics=parquet_write_statistics,
                    row_group_size=parquet_row_group_size,
                    write_batch_size=parquet_write_batch_size,
                )
            elif rust_full_native_jsonl and include_training_rows:
                rust_result = _RUST_FULL_SIMULATOR.run_game_jsonl(game_id, seed, agent_mix)
            else:
                rust_result = _RUST_FULL_SIMULATOR.run_game(
                    game_id,
                    seed,
                    agent_mix,
                    include_training_rows,
                )
            elapsed = time.perf_counter() - start
            analytics = rust_result.get('analytics') or {
                'comp_placements': [],
                'augment_placements': [],
                'champion_placements': [],
            }

            return {
                'status': 'ok',
                'game_id': game_id,
                'seed': seed,
                'elapsed': round(elapsed, 3),
                'rounds': int(rust_result.get('rounds', 0)),
                'placements': rust_result.get('placements', []),
                'training_rows': rust_result.get('training_rows', []),
                'training_rows_jsonl': rust_result.get('training_rows_jsonl', ''),
                'training_rows_parquet': rust_result.get('training_rows_parquet', b''),
                'training_row_count': int(rust_result.get('training_row_count', 0)),
                'analytics': analytics,
            }

        # Build agent
        if agent_mix:
            agent = MixedLobbyAgent(agent_mix)
            agent.assign_players()
            agent_fn = agent
        else:
            agent_fn = None  # TFTGame defaults to fast_random_agent

        collector = GameCollector(game_id)
        game = TFTGame(
            num_players=8,
            seed=seed,
            verbose=False,
            logging_enabled=False,
            collector=collector,
            agent_fn=agent_fn,
            engine=engine,
        )
        start = time.perf_counter()
        game.play()
        elapsed = time.perf_counter() - start

        return {
            'status': 'ok',
            'game_id': game_id,
            'seed': seed,
            'elapsed': round(elapsed, 3),
            'rounds': game.round_num,
            'placements': collector.placements,
            'training_rows': collector.get_training_rows(),
            'analytics': collector.get_analytics(),
        }
    except Exception:
        return {
            'status': 'error',
            'game_id': game_id,
            'seed': seed,
            'error': traceback.format_exc(),
        }


# ── Streaming Writer ─────────────────────────────────────────────────────

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
        parquet_compression: str = 'uncompressed',
        parquet_use_dictionary: bool = False,
        parquet_write_statistics: bool = False,
    ):
        self.output_dir = output_dir
        self.chunk_size = chunk_size
        self.require_parquet = require_parquet
        self.parquet_compression = _normalize_parquet_compression(parquet_compression)
        self.parquet_use_dictionary = parquet_use_dictionary
        self.parquet_write_statistics = parquet_write_statistics
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
            self._completed_seeds = list(resume_state.get('completed_seeds', []))
            self._chunk_idx = resume_state.get('chunks_written', 0)
            self._total_rows = resume_state.get('total_rows', 0)
            self._sum_game_time = resume_state.get('sum_game_time', 0.0)
            self._total_rounds = resume_state.get('total_rounds', 0)
            self._champ_placements = Counter(resume_state.get('champ_placements', {}))
            self._champ_placements_sq = Counter(resume_state.get('champ_placements_sq', {}))
            self._champ_counts = Counter(resume_state.get('champ_counts', {}))
            self._champ_top4_counts = Counter(resume_state.get('champ_top4_counts', {}))
            self._champ_win_counts = Counter(resume_state.get('champ_win_counts', {}))
            self._aug_placements = Counter(resume_state.get('aug_placements', {}))
            self._aug_placements_sq = Counter(resume_state.get('aug_placements_sq', {}))
            self._aug_counts = Counter(resume_state.get('aug_counts', {}))
            self._aug_top4_counts = Counter(resume_state.get('aug_top4_counts', {}))
            self._aug_win_counts = Counter(resume_state.get('aug_win_counts', {}))

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
        return f'chunk_{self._chunk_idx:04d}'

    def add_result(self, result: Dict, *, buffer_training_rows: bool = True):
        """Process a completed game result."""
        if result['status'] == 'error':
            self._errors.append({
                'game_id': result['game_id'],
                'seed': result['seed'],
                'error': result['error'],
            })
            return

        self._completed_seeds.append(result['seed'])
        self._sum_game_time += result['elapsed']
        self._total_rounds += result['rounds']

        if buffer_training_rows:
            # Buffer training rows
            training_rows = result.get('training_rows', [])
            if training_rows:
                self._row_buffer.extend(training_rows)
                self._pending_row_count += len(training_rows)
            training_rows_jsonl = result.get('training_rows_jsonl', '')
            if training_rows_jsonl:
                self._jsonl_blob_buffer.append(training_rows_jsonl)
                self._pending_row_count += int(result.get('training_row_count', 0))
            training_rows_parquet = result.get('training_rows_parquet', b'')
            if training_rows_parquet:
                self._parquet_blob_buffer.append(training_rows_parquet)
                self._pending_row_count += int(result.get('training_row_count', 0))

        # Accumulate analytics
        analytics = result['analytics']
        for name, placement in analytics['champion_placements']:
            self._champ_placements[name] += placement
            self._champ_placements_sq[name] += placement * placement
            self._champ_counts[name] += 1
            if placement <= 4:
                self._champ_top4_counts[name] += 1
            if placement == 1:
                self._champ_win_counts[name] += 1
        for name, placement in analytics['augment_placements']:
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
        self._total_rows += max(0, row_count)
        self._chunk_idx += 1
        self._games_in_buffer = 0

    def _flush_chunk(self):
        """Write buffered training rows to a chunk file."""
        if not self._row_buffer and not self._jsonl_blob_buffer and not self._parquet_blob_buffer:
            return

        chunk_name = f'chunk_{self._chunk_idx:04d}'
        if self._parquet_blob_buffer:
            self._write_parquet_blob_chunk(chunk_name)
        elif self._jsonl_blob_buffer:
            if self.require_parquet:
                self._write_parquet_from_jsonl_blob_chunk(chunk_name)
            else:
                try:
                    self._write_parquet_from_jsonl_blob_chunk(chunk_name)
                except (ImportError, Exception):
                    self._write_jsonl_blob_chunk(chunk_name)
        else:
            if self.require_parquet:
                self._write_parquet_chunk(chunk_name)
            else:
                try:
                    self._write_parquet_chunk(chunk_name)
                except (ImportError, Exception):
                    self._write_jsonl_chunk(chunk_name)

        self._total_rows += self._pending_row_count
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
        path = os.path.join(self.output_dir, chunk_name + '.parquet')
        pq.write_table(
            table,
            path,
            compression=self.parquet_compression,
            use_dictionary=self.parquet_use_dictionary,
            write_statistics=self.parquet_write_statistics,
        )

    def _write_jsonl_chunk(self, chunk_name: str):
        """Write chunk as JSON Lines (fallback)."""
        path = os.path.join(self.output_dir, chunk_name + '.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for row in self._row_buffer:
                f.write(json.dumps(row) + '\n')

    def _write_jsonl_blob_chunk(self, chunk_name: str):
        """Write pre-serialized JSONL payloads from Rust."""
        path = os.path.join(self.output_dir, chunk_name + '.jsonl')
        with open(path, 'w', encoding='utf-8') as f:
            for blob in self._jsonl_blob_buffer:
                if not blob:
                    continue
                f.write(blob)
                if not blob.endswith('\n'):
                    f.write('\n')

    def _write_parquet_blob_chunk(self, chunk_name: str):
        """Aggregate Rust-prebuilt parquet blobs into one chunk parquet file."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except Exception:
            # Fallback: preserve behavior if pyarrow is unavailable.
            for idx, blob in enumerate(self._parquet_blob_buffer):
                if not blob:
                    continue
                path = os.path.join(self.output_dir, f'{chunk_name}_{idx:04d}.parquet')
                with open(path, 'wb') as f:
                    f.write(blob)
            return

        path = os.path.join(self.output_dir, chunk_name + '.parquet')
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
        except Exception:
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
                fallback_path = os.path.join(self.output_dir, f'{chunk_name}_{idx:04d}.parquet')
                with open(fallback_path, 'wb') as f:
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

        payload = ''.join(blob for blob in self._jsonl_blob_buffer if blob)
        if payload and not payload.endswith('\n'):
            payload += '\n'
        if not payload:
            return

        table = paj.read_json(pa.BufferReader(payload.encode('utf-8')))
        path = os.path.join(self.output_dir, chunk_name + '.parquet')
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
            'completed_seeds': sorted(self._completed_seeds),
            'num_completed': len(self._completed_seeds),
            'num_errors': len(self._errors),
            'chunks_written': self._chunk_idx,
            'total_rows': self._total_rows,
            'sum_game_time': self._sum_game_time,
            'total_rounds': self._total_rounds,
            'champ_placements': dict(self._champ_placements),
            'champ_placements_sq': dict(self._champ_placements_sq),
            'champ_counts': dict(self._champ_counts),
            'champ_top4_counts': dict(self._champ_top4_counts),
            'champ_win_counts': dict(self._champ_win_counts),
            'aug_placements': dict(self._aug_placements),
            'aug_placements_sq': dict(self._aug_placements_sq),
            'aug_counts': dict(self._aug_counts),
            'aug_top4_counts': dict(self._aug_top4_counts),
            'aug_win_counts': dict(self._aug_win_counts),
        }
        path = os.path.join(self.output_dir, 'checkpoint.json')
        # Write atomically (write to temp, then rename)
        tmp_path = path + '.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f)
        os.replace(tmp_path, path)

    def finalize(self, total_time: float, num_workers: int,
                 run_metadata: Optional[Dict[str, Any]] = None) -> Dict:
        """Flush remaining data, write errors, summary, and final checkpoint."""
        self._flush_chunk()

        # Write errors
        if self._errors:
            error_path = os.path.join(self.output_dir, 'errors.json')
            with open(error_path, 'w', encoding='utf-8') as f:
                json.dump(self._errors, f, indent=2)
            print(f"  Errors: {error_path} ({len(self._errors)} failures)")

        # Compute and write summary
        summary = self._compute_summary(total_time, num_workers, run_metadata or {})
        summary_path = os.path.join(self.output_dir, 'summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        print(f"  Summary: {summary_path}")

        # Final checkpoint
        self.write_checkpoint()

        return summary

    def _compute_summary(self, total_time: float, num_workers: int,
                         run_metadata: Dict[str, Any]) -> Dict:
        """Compute aggregate statistics."""
        num_games = len(self._completed_seeds)
        if num_games == 0:
            return {
                'num_games': 0,
                'num_errors': len(self._errors),
                'num_workers': num_workers,
                'total_time_sec': round(total_time, 1),
                'run_config': run_metadata,
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

        def _build_rate_rows(names: List[str], counts: Counter, placements: Counter,
                             placements_sq: Counter, top4_counts: Counter,
                             win_counts: Counter) -> List[Dict[str, Any]]:
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

                rows.append({
                    'name': name,
                    'samples': n,
                    'avg_placement': round(avg, 3),
                    'placement_stddev': round(std_dev, 3),
                    'top4_rate': round(top4_rate, 4),
                    'top4_ci95': [round(top4_low, 4), round(top4_high, 4)],
                    'win_rate': round(win_rate, 4),
                    'win_ci95': [round(win_low, 4), round(win_high, 4)],
                })
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
            'num_games': num_games,
            'num_errors': len(self._errors),
            'num_workers': num_workers,
            'total_time_sec': round(total_time, 1),
            'games_per_sec': round(num_games / total_time, 2) if total_time > 0 else 0,
            'avg_game_time_sec': round(self._sum_game_time / num_games, 3),
            'avg_rounds': round(self._total_rounds / num_games, 1),
            'total_training_rows': self._total_rows,
            'total_chunks': self._chunk_idx,
            'top_champions': top_champs,
            'bottom_champions': bot_champs,
            'top_augments': top_augs,
            'champion_pick_rates': dict(self._champ_counts.most_common(20)),
            'confidence_method': 'wilson_95',
            'champion_metrics': sorted(champion_metric_rows, key=lambda x: x['avg_placement'])[:20],
            'augment_metrics': sorted(augment_metric_rows, key=lambda x: x['avg_placement'])[:20],
            'run_config': run_metadata,
        }


# ── Worker Init ──────────────────────────────────────────────────────────

def _worker_init(engine: str = 'python'):
    """Worker process initializer - pre-loads shared data."""
    if engine == 'rust':
        from tft_combat_engine import RustCombatEngine

        combat_data_path = Path(__file__).parent / 'data' / 'combat_data.json'
        RustCombatEngine(str(combat_data_path))
        return
    if engine == 'rust_full':
        global _RUST_FULL_SIMULATOR
        global _RUST_PARQUET_API_VALIDATED
        from tft_combat_engine import RustGameSimulator

        combat_data_path = Path(__file__).parent / 'data' / 'combat_data.json'
        _RUST_FULL_SIMULATOR = RustGameSimulator(str(combat_data_path))
        _RUST_PARQUET_API_VALIDATED.clear()
        return

    from simulator.core.combat_engine import CombatEngine
    CombatEngine()  # Warm the cache


# ── Batch Runner ─────────────────────────────────────────────────────────

def run_batch(
    num_games: int,
    num_workers: int,
    output_dir: str,
    seed_start: int = 0,
    agent_mix: Optional[Dict] = None,
    chunk_size: int = 100,
    resume: bool = False,
    agent_profile: str = 'random',
    checkpoint_every: Optional[int] = None,
    progress_every: Optional[int] = 500,
    max_errors: Optional[int] = None,
    require_parquet: bool = False,
    pool_chunksize: Optional[int] = None,
    pool_chunksize_max: Optional[int] = None,
    shard_index: Optional[int] = None,
    num_shards: Optional[int] = None,
    engine: str = 'python',
    rust_full_include_training_rows: bool = True,
    rust_full_native_jsonl: bool = False,
    rust_full_native_parquet: bool = False,
    rust_full_native_parquet_direct: bool = False,
    rust_full_rayon_batch_size: Optional[int] = None,
    rust_full_rayon_threads: Optional[int] = None,
    parquet_compression: str = 'uncompressed',
    parquet_use_dictionary: bool = False,
    parquet_write_statistics: bool = False,
    parquet_row_group_size: Optional[int] = None,
    parquet_write_batch_size: Optional[int] = None,
) -> Dict:
    """Run num_games in parallel with streaming output and checkpoints.

    Args:
        num_games: Total number of games to simulate.
        num_workers: Number of parallel worker processes.
        output_dir: Directory to write results to.
        seed_start: Starting seed (games use seeds seed_start..seed_start+num_games-1).
        agent_mix: Agent type distribution, e.g. {'random': 50, 'econ': 30, 'slam': 20}.
        chunk_size: Number of games per output chunk (controls memory usage).
        resume: If True, resume from existing checkpoint in output_dir.
        agent_profile: Agent profile name used for this run.
        checkpoint_every: Number of completed tasks between checkpoints.
        progress_every: Number of completed tasks between progress prints (defaults to 500).
        max_errors: Stop run early after this many per-game errors.
        require_parquet: Fail output writes if parquet cannot be written.
        pool_chunksize: Explicit multiprocessing imap chunk size.
        pool_chunksize_max: Upper bound on multiprocessing imap chunk size.
        shard_index: Shard index for deterministic seed partitioning.
        num_shards: Total shard count for deterministic seed partitioning.
        engine: Simulation backend ('python', 'rust', or 'rust_full').
        rust_full_include_training_rows: If False, skip per-round training rows in rust_full.
        rust_full_native_jsonl: Use Rust-pre-serialized JSONL rows in rust_full mode.
        rust_full_native_parquet: Use Rust-pre-serialized parquet rows in rust_full mode.
        rust_full_native_parquet_direct: Write chunk parquet files directly from Rust in batch mode.
        rust_full_rayon_batch_size: Batch size for Rust rayon batch API (rust_full only).
        rust_full_rayon_threads: Rayon thread count override for rust_full batch API.
        parquet_compression: Output parquet compression codec.
        parquet_use_dictionary: Whether parquet dictionary encoding is enabled.
        parquet_write_statistics: Whether parquet statistics are written.
        parquet_row_group_size: Optional parquet row-group size hint for Rust-native parquet paths.
        parquet_write_batch_size: Optional parquet write batch size hint for Rust-native parquet paths.

    Returns:
        Summary dict with timing and aggregate stats.
    """
    if pool_chunksize is not None and pool_chunksize <= 0:
        raise ValueError("pool_chunksize must be > 0 when provided.")
    if pool_chunksize_max is not None and pool_chunksize_max <= 0:
        raise ValueError("pool_chunksize_max must be > 0 when provided.")
    if rust_full_native_jsonl and engine != 'rust_full':
        raise ValueError("rust_full_native_jsonl can only be used with engine='rust_full'.")
    if rust_full_native_parquet and engine != 'rust_full':
        raise ValueError("rust_full_native_parquet can only be used with engine='rust_full'.")
    if rust_full_native_parquet_direct and engine != 'rust_full':
        raise ValueError("rust_full_native_parquet_direct can only be used with engine='rust_full'.")
    if rust_full_native_jsonl and rust_full_native_parquet:
        raise ValueError("rust_full_native_jsonl and rust_full_native_parquet are mutually exclusive.")
    if rust_full_native_parquet_direct and rust_full_native_jsonl:
        raise ValueError("rust_full_native_parquet_direct cannot be combined with rust_full_native_jsonl.")
    if rust_full_native_parquet_direct and not rust_full_native_parquet:
        raise ValueError("rust_full_native_parquet_direct requires rust_full_native_parquet.")
    if rust_full_native_parquet_direct and not rust_full_include_training_rows:
        raise ValueError("rust_full_native_parquet_direct requires rust_full_include_training_rows.")
    if rust_full_native_parquet_direct and rust_full_rayon_batch_size is None:
        raise ValueError("rust_full_native_parquet_direct requires rust_full_rayon_batch_size.")
    if rust_full_rayon_batch_size is not None and rust_full_rayon_batch_size <= 0:
        raise ValueError("rust_full_rayon_batch_size must be > 0 when provided.")
    if rust_full_rayon_threads is not None and rust_full_rayon_threads <= 0:
        raise ValueError("rust_full_rayon_threads must be > 0 when provided.")
    if (rust_full_rayon_batch_size is not None or rust_full_rayon_threads is not None) and engine != 'rust_full':
        raise ValueError("Rust rayon batch options require engine='rust_full'.")
    if parquet_row_group_size is not None and parquet_row_group_size <= 0:
        raise ValueError("parquet_row_group_size must be > 0 when provided.")
    if parquet_write_batch_size is not None and parquet_write_batch_size <= 0:
        raise ValueError("parquet_write_batch_size must be > 0 when provided.")
    _normalize_parquet_compression(parquet_compression)

    requested_seed_start = seed_start
    requested_num_games = num_games
    requested_seed_end = _compute_seed_end(requested_seed_start, requested_num_games)
    effective_seed_start, effective_num_games = _resolve_shard_range(
        seed_start=requested_seed_start,
        num_games=requested_num_games,
        shard_index=shard_index,
        num_shards=num_shards,
    )
    effective_seed_end = _compute_seed_end(effective_seed_start, effective_num_games)

    # Load checkpoint if resuming
    resume_state = None
    completed_seeds = set()
    if resume:
        checkpoint_path = os.path.join(output_dir, 'checkpoint.json')
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                resume_state = json.load(f)
            completed_seeds = set(resume_state.get('completed_seeds', []))
            print(f"Resuming from checkpoint: {len(completed_seeds)} games already done")
        else:
            print("No checkpoint found, starting fresh")

    if require_parquet and not _pyarrow_available():
        raise RuntimeError(
            "require_parquet was set but pyarrow is unavailable. "
            "Install pyarrow or remove --require-parquet."
        )

    os.makedirs(output_dir, exist_ok=True)
    writer = StreamingWriter(
        output_dir,
        chunk_size=chunk_size,
        resume_state=resume_state,
        require_parquet=require_parquet,
        parquet_compression=parquet_compression,
        parquet_use_dictionary=parquet_use_dictionary,
        parquet_write_statistics=parquet_write_statistics,
    )

    # Build task list, skipping completed seeds
    all_seeds = [effective_seed_start + i for i in range(effective_num_games)]
    tasks = [
        (
            s,
            s,
            agent_mix,
            engine,
            rust_full_include_training_rows,
            rust_full_native_jsonl,
            rust_full_native_parquet,
            parquet_compression,
            parquet_use_dictionary,
            parquet_write_statistics,
            parquet_row_group_size,
            parquet_write_batch_size,
        )
        for s in all_seeds
             if s not in completed_seeds]
    remaining = len(tasks)

    resolved_pool_chunksize: Optional[int] = None
    if num_workers > 1 and remaining > 0:
        default_pool_chunksize = max(1, remaining // (num_workers * 4))
        resolved_pool_chunksize = pool_chunksize or default_pool_chunksize
        if pool_chunksize_max is not None:
            resolved_pool_chunksize = min(resolved_pool_chunksize, pool_chunksize_max)
        resolved_pool_chunksize = min(resolved_pool_chunksize, remaining)

    use_rust_rayon_batches = (
        engine == 'rust_full'
        and rust_full_rayon_batch_size is not None
    )
    use_rust_batch_parquet_api = (
        use_rust_rayon_batches
        and rust_full_include_training_rows
        and rust_full_native_parquet
    )
    use_rust_batch_parquet_file_api = (
        use_rust_batch_parquet_api
        and rust_full_native_parquet_direct
    )

    if remaining == 0:
        print("All games already completed!")
        return writer.finalize(
            0.0,
            num_workers,
            run_metadata={
                'seed_start': effective_seed_start,
                'seed_end': effective_seed_end,
                'effective_seed_start': effective_seed_start,
                'effective_seed_end': effective_seed_end,
                'requested_seed_start': requested_seed_start,
                'requested_seed_end': requested_seed_end,
                'requested_num_games': requested_num_games,
                'effective_num_games': effective_num_games,
                'agent_profile': agent_profile,
                'agent_mix': agent_mix if agent_mix else {'random': 100},
                'chunk_size': chunk_size,
                'pool_chunksize': resolved_pool_chunksize,
                'pool_chunksize_max': pool_chunksize_max,
                'shard_index': shard_index,
                'num_shards': num_shards,
                'engine': engine,
                'rust_full_include_training_rows': rust_full_include_training_rows,
                'rust_full_native_jsonl': rust_full_native_jsonl,
                'rust_full_native_parquet': rust_full_native_parquet,
                'rust_full_native_parquet_direct': rust_full_native_parquet_direct,
                'rust_full_rayon_batch_size': rust_full_rayon_batch_size,
                'rust_full_rayon_threads': rust_full_rayon_threads,
                'rust_full_batch_parquet_api': use_rust_batch_parquet_api,
                'rust_full_batch_parquet_file_api': use_rust_batch_parquet_file_api,
                'parquet_compression': parquet_compression,
                'parquet_use_dictionary': parquet_use_dictionary,
                'parquet_write_statistics': parquet_write_statistics,
                'parquet_row_group_size': parquet_row_group_size,
                'parquet_write_batch_size': parquet_write_batch_size,
                'resume': resume,
                'checkpoint_every': checkpoint_every,
                'progress_every': progress_every,
                'max_errors': max_errors,
                'require_parquet': require_parquet,
                'aborted': False,
                'aborted_reason': None,
            },
        )

    agent_desc = 'default (fast_random)' if not agent_mix else str(agent_mix)
    print(f"Running {remaining} games across {num_workers} workers "
          f"(chunk_size={chunk_size})")
    if effective_seed_end is None:
        seed_span = "none"
    else:
        seed_span = f"{effective_seed_start} to {effective_seed_end}"
    print(f"Seeds: {seed_span} ({len(completed_seeds)} already done)")
    if num_shards is not None and shard_index is not None:
        print(f"Shard: {shard_index + 1}/{num_shards} "
              f"(requested_games={requested_num_games}, shard_games={effective_num_games})")
    if resolved_pool_chunksize is not None:
        print(f"Pool chunksize: {resolved_pool_chunksize}"
              f"{'' if pool_chunksize_max is None else f' (cap={pool_chunksize_max})'}")
    print(f"Agents: {agent_desc}")
    print(f"Engine: {engine}")
    print(f"Output: {output_dir}")
    print()

    start = time.perf_counter()
    checkpoint_interval = checkpoint_every if checkpoint_every and checkpoint_every > 0 else max(1, remaining // 20)
    progress_interval = progress_every if progress_every and progress_every > 0 else 500
    if remaining > 0 and progress_interval > remaining:
        # Avoid small test runs appearing "stuck" until completion.
        progress_interval = max(1, remaining // 10)
    done = 0
    aborted_reason: Optional[str] = None

    def _process_result(result: Dict, *, buffer_training_rows: bool = True):
        nonlocal done
        writer.add_result(result, buffer_training_rows=buffer_training_rows)
        done += 1
        if done % progress_interval == 0 or done == remaining:
            elapsed = time.perf_counter() - start
            rate = done / elapsed if elapsed > 0 else 0
            eta = (remaining - done) / rate if rate > 0 else 0
            err_str = f", {writer.num_errors} errors" if writer.num_errors else ""
            print(f"  [{done}/{remaining}] {rate:.1f} games/sec, "
                  f"ETA: {eta:.0f}s{err_str}", flush=True)

        if max_errors is not None and writer.num_errors >= max_errors:
            raise BatchAbort(f"Reached max error threshold ({writer.num_errors}/{max_errors}).")

        if done % checkpoint_interval == 0:
            writer.write_checkpoint()

    if use_rust_rayon_batches:
        _worker_init('rust_full')
        global _RUST_FULL_SIMULATOR
        rayon_threads = rust_full_rayon_threads or num_workers
        if use_rust_batch_parquet_file_api:
            _ensure_rust_parquet_method_support(
                _RUST_FULL_SIMULATOR,
                'run_games_batch_parquet_to_file',
            )
        if use_rust_batch_parquet_api:
            _ensure_rust_parquet_method_support(
                _RUST_FULL_SIMULATOR,
                'run_games_batch_parquet',
            )
        batch_output_mode = 'rows'
        if rust_full_include_training_rows and not use_rust_batch_parquet_api:
            if rust_full_native_parquet:
                batch_output_mode = 'parquet'
            elif rust_full_native_jsonl:
                batch_output_mode = 'jsonl'
        print(
            "Rust rayon batch mode: "
            f"batch_size={rust_full_rayon_batch_size}, threads={rayon_threads}, "
            f"output_mode={batch_output_mode}, "
            f"batch_parquet_api={use_rust_batch_parquet_api}, "
            f"batch_parquet_file_api={use_rust_batch_parquet_file_api}"
        )

        try:
            task_cursor = 0
            while task_cursor < len(tasks):
                next_batch_size = rust_full_rayon_batch_size
                if use_rust_batch_parquet_file_api:
                    # In direct-file mode, each Rust batch call writes one chunk file.
                    next_batch_size = min(chunk_size, len(tasks) - task_cursor)
                elif use_rust_batch_parquet_api:
                    games_until_chunk_flush = max(1, chunk_size - writer.games_in_buffer)
                    next_batch_size = min(next_batch_size, games_until_chunk_flush)
                task_batch = tasks[task_cursor:task_cursor + next_batch_size]
                task_cursor += len(task_batch)
                batch_game_ids = [task[0] for task in task_batch]
                batch_seeds = [task[1] for task in task_batch]
                batch_wrote_parquet = False
                batch_training_row_count = 0
                try:
                    if use_rust_batch_parquet_file_api:
                        chunk_name = writer.next_chunk_name
                        chunk_path = os.path.join(output_dir, chunk_name + '.parquet')
                        batch_payload = _RUST_FULL_SIMULATOR.run_games_batch_parquet_to_file(
                            batch_game_ids,
                            batch_seeds,
                            chunk_path,
                            agent_mix,
                            rust_full_include_training_rows,
                            rayon_threads,
                            compression=parquet_compression,
                            use_dictionary=parquet_use_dictionary,
                            write_statistics=parquet_write_statistics,
                            row_group_size=parquet_row_group_size,
                            write_batch_size=parquet_write_batch_size,
                        )
                        batch_results = list(batch_payload.get('results', []))
                        batch_training_row_count = int(batch_payload.get('training_row_count', 0))
                        batch_wrote_parquet = bool(batch_payload.get('wrote_parquet', False))
                    elif use_rust_batch_parquet_api:
                        batch_payload = _RUST_FULL_SIMULATOR.run_games_batch_parquet(
                            batch_game_ids,
                            batch_seeds,
                            agent_mix,
                            rust_full_include_training_rows,
                            rayon_threads,
                            compression=parquet_compression,
                            use_dictionary=parquet_use_dictionary,
                            write_statistics=parquet_write_statistics,
                            row_group_size=parquet_row_group_size,
                            write_batch_size=parquet_write_batch_size,
                        )
                        batch_results = list(batch_payload.get('results', []))
                        batch_parquet_blob = batch_payload.get('training_rows_parquet', b'')
                        batch_training_row_count = int(batch_payload.get('training_row_count', 0))
                        if batch_parquet_blob:
                            for result in batch_results:
                                if result.get('status') == 'ok':
                                    result['training_rows_parquet'] = batch_parquet_blob
                                    result['training_row_count'] = batch_training_row_count
                                    break
                    else:
                        batch_results = _RUST_FULL_SIMULATOR.run_games_batch(
                            batch_game_ids,
                            batch_seeds,
                            agent_mix,
                            rust_full_include_training_rows,
                            batch_output_mode,
                            rayon_threads,
                        )
                except Exception:
                    error_text = traceback.format_exc()
                    batch_results = [
                        {
                            'status': 'error',
                            'game_id': game_id,
                            'seed': seed,
                            'error': error_text,
                        }
                        for game_id, seed in zip(batch_game_ids, batch_seeds)
                    ]

                for result in batch_results:
                    _process_result(
                        result,
                        buffer_training_rows=not use_rust_batch_parquet_file_api,
                    )
                if use_rust_batch_parquet_file_api and batch_wrote_parquet:
                    writer.record_external_parquet_chunk(batch_training_row_count)
        except BatchAbort as exc:
            aborted_reason = str(exc)
    elif num_workers <= 1:
        # Sequential mode
        _worker_init(engine)
        try:
            for task in tasks:
                result = run_game(task)
                _process_result(result)
        except BatchAbort as exc:
            aborted_reason = str(exc)
    else:
        # Parallel mode
        with multiprocessing.Pool(
            num_workers,
            initializer=_worker_init,
            initargs=(engine,),
        ) as pool:
            chunksize = resolved_pool_chunksize or 1
            try:
                for result in pool.imap_unordered(run_game, tasks, chunksize=chunksize):
                    _process_result(result)
            except BatchAbort as exc:
                aborted_reason = str(exc)
                pool.terminate()

    total_time = time.perf_counter() - start
    if aborted_reason:
        print(f"\nRun aborted early: {aborted_reason}")
        print(f"Processed {done}/{remaining} tasks before stop.")
    else:
        print(f"\nAll {remaining} games completed in {total_time:.1f}s "
              f"({remaining / total_time:.1f} games/sec)")
    if writer.num_errors:
        print(f"  {writer.num_errors} games failed (see errors.json)")

    writer.write_checkpoint()
    print("Writing final results...")
    summary = writer.finalize(
        total_time,
        num_workers,
        run_metadata={
            'seed_start': effective_seed_start,
            'seed_end': effective_seed_end,
            'effective_seed_start': effective_seed_start,
            'effective_seed_end': effective_seed_end,
            'requested_seed_start': requested_seed_start,
            'requested_seed_end': requested_seed_end,
            'requested_num_games': requested_num_games,
            'effective_num_games': effective_num_games,
            'agent_profile': agent_profile,
            'agent_mix': agent_mix if agent_mix else {'random': 100},
            'chunk_size': chunk_size,
            'pool_chunksize': resolved_pool_chunksize,
            'pool_chunksize_max': pool_chunksize_max,
            'shard_index': shard_index,
            'num_shards': num_shards,
            'engine': engine,
            'rust_full_include_training_rows': rust_full_include_training_rows,
            'rust_full_native_jsonl': rust_full_native_jsonl,
            'rust_full_native_parquet': rust_full_native_parquet,
            'rust_full_native_parquet_direct': rust_full_native_parquet_direct,
            'rust_full_rayon_batch_size': rust_full_rayon_batch_size,
            'rust_full_rayon_threads': rust_full_rayon_threads,
            'rust_full_batch_parquet_api': use_rust_batch_parquet_api,
            'rust_full_batch_parquet_file_api': use_rust_batch_parquet_file_api,
            'parquet_compression': parquet_compression,
            'parquet_use_dictionary': parquet_use_dictionary,
            'parquet_write_statistics': parquet_write_statistics,
            'parquet_row_group_size': parquet_row_group_size,
            'parquet_write_batch_size': parquet_write_batch_size,
            'resume': resume,
            'checkpoint_every': checkpoint_interval,
            'progress_every': progress_interval,
            'max_errors': max_errors,
            'require_parquet': require_parquet,
            'aborted': bool(aborted_reason),
            'aborted_reason': aborted_reason,
        },
    )
    return summary


# ── CLI ──────────────────────────────────────────────────────────────────

def _parse_agent_mix(s: str) -> Dict[str, int]:
    """Parse agent mix string like 'random:50,econ:30,slam:20'."""
    mix = {}
    for part in s.split(','):
        name, weight = part.strip().split(':')
        name = name.strip()
        if name not in ('random', 'econ', 'slam'):
            raise ValueError(f"Unknown agent type '{name}'. "
                             f"Valid types: random, econ, slam")
        parsed_weight = int(weight.strip())
        if parsed_weight < 0:
            raise ValueError(f"Weight for '{name}' cannot be negative")
        mix[name] = parsed_weight
    if not mix or sum(mix.values()) <= 0:
        raise ValueError("Agent mix must include at least one positive weight")
    return mix


def _cli_flag_present(argv: List[str], flag: str) -> bool:
    return any(arg == flag or arg.startswith(f"{flag}=") for arg in argv)


def main():
    parser = argparse.ArgumentParser(
        description='Run batch TFT game simulations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Quick test:       python -m simulator.cloud_runner --games 10 --workers 1
  Production run:   python -m simulator.cloud_runner --games 10000 --workers 8 --output results/run_001
  Resume crashed:   python -m simulator.cloud_runner --games 10000 --resume results/run_001
  Mixed agents:     python -m simulator.cloud_runner --games 1000 --agent-mix random:50,econ:30,slam:20
  Ladder profile:   python -m simulator.cloud_runner --games 1000 --agent-profile ladder
  Large scale:      python -m simulator.cloud_runner --games 100000 --chunk-size 500
  Shard 1/4:        python -m simulator.cloud_runner --games 1000000 --num-shards 4 --shard-index 0
  Shard 2/4:        python -m simulator.cloud_runner --games 1000000 --num-shards 4 --shard-index 1
        """,
    )
    parser.add_argument('--games', type=int, default=10,
                        help='Number of games to simulate')
    parser.add_argument('--workers', type=int, default=None,
                        help='Number of parallel workers (default: CPU count - 1)')
    parser.add_argument('--output', type=str, default='results/batch',
                        help='Output directory for results')
    parser.add_argument('--seed-start', type=int, default=0,
                        help='Starting seed for deterministic runs')
    parser.add_argument('--agent-mix', type=str, default=None,
                        help='Agent type distribution, e.g. "random:50,econ:30,slam:20"')
    parser.add_argument('--agent-profile', type=str, default='random',
                        choices=sorted(AGENT_PROFILES.keys()),
                        help='Preset agent behavior profile used when --agent-mix is not provided')
    parser.add_argument('--chunk-size', type=int, default=100,
                        help='Games per output chunk (controls memory usage)')
    parser.add_argument('--resume', type=str, default=None, metavar='DIR',
                        help='Resume an interrupted batch from checkpoint in DIR')
    parser.add_argument('--checkpoint-every', type=int, default=None,
                        help='Write checkpoint every N completed tasks')
    parser.add_argument('--progress-every', type=int, default=500,
                        help='Print progress every N completed tasks (default: 500)')
    parser.add_argument('--max-errors', type=int, default=None,
                        help='Stop run early after N game errors')
    parser.add_argument('--require-parquet', action='store_true',
                        help='Fail run if parquet output is unavailable')
    parser.add_argument('--pool-chunksize', type=int, default=None,
                        help='Explicit multiprocessing imap chunk size (default: auto)')
    parser.add_argument('--pool-chunksize-max', type=int, default=None,
                        help='Optional upper bound for multiprocessing imap chunk size')
    parser.add_argument('--shard-index', type=int, default=None,
                        help='Shard index (0-based) when partitioning a run across machines')
    parser.add_argument('--num-shards', type=int, default=None,
                        help='Total number of shards when partitioning a run across machines')
    parser.add_argument('--engine', type=str, default='python', choices=['python', 'rust', 'rust_full'],
                        help='Simulation backend (default: python)')
    parser.add_argument('--no-rust-full-auto-profile', action='store_true',
                        help='Disable rust_full auto-tuned defaults and use explicit/baseline options')
    parser.add_argument('--rust-full-summary-only', action='store_true',
                        help='Skip training row generation in rust_full mode for max throughput')
    parser.add_argument('--rust-full-native-jsonl', action=argparse.BooleanOptionalAction, default=None,
                        help='Enable/disable Rust-pre-serialized JSONL rows in rust_full mode')
    parser.add_argument('--rust-full-native-parquet', action=argparse.BooleanOptionalAction, default=None,
                        help='Enable/disable Rust-pre-serialized parquet rows in rust_full mode')
    parser.add_argument('--rust-full-native-parquet-direct', action=argparse.BooleanOptionalAction, default=None,
                        help='Enable/disable direct Rust chunk parquet file writing in rust_full batch mode')
    parser.add_argument('--rust-full-rayon-batch-size', type=int, default=None,
                        help='Use Rust rayon batch API with this per-call batch size (rust_full only)')
    parser.add_argument('--rust-full-rayon-threads', type=int, default=None,
                        help='Override rayon thread count for rust_full batch API')
    parser.add_argument('--parquet-compression', type=str, default=None,
                        help='Parquet compression codec: uncompressed|snappy|zstd|gzip|brotli|lz4')
    parser.add_argument('--parquet-use-dictionary', action=argparse.BooleanOptionalAction, default=None,
                        help='Enable/disable parquet dictionary encoding for chunk writes')
    parser.add_argument('--parquet-write-statistics', action=argparse.BooleanOptionalAction, default=None,
                        help='Enable/disable parquet column statistics for chunk writes')
    parser.add_argument('--parquet-row-group-size', type=int, default=None,
                        help='Optional parquet row-group size for Rust-native parquet writes')
    parser.add_argument('--parquet-write-batch-size', type=int, default=None,
                        help='Optional parquet write batch size for Rust-native parquet writes')
    parser.add_argument('--skip-reference-validation', action='store_true',
                        help='Skip simulator reference preflight validation')
    args = parser.parse_args()

    if (args.shard_index is None) != (args.num_shards is None):
        parser.error("--shard-index and --num-shards must be provided together")
    if args.games < 0:
        parser.error("--games must be >= 0")
    if args.pool_chunksize is not None and args.pool_chunksize <= 0:
        parser.error("--pool-chunksize must be > 0")
    if args.pool_chunksize_max is not None and args.pool_chunksize_max <= 0:
        parser.error("--pool-chunksize-max must be > 0")
    if args.num_shards is not None:
        if args.num_shards <= 0:
            parser.error("--num-shards must be > 0")
        if args.shard_index < 0 or args.shard_index >= args.num_shards:
            parser.error(f"--shard-index must be in [0, {args.num_shards - 1}]")
    if args.rust_full_native_jsonl is True and args.engine != 'rust_full':
        parser.error("--rust-full-native-jsonl requires --engine rust_full")
    if args.rust_full_native_parquet is True and args.engine != 'rust_full':
        parser.error("--rust-full-native-parquet requires --engine rust_full")
    if args.rust_full_native_parquet_direct is True and args.engine != 'rust_full':
        parser.error("--rust-full-native-parquet-direct requires --engine rust_full")
    if args.rust_full_native_jsonl is True and args.rust_full_native_parquet is True:
        parser.error("--rust-full-native-jsonl and --rust-full-native-parquet cannot be combined")
    if args.rust_full_native_parquet_direct is True and args.rust_full_native_jsonl is True:
        parser.error("--rust-full-native-parquet-direct cannot be combined with --rust-full-native-jsonl")
    if args.rust_full_rayon_batch_size is not None:
        if args.rust_full_rayon_batch_size <= 0:
            parser.error("--rust-full-rayon-batch-size must be > 0")
        if args.engine != 'rust_full':
            parser.error("--rust-full-rayon-batch-size requires --engine rust_full")
    if args.rust_full_rayon_threads is not None:
        if args.rust_full_rayon_threads <= 0:
            parser.error("--rust-full-rayon-threads must be > 0")
        if args.engine != 'rust_full':
            parser.error("--rust-full-rayon-threads requires --engine rust_full")
    if args.parquet_row_group_size is not None and args.parquet_row_group_size <= 0:
        parser.error("--parquet-row-group-size must be > 0")
    if args.parquet_write_batch_size is not None and args.parquet_write_batch_size <= 0:
        parser.error("--parquet-write-batch-size must be > 0")
    if args.parquet_compression is not None:
        try:
            _normalize_parquet_compression(args.parquet_compression)
        except ValueError as exc:
            parser.error(str(exc))

    num_workers = args.workers or max(1, multiprocessing.cpu_count() - 1)

    raw_cli_args = sys.argv[1:]
    explicit_chunk_size = _cli_flag_present(raw_cli_args, '--chunk-size')
    explicit_native_jsonl = args.rust_full_native_jsonl is not None
    explicit_native_parquet = args.rust_full_native_parquet is not None
    explicit_native_parquet_direct = args.rust_full_native_parquet_direct is not None
    explicit_rayon_batch_size = args.rust_full_rayon_batch_size is not None
    explicit_rayon_threads = args.rust_full_rayon_threads is not None
    explicit_parquet_compression = args.parquet_compression is not None
    explicit_parquet_use_dictionary = args.parquet_use_dictionary is not None
    explicit_parquet_write_statistics = args.parquet_write_statistics is not None

    effective_chunk_size = args.chunk_size
    effective_rust_full_native_jsonl = bool(args.rust_full_native_jsonl) if args.rust_full_native_jsonl is not None else False
    effective_rust_full_native_parquet = bool(args.rust_full_native_parquet) if args.rust_full_native_parquet is not None else False
    effective_rust_full_native_parquet_direct = bool(args.rust_full_native_parquet_direct) if args.rust_full_native_parquet_direct is not None else False
    effective_rust_full_rayon_batch_size = args.rust_full_rayon_batch_size
    effective_rust_full_rayon_threads = args.rust_full_rayon_threads
    effective_parquet_compression = args.parquet_compression if args.parquet_compression is not None else 'uncompressed'
    effective_parquet_use_dictionary = bool(args.parquet_use_dictionary) if args.parquet_use_dictionary is not None else False
    effective_parquet_write_statistics = bool(args.parquet_write_statistics) if args.parquet_write_statistics is not None else False
    effective_parquet_row_group_size = args.parquet_row_group_size
    effective_parquet_write_batch_size = args.parquet_write_batch_size
    auto_profile_applied = False

    if args.engine == 'rust_full' and not args.no_rust_full_auto_profile:
        if not explicit_chunk_size and args.chunk_size == 100:
            effective_chunk_size = 1000
            auto_profile_applied = True
        if (
            not args.rust_full_summary_only
            and not args.rust_full_native_jsonl
            and not args.rust_full_native_parquet
            and not explicit_native_jsonl
            and not explicit_native_parquet
        ):
            effective_rust_full_native_parquet = True
            auto_profile_applied = True
        if (
            effective_rust_full_native_parquet
            and not args.rust_full_summary_only
            and not explicit_native_parquet_direct
        ):
            effective_rust_full_native_parquet_direct = True
            auto_profile_applied = True
        if args.rust_full_rayon_batch_size is None and not explicit_rayon_batch_size:
            effective_rust_full_rayon_batch_size = 64
            auto_profile_applied = True
        if args.rust_full_rayon_threads is None and not explicit_rayon_threads:
            effective_rust_full_rayon_threads = num_workers
            auto_profile_applied = True
        if not explicit_parquet_compression:
            effective_parquet_compression = 'snappy'
            auto_profile_applied = True
        if not explicit_parquet_use_dictionary:
            effective_parquet_use_dictionary = True
            auto_profile_applied = True
        if not explicit_parquet_write_statistics:
            effective_parquet_write_statistics = True
            auto_profile_applied = True

    try:
        _normalize_parquet_compression(effective_parquet_compression)
    except ValueError as exc:
        parser.error(str(exc))
    if effective_rust_full_native_parquet_direct and not effective_rust_full_native_parquet:
        parser.error("--rust-full-native-parquet-direct requires --rust-full-native-parquet")
    if effective_rust_full_native_parquet_direct and effective_rust_full_native_jsonl:
        parser.error("--rust-full-native-parquet-direct cannot be combined with --rust-full-native-jsonl")
    if effective_rust_full_native_parquet_direct and args.rust_full_summary_only:
        parser.error("--rust-full-native-parquet-direct requires training rows (do not use --rust-full-summary-only)")
    if effective_rust_full_native_parquet_direct and effective_rust_full_rayon_batch_size is None:
        parser.error("--rust-full-native-parquet-direct requires --rust-full-rayon-batch-size")

    if auto_profile_applied:
        print(
            "Applying rust_full default speed profile: "
            f"chunk_size={effective_chunk_size}, "
            f"native_parquet={effective_rust_full_native_parquet}, "
            f"native_parquet_direct={effective_rust_full_native_parquet_direct}, "
            f"rayon_batch_size={effective_rust_full_rayon_batch_size}, "
            f"rayon_threads={effective_rust_full_rayon_threads}, "
            f"parquet_compression={effective_parquet_compression}, "
            f"parquet_use_dictionary={effective_parquet_use_dictionary}, "
            f"parquet_write_statistics={effective_parquet_write_statistics}, "
            f"parquet_row_group_size={effective_parquet_row_group_size}, "
            f"parquet_write_batch_size={effective_parquet_write_batch_size}"
        )

    if not args.skip_reference_validation:
        try:
            _validate_reference_data_preflight()
        except RuntimeError as exc:
            print(str(exc))
            sys.exit(1)

    # Handle resume mode
    if args.resume:
        output_dir = args.resume
        # Load checkpoint to get original settings
        checkpoint_path = os.path.join(output_dir, 'checkpoint.json')
        if not os.path.exists(checkpoint_path):
            print(f"Error: No checkpoint.json found in {output_dir}")
            sys.exit(1)
        if args.agent_mix:
            agent_mix = _parse_agent_mix(args.agent_mix)
        else:
            profile_mix = AGENT_PROFILES.get(args.agent_profile)
            agent_mix = dict(profile_mix) if profile_mix else None
        summary = run_batch(
            num_games=args.games,
            num_workers=num_workers,
            output_dir=output_dir,
            seed_start=args.seed_start,
            agent_mix=agent_mix,
            chunk_size=effective_chunk_size,
            resume=True,
            agent_profile=args.agent_profile,
            checkpoint_every=args.checkpoint_every,
            progress_every=args.progress_every,
            max_errors=args.max_errors,
            require_parquet=args.require_parquet,
            pool_chunksize=args.pool_chunksize,
            pool_chunksize_max=args.pool_chunksize_max,
            shard_index=args.shard_index,
            num_shards=args.num_shards,
            engine=args.engine,
            rust_full_include_training_rows=not args.rust_full_summary_only,
            rust_full_native_jsonl=effective_rust_full_native_jsonl,
            rust_full_native_parquet=effective_rust_full_native_parquet,
            rust_full_native_parquet_direct=effective_rust_full_native_parquet_direct,
            rust_full_rayon_batch_size=effective_rust_full_rayon_batch_size,
            rust_full_rayon_threads=effective_rust_full_rayon_threads,
            parquet_compression=effective_parquet_compression,
            parquet_use_dictionary=effective_parquet_use_dictionary,
            parquet_write_statistics=effective_parquet_write_statistics,
            parquet_row_group_size=effective_parquet_row_group_size,
            parquet_write_batch_size=effective_parquet_write_batch_size,
        )
    else:
        if args.agent_mix:
            agent_mix = _parse_agent_mix(args.agent_mix)
        else:
            profile_mix = AGENT_PROFILES.get(args.agent_profile)
            agent_mix = dict(profile_mix) if profile_mix else None
        summary = run_batch(
            num_games=args.games,
            num_workers=num_workers,
            output_dir=args.output,
            seed_start=args.seed_start,
            agent_mix=agent_mix,
            chunk_size=effective_chunk_size,
            agent_profile=args.agent_profile,
            checkpoint_every=args.checkpoint_every,
            progress_every=args.progress_every,
            max_errors=args.max_errors,
            require_parquet=args.require_parquet,
            pool_chunksize=args.pool_chunksize,
            pool_chunksize_max=args.pool_chunksize_max,
            shard_index=args.shard_index,
            num_shards=args.num_shards,
            engine=args.engine,
            rust_full_include_training_rows=not args.rust_full_summary_only,
            rust_full_native_jsonl=effective_rust_full_native_jsonl,
            rust_full_native_parquet=effective_rust_full_native_parquet,
            rust_full_native_parquet_direct=effective_rust_full_native_parquet_direct,
            rust_full_rayon_batch_size=effective_rust_full_rayon_batch_size,
            rust_full_rayon_threads=effective_rust_full_rayon_threads,
            parquet_compression=effective_parquet_compression,
            parquet_use_dictionary=effective_parquet_use_dictionary,
            parquet_write_statistics=effective_parquet_write_statistics,
            parquet_row_group_size=effective_parquet_row_group_size,
            parquet_write_batch_size=effective_parquet_write_batch_size,
        )

    print(f"\n{'='*50}")
    print(f"BATCH COMPLETE")
    print(f"{'='*50}")
    print(f"Games:  {summary.get('num_games', 0)}")
    print(f"Errors: {summary.get('num_errors', 0)}")
    print(f"Time:   {summary.get('total_time_sec', 0)}s")
    print(f"Rate:   {summary.get('games_per_sec', 0)} games/sec")
    print(f"Rows:   {summary.get('total_training_rows', 0)}")
    print(f"Chunks: {summary.get('total_chunks', 0)}")

    if summary.get('top_champions'):
        print(f"\nTop 5 champions (avg placement):")
        for name, avg in summary['top_champions'][:5]:
            print(f"  {name}: {avg}")
    if summary.get('bottom_champions'):
        print(f"\nBottom 5 champions (avg placement):")
        for name, avg in summary['bottom_champions'][:5]:
            print(f"  {name}: {avg}")


if __name__ == '__main__':
    main()

