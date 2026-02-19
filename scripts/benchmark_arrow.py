"""Benchmark Arrow vs Dict data loading at Gate B scale.

Usage:
    python scripts/benchmark_arrow.py --data /path/to/gate_b_50k
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.data_loader import DataLoader  # noqa: E402
from models.feature_engineering import TFTFeatureEngineer  # noqa: E402


def bench_arrow(loader: DataLoader) -> dict:
    """Benchmark Arrow streaming path."""
    t0 = time.perf_counter()
    X_tr, X_te, y_tr, y_te = loader.load_fight_prediction_arrow(
        test_size=0.2,
        seed=42,
    )
    elapsed = time.perf_counter() - t0
    total = len(X_tr) + len(X_te)
    return {
        "path": "arrow",
        "elapsed": elapsed,
        "train_shape": X_tr.shape,
        "test_shape": X_te.shape,
        "total_rows": total,
        "rows_per_sec": total / elapsed,
    }


def bench_dict(loader: DataLoader) -> dict:
    """Benchmark dict-based path."""
    t0 = time.perf_counter()
    X_tr, X_te, y_tr, y_te = loader.load_fight_prediction_data(
        test_size=0.2,
        seed=42,
    )
    elapsed = time.perf_counter() - t0
    total = len(X_tr) + len(X_te)
    return {
        "path": "dict",
        "elapsed": elapsed,
        "train_shape": X_tr.shape,
        "test_shape": X_te.shape,
        "total_rows": total,
        "rows_per_sec": total / elapsed,
    }


def bench_arrow_parallel(data_dir: str, workers: int) -> dict:
    """Benchmark Arrow parallel vectorization path.

    Creates a fresh DataLoader per run to avoid pool caching bug
    (DataLoader._ensure_pool caches the pool on first call).
    """
    fe = TFTFeatureEngineer()
    loader = DataLoader(data_dir, feature_engineer=fe, n_workers=workers)

    t0 = time.perf_counter()
    X = loader.vectorize_arrow_parallel()
    elapsed = time.perf_counter() - t0

    loader.close()
    total = len(X)
    return {
        "path": f"arrow_parallel(w={workers})",
        "elapsed": elapsed,
        "total_rows": total,
        "rows_per_sec": total / elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark Arrow vs Dict loading")
    parser.add_argument("--data", required=True, help="Path to Gate B output dir")
    parser.add_argument("--skip-dict", action="store_true", help="Skip dict benchmark")
    parser.add_argument(
        "--skip-arrow-single", action="store_true", help="Skip Arrow single-process"
    )
    parser.add_argument(
        "--parallel-workers",
        type=int,
        nargs="+",
        default=[4, 8, 16],
        help="Worker counts to test for parallel benchmark",
    )
    args = parser.parse_args()

    print(f"Data: {args.data}")
    parquet_files = sorted(Path(args.data).glob("*.parquet"))
    print(f"Parquet files: {len(parquet_files)}")

    # Check Cython
    try:
        from models.fe_fast import CYTHON_AVAILABLE

        print(f"Cython FE: {CYTHON_AVAILABLE}")
    except ImportError:
        print("Cython FE: not available")

    fe = TFTFeatureEngineer()
    loader = DataLoader(args.data, feature_engineer=fe)
    print()

    results = []

    # Arrow single-process
    if not args.skip_arrow_single:
        print("=" * 60)
        print("Benchmark: Arrow (single-process)")
        print("=" * 60)
        r = bench_arrow(loader)
        results.append(r)
        print(f"  Time:     {r['elapsed']:.1f}s")
        print(f"  Train:    {r['train_shape']}")
        print(f"  Test:     {r['test_shape']}")
        print(f"  Rows/sec: {r['rows_per_sec']:,.0f}")
        print()

    # Arrow parallel (various worker counts)
    for w in args.parallel_workers:
        print("=" * 60)
        print(f"Benchmark: Arrow parallel (workers={w})")
        print("=" * 60)
        r = bench_arrow_parallel(args.data, w)
        results.append(r)
        if "error" in r:
            print(f"  Error: {r['error']}")
        else:
            print(f"  Time:     {r['elapsed']:.1f}s")
            print(f"  Rows:     {r['total_rows']:,}")
            print(f"  Rows/sec: {r['rows_per_sec']:,.0f}")
        print()

    # Dict path
    if not args.skip_dict:
        print("=" * 60)
        print("Benchmark: Dict (single-process)")
        print("=" * 60)
        r = bench_dict(loader)
        results.append(r)
        print(f"  Time:     {r['elapsed']:.1f}s")
        print(f"  Train:    {r['train_shape']}")
        print(f"  Test:     {r['test_shape']}")
        print(f"  Rows/sec: {r['rows_per_sec']:,.0f}")
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        if "error" in r:
            continue
        elapsed = r["elapsed"]
        rps = r["rows_per_sec"]
        print(f"  {r['path']:30s}  {elapsed:8.1f}s  {rps:>10,.0f} rows/sec")

    # Speedup
    arrow_time = next((r["elapsed"] for r in results if r["path"] == "arrow"), None)
    dict_time = next((r["elapsed"] for r in results if r["path"] == "dict"), None)
    if arrow_time and dict_time:
        print(f"\n  Arrow vs Dict speedup: {dict_time / arrow_time:.2f}x")

    best_parallel = min(
        (
            r
            for r in results
            if r["path"].startswith("arrow_parallel") and "error" not in r
        ),
        key=lambda r: r["elapsed"],
        default=None,
    )
    if best_parallel and dict_time:
        print(
            f"  Best parallel vs Dict speedup: {dict_time / best_parallel['elapsed']:.2f}x"
        )
    if best_parallel and arrow_time:
        print(
            f"  Parallel vs Arrow single speedup: {arrow_time / best_parallel['elapsed']:.2f}x"
        )


if __name__ == "__main__":
    main()
