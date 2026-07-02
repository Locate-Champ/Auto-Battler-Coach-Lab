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
import inspect  # noqa: F401 - tests monkeypatch cloud_runner.inspect.signature
import logging
import multiprocessing
import os
import sys
from typing import Dict, List

from simulator._cloud_runner_core import (
    BatchAbort,  # noqa: F401
    BatchRunner,
    BatchRunnerConfig,
    _worker_init,  # noqa: F401
    _worker_parquet_validated,  # noqa: F401
    _worker_sim,  # noqa: F401
    run_game,  # noqa: F401
)
from simulator._cloud_runner_utils import (
    AGENT_PROFILES,
    WILSON_Z_95,  # noqa: F401
    _build_cost_telemetry,  # noqa: F401
    _compute_seed_end,  # noqa: F401
    _ensure_rust_parquet_method_support,  # noqa: F401
    _estimate_worker_cpu_share_pct,  # noqa: F401
    _extract_signature_parameter_names,  # noqa: F401
    _iter_task_batches,  # noqa: F401
    _normalize_parquet_compression,
    _pyarrow_available,  # noqa: F401
    _resolve_shard_range,  # noqa: F401
    _round_or_none,  # noqa: F401
    _rust_extension_rebuild_hint,  # noqa: F401
    _sample_cpu_utilization_pct,  # noqa: F401
    _validate_reference_data_preflight,
    _wilson_interval,  # noqa: F401
)
from simulator._cloud_runner_writer import StreamingWriter  # noqa: F401

# Alias to satisfy roadmap SC1 ("from simulator.cloud_runner import CloudRunner")
CloudRunner = BatchRunner

_log = logging.getLogger(__name__)


# ── CLI ──────────────────────────────────────────────────────────────────


