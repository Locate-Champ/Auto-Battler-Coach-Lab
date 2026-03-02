"""Cloud runner core: BatchRunner, BatchRunnerConfig, and worker functions.

One-way dependency: core -> {utils, writer} (never the reverse).
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import random
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from simulator._cloud_runner_utils import (
    _compute_seed_end,
    _ensure_rust_parquet_method_support,
    _estimate_worker_cpu_share_pct,
    _normalize_parquet_compression,
    _pyarrow_available,
    _resolve_shard_range,
    _sample_cpu_utilization_pct,
)
from simulator._cloud_runner_writer import StreamingWriter
from simulator.game.actions import MixedLobbyAgent
from simulator.game.collector import GameCollector
from simulator.game.game import TFTGame

_log = logging.getLogger(__name__)

# Worker-process state (set by Pool initializer, process-local -- NOT shared mutable state)
_worker_sim: Any = None
_worker_parquet_validated: set[str] = set()


@dataclass(frozen=True)
class BatchRunnerConfig:
    """Immutable configuration for a batch simulation run.

    Use dataclasses.replace() for test overrides.
    """

    num_games: int
    num_workers: int
    output_dir: str
    seed_start: int = 0
    agent_mix: Optional[Dict[str, int]] = None
    chunk_size: int = 100
    resume: bool = False
    agent_profile: str = "random"
    checkpoint_every: Optional[int] = None
    progress_every: Optional[int] = 500
    max_errors: Optional[int] = None
    require_parquet: bool = False
    pool_chunksize: Optional[int] = None
    pool_chunksize_max: Optional[int] = None
    shard_index: Optional[int] = None
    num_shards: Optional[int] = None
    engine: str = "python"
    rust_full_include_training_rows: bool = True
    rust_full_native_jsonl: bool = False
    rust_full_native_parquet: bool = False
    rust_full_native_parquet_direct: bool = False
    rust_full_rayon_batch_size: Optional[int] = None
    rust_full_rayon_threads: Optional[int] = None
    parquet_compression: str = "uncompressed"
    parquet_use_dictionary: bool = False
    parquet_write_statistics: bool = False
    parquet_row_group_size: Optional[int] = None
    parquet_write_batch_size: Optional[int] = None
    s3_uri: Optional[str] = None
    instance_hourly_usd: float = 0.0
    instance_type: Optional[str] = None


class BatchAbort(Exception):
    """Raised when a run should stop early while preserving output state."""


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

        if engine == "rust_full":
            global _worker_sim, _worker_parquet_validated
            if _worker_sim is None:
                from tft_combat_engine import RustGameSimulator

                combat_data_path = Path(__file__).parent / "data" / "combat_data.json"
                _worker_sim = RustGameSimulator(str(combat_data_path))
                _worker_parquet_validated = set()

            start = time.perf_counter()
            if rust_full_native_parquet and include_training_rows:
                _ensure_rust_parquet_method_support(
                    _worker_sim, "run_game_parquet", _worker_parquet_validated
                )
                rust_result = _worker_sim.run_game_parquet(
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
                rust_result = _worker_sim.run_game_jsonl(game_id, seed, agent_mix)
            else:
                rust_result = _worker_sim.run_game(
                    game_id,
                    seed,
                    agent_mix,
                    include_training_rows,
                )
            elapsed = time.perf_counter() - start
            analytics = rust_result.get("analytics") or {
                "comp_placements": [],
                "augment_placements": [],
                "champion_placements": [],
            }

            return {
                "status": "ok",
                "game_id": game_id,
                "seed": seed,
                "elapsed": round(elapsed, 3),
                "rounds": int(rust_result.get("rounds", 0)),
                "placements": rust_result.get("placements", []),
                "training_rows": rust_result.get("training_rows", []),
                "training_rows_jsonl": rust_result.get("training_rows_jsonl", ""),
                "training_rows_parquet": rust_result.get("training_rows_parquet", b""),
                "training_row_count": int(rust_result.get("training_row_count", 0)),
                "analytics": analytics,
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
            "status": "ok",
            "game_id": game_id,
            "seed": seed,
            "elapsed": round(elapsed, 3),
            "rounds": game.round_num,
            "placements": collector.placements,
            "training_rows": collector.get_training_rows(),
            "analytics": collector.get_analytics(),
        }
    except (ValueError, KeyError, TypeError, RuntimeError, OSError):
        return {
            "status": "error",
            "game_id": game_id,
            "seed": seed,
            "error": traceback.format_exc(),
        }


# ── Worker Init ──────────────────────────────────────────────────────────


def _worker_init(engine: str = "python"):
    """Worker process initializer - pre-loads shared data."""
    if engine == "rust":
        from tft_combat_engine import RustCombatEngine

        combat_data_path = Path(__file__).parent / "data" / "combat_data.json"
        RustCombatEngine(str(combat_data_path))
        return
    if engine == "rust_full":
        global _worker_sim, _worker_parquet_validated
        from tft_combat_engine import RustGameSimulator

        combat_data_path = Path(__file__).parent / "data" / "combat_data.json"
        _worker_sim = RustGameSimulator(str(combat_data_path))
        _worker_parquet_validated = set()
        return

    from simulator.core.combat_engine import CombatEngine

    CombatEngine()  # Warm the cache


# ── Batch Runner ─────────────────────────────────────────────────────────


class BatchRunner:
    """Runs batch simulations with instance-scoped state.

    Single-use: construct per batch, call run(), discard.
    """

    def __init__(self, config: BatchRunnerConfig) -> None:
        self._config = config
        # Main-process instance state (replaces former module globals):
        self._rust_simulator: Any = None
        self._parquet_api_validated: set[str] = set()

    def _ensure_rust_simulator(self) -> None:
        """Lazily construct the Rust simulator for rayon batch path."""
        if self._rust_simulator is None:
            from tft_combat_engine import RustGameSimulator

            combat_data_path = Path(__file__).parent / "data" / "combat_data.json"
            self._rust_simulator = RustGameSimulator(str(combat_data_path))
            self._parquet_api_validated.clear()

    def run(self) -> Dict:
        """Execute the batch. Returns summary dict."""
        cfg = self._config

        if cfg.pool_chunksize is not None and cfg.pool_chunksize <= 0:
            raise ValueError("pool_chunksize must be > 0 when provided.")
        if cfg.pool_chunksize_max is not None and cfg.pool_chunksize_max <= 0:
            raise ValueError("pool_chunksize_max must be > 0 when provided.")
        if cfg.rust_full_native_jsonl and cfg.engine != "rust_full":
            raise ValueError("rust_full_native_jsonl can only be used with engine='rust_full'.")
        if cfg.rust_full_native_parquet and cfg.engine != "rust_full":
            raise ValueError("rust_full_native_parquet can only be used with engine='rust_full'.")
        if cfg.rust_full_native_parquet_direct and cfg.engine != "rust_full":
            raise ValueError(
                "rust_full_native_parquet_direct can only be used with engine='rust_full'."
            )
        if cfg.rust_full_native_jsonl and cfg.rust_full_native_parquet:
            raise ValueError(
                "rust_full_native_jsonl and rust_full_native_parquet are mutually exclusive."
            )
        if cfg.rust_full_native_parquet_direct and cfg.rust_full_native_jsonl:
            raise ValueError(
                "rust_full_native_parquet_direct cannot be combined with rust_full_native_jsonl."
            )
        if cfg.rust_full_native_parquet_direct and not cfg.rust_full_native_parquet:
            raise ValueError("rust_full_native_parquet_direct requires rust_full_native_parquet.")
        if cfg.rust_full_native_parquet_direct and not cfg.rust_full_include_training_rows:
            raise ValueError(
                "rust_full_native_parquet_direct requires rust_full_include_training_rows."
            )
        if cfg.rust_full_native_parquet_direct and cfg.rust_full_rayon_batch_size is None:
            raise ValueError("rust_full_native_parquet_direct requires rust_full_rayon_batch_size.")
        if cfg.rust_full_rayon_batch_size is not None and cfg.rust_full_rayon_batch_size <= 0:
            raise ValueError("rust_full_rayon_batch_size must be > 0 when provided.")
        if cfg.rust_full_rayon_threads is not None and cfg.rust_full_rayon_threads <= 0:
            raise ValueError("rust_full_rayon_threads must be > 0 when provided.")
        if (
            cfg.rust_full_rayon_batch_size is not None or cfg.rust_full_rayon_threads is not None
        ) and cfg.engine != "rust_full":
            raise ValueError("Rust rayon batch options require engine='rust_full'.")
        if cfg.parquet_row_group_size is not None and cfg.parquet_row_group_size <= 0:
            raise ValueError("parquet_row_group_size must be > 0 when provided.")
        if cfg.parquet_write_batch_size is not None and cfg.parquet_write_batch_size <= 0:
            raise ValueError("parquet_write_batch_size must be > 0 when provided.")
        if cfg.instance_hourly_usd < 0:
            raise ValueError("instance_hourly_usd must be >= 0.")
        _normalize_parquet_compression(cfg.parquet_compression)

        logical_cpu_count = max(1, multiprocessing.cpu_count())
        worker_cpu_share_pct_est = _estimate_worker_cpu_share_pct(
            cfg.num_workers, logical_cpu_count
        )
        cpu_utilization_samples_pct: List[float] = []

        requested_seed_start = cfg.seed_start
        requested_num_games = cfg.num_games
        requested_seed_end = _compute_seed_end(requested_seed_start, requested_num_games)
        effective_seed_start, effective_num_games = _resolve_shard_range(
            seed_start=requested_seed_start,
            num_games=requested_num_games,
            shard_index=cfg.shard_index,
            num_shards=cfg.num_shards,
        )
        effective_seed_end = _compute_seed_end(effective_seed_start, effective_num_games)

        # Load checkpoint if resuming
        resume_state = None
        completed_seeds = set()
        if cfg.resume:
            checkpoint_path = os.path.join(cfg.output_dir, "checkpoint.json")
            if os.path.exists(checkpoint_path):
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    resume_state = json.load(f)
                completed_seeds = set(resume_state.get("completed_seeds", []))
                _log.info("Resuming from checkpoint: %d games already done", len(completed_seeds))
            else:
                _log.info("No checkpoint found, starting fresh")

        if cfg.require_parquet and not _pyarrow_available():
            raise RuntimeError(
                "require_parquet was set but pyarrow is unavailable. "
                "Install pyarrow or remove --require-parquet."
            )

        os.makedirs(cfg.output_dir, exist_ok=True)
        writer = StreamingWriter(
            cfg.output_dir,
            chunk_size=cfg.chunk_size,
            resume_state=resume_state,
            require_parquet=cfg.require_parquet,
            parquet_compression=cfg.parquet_compression,
            parquet_use_dictionary=cfg.parquet_use_dictionary,
            parquet_write_statistics=cfg.parquet_write_statistics,
            s3_uri=cfg.s3_uri,
        )

        # Build task list, skipping completed seeds
        all_seeds = [effective_seed_start + i for i in range(effective_num_games)]
        tasks = [
            (
                s,
                s,
                cfg.agent_mix,
                cfg.engine,
                cfg.rust_full_include_training_rows,
                cfg.rust_full_native_jsonl,
                cfg.rust_full_native_parquet,
                cfg.parquet_compression,
                cfg.parquet_use_dictionary,
                cfg.parquet_write_statistics,
                cfg.parquet_row_group_size,
                cfg.parquet_write_batch_size,
            )
            for s in all_seeds
            if s not in completed_seeds
        ]
        remaining = len(tasks)

        resolved_pool_chunksize: Optional[int] = None
        if cfg.num_workers > 1 and remaining > 0:
            default_pool_chunksize = max(1, remaining // (cfg.num_workers * 4))
            resolved_pool_chunksize = cfg.pool_chunksize or default_pool_chunksize
            if cfg.pool_chunksize_max is not None:
                resolved_pool_chunksize = min(resolved_pool_chunksize, cfg.pool_chunksize_max)
            resolved_pool_chunksize = min(resolved_pool_chunksize, remaining)

        use_rust_rayon_batches = (
            cfg.engine == "rust_full" and cfg.rust_full_rayon_batch_size is not None
        )
        use_rust_batch_parquet_api = (
            use_rust_rayon_batches
            and cfg.rust_full_include_training_rows
            and cfg.rust_full_native_parquet
        )
        use_rust_batch_parquet_file_api = (
            use_rust_batch_parquet_api and cfg.rust_full_native_parquet_direct
        )

        if remaining == 0:
            _log.info("All games already completed!")
            return writer.finalize(
                0.0,
                cfg.num_workers,
                run_metadata={
                    "seed_start": effective_seed_start,
                    "seed_end": effective_seed_end,
                    "effective_seed_start": effective_seed_start,
                    "effective_seed_end": effective_seed_end,
                    "requested_seed_start": requested_seed_start,
                    "requested_seed_end": requested_seed_end,
                    "requested_num_games": requested_num_games,
                    "effective_num_games": effective_num_games,
                    "agent_profile": cfg.agent_profile,
                    "agent_mix": cfg.agent_mix if cfg.agent_mix else {"random": 100},
                    "chunk_size": cfg.chunk_size,
                    "pool_chunksize": resolved_pool_chunksize,
                    "pool_chunksize_max": cfg.pool_chunksize_max,
                    "shard_index": cfg.shard_index,
                    "num_shards": cfg.num_shards,
                    "engine": cfg.engine,
                    "rust_full_include_training_rows": cfg.rust_full_include_training_rows,
                    "rust_full_native_jsonl": cfg.rust_full_native_jsonl,
                    "rust_full_native_parquet": cfg.rust_full_native_parquet,
                    "rust_full_native_parquet_direct": cfg.rust_full_native_parquet_direct,
                    "rust_full_rayon_batch_size": cfg.rust_full_rayon_batch_size,
                    "rust_full_rayon_threads": cfg.rust_full_rayon_threads,
                    "rust_full_batch_parquet_api": use_rust_batch_parquet_api,
                    "rust_full_batch_parquet_file_api": use_rust_batch_parquet_file_api,
                    "parquet_compression": cfg.parquet_compression,
                    "parquet_use_dictionary": cfg.parquet_use_dictionary,
                    "parquet_write_statistics": cfg.parquet_write_statistics,
                    "parquet_row_group_size": cfg.parquet_row_group_size,
                    "parquet_write_batch_size": cfg.parquet_write_batch_size,
                    "resume": cfg.resume,
                    "checkpoint_every": cfg.checkpoint_every,
                    "progress_every": cfg.progress_every,
                    "max_errors": cfg.max_errors,
                    "require_parquet": cfg.require_parquet,
                    "s3_uri": cfg.s3_uri,
                    "instance_hourly_usd": cfg.instance_hourly_usd,
                    "instance_type": cfg.instance_type,
                    "logical_cpu_count": logical_cpu_count,
                    "worker_cpu_share_pct_est": worker_cpu_share_pct_est,
                    "cpu_utilization_samples_pct": cpu_utilization_samples_pct,
                    "aborted": False,
                    "aborted_reason": None,
                },
            )

        agent_desc = "default (fast_random)" if not cfg.agent_mix else str(cfg.agent_mix)
        _log.info(
            "Running %d games across %d workers (chunk_size=%d)",
            remaining,
            cfg.num_workers,
            cfg.chunk_size,
        )
        if effective_seed_end is None:
            seed_span = "none"
        else:
            seed_span = "%d to %d" % (effective_seed_start, effective_seed_end)
        _log.info("Seeds: %s (%d already done)", seed_span, len(completed_seeds))
        if cfg.num_shards is not None and cfg.shard_index is not None:
            _log.info(
                "Shard: %d/%d (requested_games=%d, shard_games=%d)",
                cfg.shard_index + 1,
                cfg.num_shards,
                requested_num_games,
                effective_num_games,
            )
        if resolved_pool_chunksize is not None:
            cap_str = "" if cfg.pool_chunksize_max is None else " (cap=%d)" % cfg.pool_chunksize_max
            _log.info("Pool chunksize: %d%s", resolved_pool_chunksize, cap_str)
        _log.info("Agents: %s", agent_desc)
        _log.info("Engine: %s", cfg.engine)
        _log.info("Output: %s", cfg.output_dir)
        if cfg.s3_uri:
            _log.info("S3:     %s (streaming upload)", cfg.s3_uri)

        start = time.perf_counter()
        checkpoint_interval = (
            cfg.checkpoint_every
            if cfg.checkpoint_every and cfg.checkpoint_every > 0
            else max(1, remaining // 20)
        )
        progress_interval = (
            cfg.progress_every if cfg.progress_every and cfg.progress_every > 0 else 500
        )
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
                cpu_pct = _sample_cpu_utilization_pct(logical_cpu_count)
                cpu_str = ""
                if cpu_pct is not None:
                    cpu_utilization_samples_pct.append(cpu_pct)
                    cpu_str = ", cpu=%.1f%%" % cpu_pct
                err_str = ", %d errors" % writer.num_errors if writer.num_errors else ""
                _log.info(
                    "  [%d/%d] %.1f games/sec, ETA: %.0fs%s%s",
                    done,
                    remaining,
                    rate,
                    eta,
                    cpu_str,
                    err_str,
                )

            if cfg.max_errors is not None and writer.num_errors >= cfg.max_errors:
                raise BatchAbort(
                    f"Reached max error threshold ({writer.num_errors}/{cfg.max_errors})."
                )

            if done % checkpoint_interval == 0:
                writer.write_checkpoint()

        if use_rust_rayon_batches:
            self._ensure_rust_simulator()
            rayon_threads = cfg.rust_full_rayon_threads or cfg.num_workers
            if use_rust_batch_parquet_file_api:
                _ensure_rust_parquet_method_support(
                    self._rust_simulator,
                    "run_games_batch_parquet_to_file",
                    self._parquet_api_validated,
                )
            if use_rust_batch_parquet_api:
                _ensure_rust_parquet_method_support(
                    self._rust_simulator,
                    "run_games_batch_parquet",
                    self._parquet_api_validated,
                )
            batch_output_mode = "rows"
            if cfg.rust_full_include_training_rows and not use_rust_batch_parquet_api:
                if cfg.rust_full_native_parquet:
                    batch_output_mode = "parquet"
                elif cfg.rust_full_native_jsonl:
                    batch_output_mode = "jsonl"
            _log.info(
                "Rust rayon batch mode: batch_size=%s, threads=%d, "
                "output_mode=%s, batch_parquet_api=%s, batch_parquet_file_api=%s",
                cfg.rust_full_rayon_batch_size,
                rayon_threads,
                batch_output_mode,
                use_rust_batch_parquet_api,
                use_rust_batch_parquet_file_api,
            )

            try:
                task_cursor = 0
                while task_cursor < len(tasks):
                    next_batch_size = cfg.rust_full_rayon_batch_size
                    if use_rust_batch_parquet_file_api:
                        # In direct-file mode, each Rust batch call writes one chunk file.
                        next_batch_size = min(cfg.chunk_size, len(tasks) - task_cursor)
                    elif use_rust_batch_parquet_api:
                        games_until_chunk_flush = max(1, cfg.chunk_size - writer.games_in_buffer)
                        next_batch_size = min(next_batch_size, games_until_chunk_flush)
                    task_batch = tasks[task_cursor : task_cursor + next_batch_size]
                    task_cursor += len(task_batch)
                    batch_game_ids = [task[0] for task in task_batch]
                    batch_seeds = [task[1] for task in task_batch]
                    batch_wrote_parquet = False
                    batch_training_row_count = 0
                    try:
                        if use_rust_batch_parquet_file_api:
                            chunk_name = writer.next_chunk_name
                            chunk_path = os.path.join(cfg.output_dir, chunk_name + ".parquet")
                            batch_payload = self._rust_simulator.run_games_batch_parquet_to_file(
                                batch_game_ids,
                                batch_seeds,
                                chunk_path,
                                cfg.agent_mix,
                                cfg.rust_full_include_training_rows,
                                rayon_threads,
                                compression=cfg.parquet_compression,
                                use_dictionary=cfg.parquet_use_dictionary,
                                write_statistics=cfg.parquet_write_statistics,
                                row_group_size=cfg.parquet_row_group_size,
                                write_batch_size=cfg.parquet_write_batch_size,
                            )
                            batch_results = list(batch_payload.get("results", []))
                            batch_training_row_count = int(
                                batch_payload.get("training_row_count", 0)
                            )
                            batch_wrote_parquet = bool(batch_payload.get("wrote_parquet", False))
                        elif use_rust_batch_parquet_api:
                            batch_payload = self._rust_simulator.run_games_batch_parquet(
                                batch_game_ids,
                                batch_seeds,
                                cfg.agent_mix,
                                cfg.rust_full_include_training_rows,
                                rayon_threads,
                                compression=cfg.parquet_compression,
                                use_dictionary=cfg.parquet_use_dictionary,
                                write_statistics=cfg.parquet_write_statistics,
                                row_group_size=cfg.parquet_row_group_size,
                                write_batch_size=cfg.parquet_write_batch_size,
                            )
                            batch_results = list(batch_payload.get("results", []))
                            batch_parquet_blob = batch_payload.get("training_rows_parquet", b"")
                            batch_training_row_count = int(
                                batch_payload.get("training_row_count", 0)
                            )
                            if batch_parquet_blob:
                                for result in batch_results:
                                    if result.get("status") == "ok":
                                        result["training_rows_parquet"] = batch_parquet_blob
                                        result["training_row_count"] = batch_training_row_count
                                        break
                        else:
                            batch_results = self._rust_simulator.run_games_batch(
                                batch_game_ids,
                                batch_seeds,
                                cfg.agent_mix,
                                cfg.rust_full_include_training_rows,
                                batch_output_mode,
                                rayon_threads,
                            )
                    except (RuntimeError, ValueError, OSError):
                        error_text = traceback.format_exc()
                        batch_results = [
                            {
                                "status": "error",
                                "game_id": game_id,
                                "seed": seed,
                                "error": error_text,
                            }
                            for game_id, seed in zip(batch_game_ids, batch_seeds, strict=True)
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
        elif cfg.num_workers <= 1:
            # Sequential mode
            _worker_init(cfg.engine)
            try:
                for task in tasks:
                    result = run_game(task)
                    _process_result(result)
            except BatchAbort as exc:
                aborted_reason = str(exc)
        else:
            # Parallel mode
            ctx = multiprocessing.get_context("spawn")
            with ctx.Pool(
                cfg.num_workers,
                initializer=_worker_init,
                initargs=(cfg.engine,),
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
            _log.warning("Run aborted early: %s", aborted_reason)
            _log.warning("Processed %d/%d tasks before stop.", done, remaining)
        else:
            _log.info(
                "All %d games completed in %.1fs (%.1f games/sec)",
                remaining,
                total_time,
                remaining / total_time if total_time > 0 else 0,
            )
        if writer.num_errors:
            _log.warning("  %d games failed (see errors.json)", writer.num_errors)

        writer.write_checkpoint()
        _log.info("Writing final results...")
        summary = writer.finalize(
            total_time,
            cfg.num_workers,
            run_metadata={
                "seed_start": effective_seed_start,
                "seed_end": effective_seed_end,
                "effective_seed_start": effective_seed_start,
                "effective_seed_end": effective_seed_end,
                "requested_seed_start": requested_seed_start,
                "requested_seed_end": requested_seed_end,
                "requested_num_games": requested_num_games,
                "effective_num_games": effective_num_games,
                "agent_profile": cfg.agent_profile,
                "agent_mix": cfg.agent_mix if cfg.agent_mix else {"random": 100},
                "chunk_size": cfg.chunk_size,
                "pool_chunksize": resolved_pool_chunksize,
                "pool_chunksize_max": cfg.pool_chunksize_max,
                "shard_index": cfg.shard_index,
                "num_shards": cfg.num_shards,
                "engine": cfg.engine,
                "rust_full_include_training_rows": cfg.rust_full_include_training_rows,
                "rust_full_native_jsonl": cfg.rust_full_native_jsonl,
                "rust_full_native_parquet": cfg.rust_full_native_parquet,
                "rust_full_native_parquet_direct": cfg.rust_full_native_parquet_direct,
                "rust_full_rayon_batch_size": cfg.rust_full_rayon_batch_size,
                "rust_full_rayon_threads": cfg.rust_full_rayon_threads,
                "rust_full_batch_parquet_api": use_rust_batch_parquet_api,
                "rust_full_batch_parquet_file_api": use_rust_batch_parquet_file_api,
                "parquet_compression": cfg.parquet_compression,
                "parquet_use_dictionary": cfg.parquet_use_dictionary,
                "parquet_write_statistics": cfg.parquet_write_statistics,
                "parquet_row_group_size": cfg.parquet_row_group_size,
                "parquet_write_batch_size": cfg.parquet_write_batch_size,
                "resume": cfg.resume,
                "checkpoint_every": checkpoint_interval,
                "progress_every": progress_interval,
                "max_errors": cfg.max_errors,
                "require_parquet": cfg.require_parquet,
                "s3_uri": cfg.s3_uri,
                "instance_hourly_usd": cfg.instance_hourly_usd,
                "instance_type": cfg.instance_type,
                "logical_cpu_count": logical_cpu_count,
                "worker_cpu_share_pct_est": worker_cpu_share_pct_est,
                "cpu_utilization_samples_pct": cpu_utilization_samples_pct,
                "aborted": bool(aborted_reason),
                "aborted_reason": aborted_reason,
            },
        )
        return summary
