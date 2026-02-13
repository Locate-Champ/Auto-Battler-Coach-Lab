"""Performance benchmark for the TFT combat simulator.

Measures throughput for common simulation workloads across all engine modes:
- Standard Python engine (run_combat)
- Adaptive tick skipping (run_combat_adaptive_tick)
- Cython-accelerated damage math
- Multiprocessing batch simulation

Usage:
    python -m simulator.perf_benchmark
"""

import time
import multiprocessing as mp
from simulator.core.combat_engine import CombatEngine, HexGrid


def benchmark_1v1_duel(engine: CombatEngine, n: int = 500, fast: bool = False) -> float:
    """Benchmark N 1v1 duels between two champions."""
    run = engine.run_combat_adaptive_tick if fast else engine.run_combat
    start = time.perf_counter()
    for i in range(n):
        u1 = engine.create_unit("TFT16_Draven", 2, (0, 3), 0, ["InfinityEdge"])
        u2 = engine.create_unit("TFT16_Leona", 2, (3, 3), 1, ["WarmogsArmor"])
        run([u1], [u2], seed=i)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_4v4(engine: CombatEngine, n: int = 200, fast: bool = False) -> float:
    """Benchmark N 4v4 team fights."""
    run = engine.run_combat_adaptive_tick if fast else engine.run_combat
    start = time.perf_counter()
    for i in range(n):
        team0 = [
            engine.create_unit("TFT16_Jinx", 2, (0, 2), 0, ["InfinityEdge"]),
            engine.create_unit("TFT16_Lux", 2, (0, 4), 0, ["RabadonsDeathcap"]),
            engine.create_unit("TFT16_Leona", 2, (1, 3), 0, ["WarmogsArmor"]),
            engine.create_unit("TFT16_Renekton", 2, (1, 2), 0, ["BrambleVest"]),
        ]
        team1 = [
            engine.create_unit("TFT16_Draven", 2, (3, 4), 1, ["Bloodthirster"]),
            engine.create_unit("TFT16_Ahri", 2, (3, 2), 1, ["SpearOfShojin"]),
            engine.create_unit("TFT16_Braum", 2, (2, 3), 1, ["GargoyleStoneplate"]),
            engine.create_unit("TFT16_Ekko", 2, (2, 4), 1, ["LastWhisper"]),
        ]
        run(team0, team1, seed=i)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_8v8(engine: CombatEngine, n: int = 100, fast: bool = False) -> float:
    """Benchmark N 8v8 full team fights."""
    run = engine.run_combat_adaptive_tick if fast else engine.run_combat
    champs_t0 = [
        ("TFT16_Jinx", (0, 2), ["InfinityEdge"]),
        ("TFT16_Lux", (0, 4), ["RabadonsDeathcap"]),
        ("TFT16_Leona", (1, 3), ["WarmogsArmor"]),
        ("TFT16_Renekton", (1, 2), ["BrambleVest"]),
        ("TFT16_Ahri", (0, 6), []),
        ("TFT16_Braum", (1, 5), []),
        ("TFT16_Caitlyn", (0, 0), []),
        ("TFT16_Ekko", (1, 0), []),
    ]
    champs_t1 = [
        ("TFT16_Draven", (3, 4), ["Bloodthirster"]),
        ("TFT16_Kaisa", (3, 2), ["SpearOfShojin"]),
        ("TFT16_Nautilus", (2, 3), ["GargoyleStoneplate"]),
        ("TFT16_Darius", (2, 4), ["LastWhisper"]),
        ("TFT16_Lissandra", (3, 6), []),
        ("TFT16_Shen", (2, 5), []),
        ("TFT16_Tristana", (3, 0), []),
        ("TFT16_Yone", (2, 0), []),
    ]
    start = time.perf_counter()
    for i in range(n):
        team0 = [engine.create_unit(c, 2, p, 0, it) for c, p, it in champs_t0]
        team1 = [engine.create_unit(c, 2, p, 1, it) for c, p, it in champs_t1]
        run(team0, team1, seed=i)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_batch_multiprocess(n: int = 1000, workers: int = None) -> float:
    """Benchmark parallel 1v1 via multiprocessing."""
    from simulator.core.batch_simulator import batch_simulate_1v1
    if workers is None:
        workers = mp.cpu_count()
    start = time.perf_counter()
    batch_simulate_1v1(
        "TFT16_Draven", "TFT16_Leona",
        star1=2, star2=2,
        items1=["InfinityEdge", "LastWhisper"],
        items2=["WarmogsArmor", "BrambleVest"],
        num_simulations=n, workers=workers, seed=42,
        use_fast=True,
    )
    elapsed = time.perf_counter() - start
    return elapsed


