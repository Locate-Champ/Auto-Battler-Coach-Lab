"""Cloud runner utility functions and constants.

Standalone helpers used by the writer and core sub-modules.
This is a leaf dependency -- it does NOT import from other _cloud_runner_* modules.
"""

from __future__ import annotations

import inspect
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 95% Wilson interval z-score
WILSON_Z_95 = 1.959963984540054

# Agent profile presets for cloud-scale runs.
# random -> legacy fast_random behavior (no lobby mixing).
AGENT_PROFILES = {
    "random": None,
    "mixed": {"random": 50, "econ": 30, "slam": 20},
    "ladder": {"random": 20, "econ": 45, "slam": 35},
}


def _pyarrow_available() -> bool:
    try:  # pragma: no cover - optional dependency
        import pyarrow  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def _normalize_parquet_compression(name: str) -> str:
    value = name.strip().lower()
    mapping = {
        "uncompressed": "NONE",
        "none": "NONE",
        "snappy": "SNAPPY",
        "gzip": "GZIP",
        "brotli": "BROTLI",
        "lz4": "LZ4",
        "zstd": "ZSTD",
    }
    if value not in mapping:
        valid = ", ".join(sorted(mapping))
        raise ValueError(f"Unsupported parquet compression '{name}'. Valid values: {valid}")
    return mapping[value]


def _rust_extension_rebuild_hint() -> str:
    python_exe = Path(sys.executable)
    cargo_toml = Path(__file__).parent / "core" / "rust_engine" / "Cargo.toml"
    wheel_glob = (
        Path(__file__).parent
        / "core"
        / "rust_engine"
        / "target"
        / "wheels"
        / "tft_combat_engine-*.whl"
    )
    return (
        f'"{python_exe}" -m maturin build --release -m "{cargo_toml}" --interpreter "{python_exe}"\n'
        f'"{python_exe}" -m pip install --force-reinstall "{wheel_glob}"'
    )


def _extract_signature_parameter_names(method: Any) -> List[str]:
    try:
        return list(inspect.signature(method).parameters.keys())
    except (TypeError, ValueError):
        text_sig = getattr(method, "__text_signature__", None) or ""
        if "(" not in text_sig or ")" not in text_sig:
            return []
        inside = text_sig[text_sig.find("(") + 1 : text_sig.rfind(")")]
        names: List[str] = []
        for raw_part in inside.split(","):
            part = raw_part.strip()
            if not part:
                continue
            name = part.split("=")[0].strip()
            if name.startswith("$"):
                name = name[1:]
            names.append(name)
        return names


def _ensure_rust_parquet_method_support(
    rust_simulator: Any,
    method_name: str,
    validated_set: set[str],
    required_kwargs: Tuple[str, ...] = (
        "compression",
        "use_dictionary",
        "write_statistics",
        "row_group_size",
        "write_batch_size",
    ),
) -> None:
    if method_name in validated_set:
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
        missing_text = ", ".join(missing_kwargs)
        raise RuntimeError(
            f"tft_combat_engine.{method_name} is missing expected kwargs ({missing_text}). "
            f"This usually means the extension was built/installed for a different CPython interpreter than "
            f"the one running this command ({sys.executable}). Rebuild/install into this interpreter:\n"
            f"{_rust_extension_rebuild_hint()}"
        )

    validated_set.add(method_name)


def _wilson_interval(successes: int, trials: int, z: float = WILSON_Z_95) -> Tuple[float, float]:
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
    validator = Path(__file__).parent / "data" / "validate_reference_data.py"
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


def _estimate_worker_cpu_share_pct(num_workers: int, logical_cpu_count: int) -> float:
    """Estimate CPU share based on worker count and logical CPUs."""
    if logical_cpu_count <= 0:
        return 0.0
    share = (float(num_workers) / float(logical_cpu_count)) * 100.0
    return max(0.0, min(100.0, share))


def _sample_cpu_utilization_pct(logical_cpu_count: int) -> Optional[float]:
    """Best-effort CPU utilization sample (percent)."""
    try:
        import psutil  # pragma: no cover - optional dependency

        # Small interval avoids the initial 0.0 warm-up sample.
        return float(psutil.cpu_percent(interval=0.1))
    except (ImportError, OSError, RuntimeError):
        pass

    if hasattr(os, "getloadavg"):
        try:
            load_one = float(os.getloadavg()[0])  # pragma: no cover - not on Windows
            if logical_cpu_count <= 0:
                return None
            return max(0.0, min(100.0, (load_one / float(logical_cpu_count)) * 100.0))
        except (OSError, ValueError):
            return None
    return None


def _round_or_none(value: Optional[float], digits: int = 4) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _build_cost_telemetry(
    *,
    total_time_sec: float,
    num_games: int,
    total_rounds: int,
    num_workers: int,
    logical_cpu_count: int,
    instance_hourly_usd: float,
    cpu_utilization_samples_pct: Optional[List[float]] = None,
) -> Dict[str, Any]:
    games_per_sec = (num_games / total_time_sec) if total_time_sec > 0 else 0.0
    rounds_per_sec = (total_rounds / total_time_sec) if total_time_sec > 0 else 0.0
    sec_per_game = (total_time_sec / num_games) if num_games > 0 else 0.0
    sec_per_round = (total_time_sec / total_rounds) if total_rounds > 0 else 0.0

    worker_share_pct_est = _estimate_worker_cpu_share_pct(num_workers, logical_cpu_count)
    samples = [float(v) for v in (cpu_utilization_samples_pct or [])]
    sampled_avg = (sum(samples) / len(samples)) if samples else None
    sampled_min = min(samples) if samples else None
    sampled_max = max(samples) if samples else None

    total_cost_usd = (total_time_sec / 3600.0) * max(0.0, float(instance_hourly_usd))
    usd_per_game = (total_cost_usd / num_games) if num_games > 0 else 0.0
    usd_per_round = (total_cost_usd / total_rounds) if total_rounds > 0 else 0.0

    return {
        "throughput": {
            "games_per_sec": round(games_per_sec, 4),
            "rounds_per_sec": round(rounds_per_sec, 4),
            "sec_per_game": round(sec_per_game, 4),
            "sec_per_round": round(sec_per_round, 4),
        },
        "cpu_utilization": {
            "logical_cpu_count": int(logical_cpu_count),
            "num_workers": int(num_workers),
            "worker_share_pct_est": round(worker_share_pct_est, 2),
            "sample_count": int(len(samples)),
            "sampled_avg_pct": _round_or_none(sampled_avg, 2),
            "sampled_min_pct": _round_or_none(sampled_min, 2),
            "sampled_max_pct": _round_or_none(sampled_max, 2),
        },
        "cost_estimate_usd": {
            "instance_hourly_usd": round(max(0.0, float(instance_hourly_usd)), 6),
            "total_cost_usd": round(total_cost_usd, 6),
            "usd_per_game": round(usd_per_game, 6),
            "usd_per_round": round(usd_per_round, 6),
            "usd_per_1k_games": round(usd_per_game * 1000.0, 6),
            "usd_per_1k_rounds": round(usd_per_round * 1000.0, 6),
        },
    }


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
        yield tasks[start : start + batch_size]