def _parse_agent_mix(s: str) -> Dict[str, int]:
    """Parse agent mix string like 'random:50,econ:30,slam:20'."""
    mix = {}
    for part in s.split(","):
        name, weight = part.strip().split(":")
        name = name.strip()
        if name not in ("random", "econ", "slam"):
            raise ValueError(f"Unknown agent type '{name}'. Valid types: random, econ, slam")
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
        description="Run batch TFT game simulations",
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
    parser.add_argument("--games", type=int, default=10, help="Number of games to simulate")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: min(CPU count - 1, 8))",
    )
    parser.add_argument(
        "--output", type=str, default="results/batch", help="Output directory for results"
    )
    parser.add_argument(
        "--instance-hourly-usd",
        type=float,
        default=0.0,
        help="Hourly instance cost for summary cost telemetry (for example 0.544)",
    )
    parser.add_argument(
        "--instance-type",
        type=str,
        default=None,
        help="Optional instance type label for cost telemetry (for example c7i.2xlarge)",
    )
    parser.add_argument(
        "--seed-start", type=int, default=0, help="Starting seed for deterministic runs"
    )
    parser.add_argument(
        "--agent-mix",
        type=str,
        default=None,
        help='Agent type distribution, e.g. "random:50,econ:30,slam:20"',
    )
    parser.add_argument(
        "--agent-profile",
        type=str,
        default="random",
        choices=sorted(AGENT_PROFILES.keys()),
        help="Preset agent behavior profile used when --agent-mix is not provided",
    )
    parser.add_argument(
        "--chunk-size", type=int, default=100, help="Games per output chunk (controls memory usage)"
    )
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        metavar="DIR",
        help="Resume an interrupted batch from checkpoint in DIR",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=None,
        help="Write checkpoint every N completed tasks",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=500,
        help="Print progress every N completed tasks (default: 500)",
    )
    parser.add_argument(
        "--max-errors", type=int, default=None, help="Stop run early after N game errors"
    )
    parser.add_argument(
        "--require-parquet", action="store_true", help="Fail run if parquet output is unavailable"
    )
    parser.add_argument(
        "--pool-chunksize",
        type=int,
        default=None,
        help="Explicit multiprocessing imap chunk size (default: auto)",
    )
    parser.add_argument(
        "--pool-chunksize-max",
        type=int,
        default=None,
        help="Optional upper bound for multiprocessing imap chunk size",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=None,
        help="Shard index (0-based) when partitioning a run across machines",
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        default=None,
        help="Total number of shards when partitioning a run across machines",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="python",
        choices=["python", "rust", "rust_full"],
        help="Simulation backend (default: python)",
    )
    parser.add_argument(
        "--no-rust-full-auto-profile",
        action="store_true",
        help="Disable rust_full auto-tuned defaults and use explicit/baseline options",
    )
    parser.add_argument(
        "--rust-full-summary-only",
        action="store_true",
        help="Skip training row generation in rust_full mode for max throughput",
    )
    parser.add_argument(
        "--rust-full-native-jsonl",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable Rust-pre-serialized JSONL rows in rust_full mode",
    )
    parser.add_argument(
        "--rust-full-native-parquet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable Rust-pre-serialized parquet rows in rust_full mode",
    )
    parser.add_argument(
        "--rust-full-native-parquet-direct",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable direct Rust chunk parquet file writing in rust_full batch mode",
    )
    parser.add_argument(
        "--rust-full-rayon-batch-size",
        type=int,
        default=None,
        help="Use Rust rayon batch API with this per-call batch size (rust_full only)",
    )
    parser.add_argument(
        "--rust-full-rayon-threads",
        type=int,
        default=None,
        help="Override rayon thread count for rust_full batch API",
    )
    parser.add_argument(
        "--parquet-compression",
        type=str,
        default=None,
        help="Parquet compression codec: uncompressed|snappy|zstd|gzip|brotli|lz4",
    )
    parser.add_argument(
        "--parquet-use-dictionary",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable parquet dictionary encoding for chunk writes",
    )
    parser.add_argument(
        "--parquet-write-statistics",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable parquet column statistics for chunk writes",
    )
    parser.add_argument(
        "--parquet-row-group-size",
        type=int,
        default=None,
        help="Optional parquet row-group size for Rust-native parquet writes",
    )
    parser.add_argument(
        "--parquet-write-batch-size",
        type=int,
        default=None,
        help="Optional parquet write batch size for Rust-native parquet writes",
    )
    parser.add_argument(
        "--s3-uri",
        type=str,
        default=None,
        help="S3 URI to stream chunk uploads as they complete (e.g. s3://bucket/prefix)",
    )
    parser.add_argument(
        "--skip-reference-validation",
        action="store_true",
        help="Skip simulator reference preflight validation",
    )
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
    if args.rust_full_native_jsonl is True and args.engine != "rust_full":
        parser.error("--rust-full-native-jsonl requires --engine rust_full")
    if args.rust_full_native_parquet is True and args.engine != "rust_full":
        parser.error("--rust-full-native-parquet requires --engine rust_full")
    if args.rust_full_native_parquet_direct is True and args.engine != "rust_full":
        parser.error("--rust-full-native-parquet-direct requires --engine rust_full")
    if args.rust_full_native_jsonl is True and args.rust_full_native_parquet is True:
        parser.error("--rust-full-native-jsonl and --rust-full-native-parquet cannot be combined")
    if args.rust_full_native_parquet_direct is True and args.rust_full_native_jsonl is True:
        parser.error(
            "--rust-full-native-parquet-direct cannot be combined with --rust-full-native-jsonl"
        )
    if args.rust_full_rayon_batch_size is not None:
        if args.rust_full_rayon_batch_size <= 0:
            parser.error("--rust-full-rayon-batch-size must be > 0")
        if args.engine != "rust_full":
            parser.error("--rust-full-rayon-batch-size requires --engine rust_full")
    if args.rust_full_rayon_threads is not None:
        if args.rust_full_rayon_threads <= 0:
            parser.error("--rust-full-rayon-threads must be > 0")
        if args.engine != "rust_full":
            parser.error("--rust-full-rayon-threads requires --engine rust_full")
    if args.parquet_row_group_size is not None and args.parquet_row_group_size <= 0:
        parser.error("--parquet-row-group-size must be > 0")
    if args.parquet_write_batch_size is not None and args.parquet_write_batch_size <= 0:
        parser.error("--parquet-write-batch-size must be > 0")
    if args.instance_hourly_usd < 0:
        parser.error("--instance-hourly-usd must be >= 0")
    if args.parquet_compression is not None:
        try:
            _normalize_parquet_compression(args.parquet_compression)
        except ValueError as exc:
            parser.error(str(exc))

    auto_workers = max(1, multiprocessing.cpu_count() - 1)
    if args.workers is None:
        num_workers = min(auto_workers, 8)
        if auto_workers > num_workers:
            print(
                f"Auto-capping workers to {num_workers} "
                f"(detected CPU-derived default {auto_workers})."
            )
    else:
        num_workers = args.workers

    raw_cli_args = sys.argv[1:]
    explicit_chunk_size = _cli_flag_present(raw_cli_args, "--chunk-size")
    explicit_native_jsonl = args.rust_full_native_jsonl is not None
    explicit_native_parquet = args.rust_full_native_parquet is not None
    explicit_native_parquet_direct = args.rust_full_native_parquet_direct is not None
    explicit_rayon_batch_size = args.rust_full_rayon_batch_size is not None
    explicit_rayon_threads = args.rust_full_rayon_threads is not None
    explicit_parquet_compression = args.parquet_compression is not None
    explicit_parquet_use_dictionary = args.parquet_use_dictionary is not None
    explicit_parquet_write_statistics = args.parquet_write_statistics is not None

    effective_chunk_size = args.chunk_size
    effective_rust_full_native_jsonl = (
        bool(args.rust_full_native_jsonl) if args.rust_full_native_jsonl is not None else False
    )
    effective_rust_full_native_parquet = (
        bool(args.rust_full_native_parquet) if args.rust_full_native_parquet is not None else False
    )
    effective_rust_full_native_parquet_direct = (
        bool(args.rust_full_native_parquet_direct)
        if args.rust_full_native_parquet_direct is not None
        else False
    )
    effective_rust_full_rayon_batch_size = args.rust_full_rayon_batch_size
    effective_rust_full_rayon_threads = args.rust_full_rayon_threads
    effective_parquet_compression = (
        args.parquet_compression if args.parquet_compression is not None else "uncompressed"
    )
    effective_parquet_use_dictionary = (
        bool(args.parquet_use_dictionary) if args.parquet_use_dictionary is not None else False
    )
    effective_parquet_write_statistics = (
        bool(args.parquet_write_statistics) if args.parquet_write_statistics is not None else False
    )
    effective_parquet_row_group_size = args.parquet_row_group_size
    effective_parquet_write_batch_size = args.parquet_write_batch_size
    auto_profile_applied = False

    if args.engine == "rust_full" and not args.no_rust_full_auto_profile:
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
            effective_parquet_compression = "snappy"
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
        parser.error(
            "--rust-full-native-parquet-direct cannot be combined with --rust-full-native-jsonl"
        )
    if effective_rust_full_native_parquet_direct and args.rust_full_summary_only:
        parser.error(
            "--rust-full-native-parquet-direct requires training rows (do not use --rust-full-summary-only)"
        )
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
        checkpoint_path = os.path.join(output_dir, "checkpoint.json")
        if not os.path.exists(checkpoint_path):
            print(f"Error: No checkpoint.json found in {output_dir}")
            sys.exit(1)
        if args.agent_mix:
            agent_mix = _parse_agent_mix(args.agent_mix)
        else:
            profile_mix = AGENT_PROFILES.get(args.agent_profile)
            agent_mix = dict(profile_mix) if profile_mix else None
        config = BatchRunnerConfig(
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
            s3_uri=args.s3_uri,
            instance_hourly_usd=args.instance_hourly_usd,
            instance_type=args.instance_type,
        )
        summary = BatchRunner(config).run()
    else:
        if args.agent_mix:
            agent_mix = _parse_agent_mix(args.agent_mix)
        else:
            profile_mix = AGENT_PROFILES.get(args.agent_profile)
            agent_mix = dict(profile_mix) if profile_mix else None
        config = BatchRunnerConfig(
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
            s3_uri=args.s3_uri,
            instance_hourly_usd=args.instance_hourly_usd,
            instance_type=args.instance_type,
        )
        summary = BatchRunner(config).run()

    print(f"\n{'=' * 50}")
    print("BATCH COMPLETE")
    print(f"{'=' * 50}")
    print(f"Games:  {summary.get('num_games', 0)}")
    print(f"Errors: {summary.get('num_errors', 0)}")
    print(f"Time:   {summary.get('total_time_sec', 0)}s")
    print(f"Rate:   {summary.get('games_per_sec', 0)} games/sec")
    print(f"Rounds: {summary.get('total_rounds', 0)}")
    print(f"Rows:   {summary.get('total_training_rows', 0)}")
    print(f"Chunks: {summary.get('total_chunks', 0)}")

    cost_telemetry = summary.get("cost_telemetry") or {}
    throughput = cost_telemetry.get("throughput") or {}
    cpu_util = cost_telemetry.get("cpu_utilization") or {}
    cost = cost_telemetry.get("cost_estimate_usd") or {}
    if throughput:
        print(
            f"Round rate: {throughput.get('rounds_per_sec', 0)} rounds/sec "
            f"({throughput.get('sec_per_round', 0)} sec/round)"
        )
    if cpu_util:
        cpu_avg = cpu_util.get("sampled_avg_pct")
        sampled_part = f", sampled avg={cpu_avg}%" if cpu_avg is not None else ""
        print(
            f"CPU util est: {cpu_util.get('worker_share_pct_est', 0)}% "
            f"(workers={cpu_util.get('num_workers', 0)}/cpu={cpu_util.get('logical_cpu_count', 0)}"
            f"{sampled_part})"
        )
    if cost and float(cost.get("instance_hourly_usd", 0.0) or 0.0) > 0:
        print(
            f"Cost est: ${cost.get('total_cost_usd', 0)} total, "
            f"${cost.get('usd_per_1k_games', 0)} per 1k games, "
            f"${cost.get('usd_per_1k_rounds', 0)} per 1k rounds"
        )

    if summary.get("top_champions"):
        print("\nTop 5 champions (avg placement):")
        for name, avg in summary["top_champions"][:5]:
            print(f"  {name}: {avg}")
    if summary.get("bottom_champions"):
        print("\nBottom 5 champions (avg placement):")
        for name, avg in summary["bottom_champions"][:5]:
            print(f"  {name}: {avg}")


if __name__ == "__main__":
    main()