def _print_result(name, elapsed, count):
    rate = count / elapsed
    per_sim = elapsed / count * 1000
    print(f"  {name:40s}  {elapsed:7.3f}s  {rate:8.1f}/s  {per_sim:6.2f}ms/sim")


def main():
    print("=" * 78)
    print("TFT Combat Simulator - Performance Benchmark")
    print("=" * 78)

    # Check Cython availability
    try:
        from simulator.core.combat_fast import CYTHON_AVAILABLE
        cython_status = "YES" if CYTHON_AVAILABLE else "NO (not built)"
    except ImportError:
        cython_status = "NO (not installed)"
        CYTHON_AVAILABLE = False

    # Check Rust availability
    try:
        from tft_combat_engine import RustCombatEngine
        rust_status = "YES"
    except ImportError:
        rust_status = "NO (not built)"

    engine = CombatEngine(logging_enabled=False)
    print(f"Champions loaded: {len(engine.champions)}")
    print(f"Cython accel:     {cython_status}")
    print(f"Rust engine:      {rust_status}")
    print(f"CPU cores:        {mp.cpu_count()}")
    print()

    # Warmup
    u1 = engine.create_unit("TFT16_Draven", 2, (0, 3), 0)
    u2 = engine.create_unit("TFT16_Leona", 2, (3, 3), 1)
    engine.run_combat([u1], [u2], seed=0)
    engine.run_combat_adaptive_tick([u1], [u2], seed=0)

    n1v1, n4v4, n8v8 = 500, 200, 100

    # Standard engine
    print(f"{'Test':42s}  {'Time':>7s}  {'Rate':>8s}  {'Per sim':>10s}")
    print("-" * 78)

    t = benchmark_1v1_duel(engine, n1v1, fast=False)
    _print_result(f"1v1 standard ({n1v1})", t, n1v1)

    t = benchmark_1v1_duel(engine, n1v1, fast=True)
    _print_result(f"1v1 adaptive-tick ({n1v1})", t, n1v1)

    t = benchmark_4v4(engine, n4v4, fast=False)
    _print_result(f"4v4 standard ({n4v4})", t, n4v4)

    t = benchmark_4v4(engine, n4v4, fast=True)
    _print_result(f"4v4 adaptive-tick ({n4v4})", t, n4v4)

    t = benchmark_8v8(engine, n8v8, fast=False)
    _print_result(f"8v8 standard ({n8v8})", t, n8v8)

    t = benchmark_8v8(engine, n8v8, fast=True)
    _print_result(f"8v8 adaptive-tick ({n8v8})", t, n8v8)

    print()
    print("--- Multiprocessing Batch ---")
    workers = mp.cpu_count()
    n_batch = 1000

    t = benchmark_batch_multiprocess(n_batch, workers=1)
    _print_result(f"batch 1v1 x{n_batch} (1 worker, fast)", t, n_batch)

    if workers > 1:
        t = benchmark_batch_multiprocess(n_batch, workers=workers)
        _print_result(f"batch 1v1 x{n_batch} ({workers} workers, fast)", t, n_batch)

    print()
    print("=" * 78)
    print("Benchmark complete.")


if __name__ == "__main__":
    main()
