"""Performance benchmark for the TFT combat simulator.

Measures throughput for common simulation workloads:
- 1v1 duels (single champion pairs)
- 4v4 team fights
- 8v8 full team fights
- Batch 1v1 simulations (100+ runs)

Usage:
    python -m simulator.perf_benchmark
"""

import time
from simulator.core.combat_engine import CombatEngine, HexGrid


def benchmark_1v1_duel(engine: CombatEngine, n: int = 500) -> float:
    """Benchmark N 1v1 duels between two champions."""
    start = time.perf_counter()
    for i in range(n):
        u1 = engine.create_unit("TFT16_Draven", 2, (0, 3), 0, ["InfinityEdge"])
        u2 = engine.create_unit("TFT16_Leona", 2, (3, 3), 1, ["WarmogsArmor"])
        engine.run_combat([u1], [u2], seed=i)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_4v4(engine: CombatEngine, n: int = 200) -> float:
    """Benchmark N 4v4 team fights."""
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
        engine.run_combat(team0, team1, seed=i)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_8v8(engine: CombatEngine, n: int = 100) -> float:
    """Benchmark N 8v8 full team fights."""
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
        engine.run_combat(team0, team1, seed=i)
    elapsed = time.perf_counter() - start
    return elapsed


def benchmark_simulate_1v1(engine: CombatEngine) -> float:
    """Benchmark the simulate_1v1 helper (100 sims internally)."""
    start = time.perf_counter()
    engine.simulate_1v1(
        "TFT16_Draven", "TFT16_Leona",
        star1=2, star2=2,
        items1=["InfinityEdge", "LastWhisper"],
        items2=["WarmogsArmor", "BrambleVest"],
        num_simulations=500,
        seed=42,
    )
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    print("=" * 60)
    print("TFT Combat Simulator - Performance Benchmark")
    print("=" * 60)

    # Initialize engine (with logging disabled for perf)
    engine = CombatEngine(logging_enabled=False)
    print(f"Champions loaded: {len(engine.champions)}")
    print()

    # Warmup
    u1 = engine.create_unit("TFT16_Draven", 2, (0, 3), 0)
    u2 = engine.create_unit("TFT16_Leona", 2, (3, 3), 1)
    engine.run_combat([u1], [u2], seed=0)

    # Run benchmarks
    tests = [
        ("1v1 Duel (500 runs)", lambda: benchmark_1v1_duel(engine, 500), 500),
        ("4v4 Team Fight (200 runs)", lambda: benchmark_4v4(engine, 200), 200),
        ("8v8 Full Fight (100 runs)", lambda: benchmark_8v8(engine, 100), 100),
        ("simulate_1v1 (500 internal)", lambda: benchmark_simulate_1v1(engine), 500),
    ]

    for name, fn, count in tests:
        elapsed = fn()
        rate = count / elapsed
        per_sim = elapsed / count * 1000
        print(f"{name}:")
        print(f"  Total: {elapsed:.3f}s | {rate:.1f} sims/sec | {per_sim:.2f} ms/sim")
        print()

    print("=" * 60)
    print("Benchmark complete.")


if __name__ == "__main__":
    main()
