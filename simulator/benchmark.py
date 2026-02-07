#!/usr/bin/env python3
"""
TFT Combat Simulator Benchmark & Determinism Tests

This script validates the simulator as a "scientific instrument" before
using it as a "factory" for ML training data.

Tests:
1. Throughput benchmarks (sims/sec)
2. Determinism verification (same seed = same outcome)
3. Memory profiling
"""

import sys
import time
import random
import os
from pathlib import Path

# Add parent directory to path for imports
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from simulator.core.combat_engine import CombatEngine, Unit
from simulator.game.game import TFTGame


def benchmark_1v1(engine: CombatEngine, num_sims: int = 1000) -> dict:
    """Benchmark 1v1 simulation throughput."""
    start = time.perf_counter()

    result = engine.simulate_1v1(
        'TFT16_Draven', 'TFT16_Leona',
        star1=2, star2=2,
        num_simulations=num_sims
    )

    elapsed = time.perf_counter() - start
    return {
        'num_sims': num_sims,
        'elapsed_sec': round(elapsed, 3),
        'sims_per_sec': round(num_sims / elapsed, 1),
        'result': result
    }


def benchmark_team_combat(engine: CombatEngine, num_sims: int = 100) -> dict:
    """Benchmark team vs team combat throughput."""

    # Create sample teams
    def make_team(team_id: int):
        return [
            engine.create_unit('TFT16_Draven', star_level=2, team=team_id, position=(0, 0)),
            engine.create_unit('TFT16_Leona', star_level=2, team=team_id, position=(1, 0)),
            engine.create_unit('TFT16_Lux', star_level=2, team=team_id, position=(2, 0)),
            engine.create_unit('TFT16_Yasuo', star_level=2, team=team_id, position=(3, 0)),
        ]

    start = time.perf_counter()

    for _ in range(num_sims):
        team0 = make_team(0)
        team1 = make_team(1)
        engine.run_combat(team0, team1, verbose=False)

    elapsed = time.perf_counter() - start
    return {
        'num_sims': num_sims,
        'team_size': 4,
        'elapsed_sec': round(elapsed, 3),
        'sims_per_sec': round(num_sims / elapsed, 1),
    }


def test_determinism(engine: CombatEngine, num_runs: int = 100) -> dict:
    """
    Test if the simulator produces identical results with the same seed.

    This is CRITICAL for ML training - non-determinism corrupts training data.
    """
    results = []
    seed = 42

    for i in range(num_runs):
        # Reset RNG with same seed each time
        random.seed(seed)

        # Run same simulation
        result = engine.simulate_1v1(
            'TFT16_Draven', 'TFT16_Leona',
            star1=2, star2=2,
            num_simulations=1  # Single sim to check exact outcome
        )

        # Store key metrics
        results.append({
            'win_rate': result['win_rate'],
            'avg_damage': result['avg_damage'],
            'avg_combat_time': result['avg_combat_time'],
        })

    # Check if all results are identical
    first = results[0]
    all_identical = all(r == first for r in results)

    # Find any differences
    differences = []
    for i, r in enumerate(results):
        if r != first:
            differences.append({
                'run': i,
                'expected': first,
                'got': r
            })

    return {
        'num_runs': num_runs,
        'seed': seed,
        'deterministic': all_identical,
        'num_differences': len(differences),
        'first_difference': differences[0] if differences else None,
        'sample_result': first
    }


def test_determinism_team_combat(engine: CombatEngine, num_runs: int = 50) -> dict:
    """Test determinism for full team combat."""
    results = []
    seed = 12345

    def make_team(team_id: int):
        return [
            engine.create_unit('TFT16_Draven', star_level=2, team=team_id, position=(0, 0)),
            engine.create_unit('TFT16_Leona', star_level=2, team=team_id, position=(1, 0)),
            engine.create_unit('TFT16_Lux', star_level=2, team=team_id, position=(2, 0)),
        ]

    for i in range(num_runs):
        random.seed(seed)

        team0 = make_team(0)
        team1 = make_team(1)
        result = engine.run_combat(team0, team1, verbose=False)

        results.append({
            'winner': result['winner'],
            'combat_time': result['combat_time'],
            'team0_survivors': result['team0_survivors'],
            'team1_survivors': result['team1_survivors'],
            'team0_damage': result['total_damage_dealt']['team0'],
            'team1_damage': result['total_damage_dealt']['team1'],
        })

    first = results[0]
    all_identical = all(r == first for r in results)

    differences = [r for r in results if r != first]

    return {
        'num_runs': num_runs,
        'seed': seed,
        'deterministic': all_identical,
        'num_differences': len(differences),
        'sample_result': first
    }


def benchmark_full_game(num_games: int = 5) -> dict:
    """Benchmark full 8-player game throughput."""
    times = []
    rounds_list = []

    for i in range(num_games):
        start = time.perf_counter()
        game = TFTGame(num_players=8, seed=i, verbose=False)
        placements = game.play()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        rounds_list.append(game.round_num)

    avg_time = sum(times) / len(times)
    avg_rounds = sum(rounds_list) / len(rounds_list)
    return {
        'num_games': num_games,
        'total_sec': round(sum(times), 3),
        'avg_sec_per_game': round(avg_time, 3),
        'min_sec': round(min(times), 3),
        'max_sec': round(max(times), 3),
        'avg_rounds': round(avg_rounds, 1),
        'games_per_hour': round(3600 / avg_time, 0),
    }


def test_determinism_full_game(num_runs: int = 5) -> dict:
    """Test determinism for full 8-player games."""
    results = []
    seed = 99

    for _ in range(num_runs):
        random.seed(seed)
        game = TFTGame(num_players=8, seed=seed, verbose=False)
        placements = game.play()
        results.append({
            'placements': placements,
            'round_num': game.round_num,
        })

    first = results[0]
    all_identical = all(r == first for r in results)
    return {
        'num_runs': num_runs,
        'seed': seed,
        'deterministic': all_identical,
        'num_differences': sum(1 for r in results if r != first),
        'sample_result': first,
    }


def run_full_benchmark():
    """Run all benchmarks and tests."""
    print("=" * 60)
    print("TFT Combat Simulator Benchmark & Validation")
    print("=" * 60)
    print()

    # Initialize engine
    print("Loading combat engine...")
    start = time.perf_counter()
    engine = CombatEngine()
    load_time = time.perf_counter() - start
    print(f"  Engine loaded in {load_time:.2f}s")
    print(f"  Champions: {len(engine.champions)}")
    print(f"  Augments: {len(engine.augment_manager.augment_data) if hasattr(engine, 'augment_manager') else 'N/A'}")
    print()

    # Throughput benchmarks
    print("-" * 60)
    print("THROUGHPUT BENCHMARKS")
    print("-" * 60)

    print("\n1v1 Benchmark (1000 sims)...")
    bench_1v1 = benchmark_1v1(engine, 1000)
    print(f"  Elapsed: {bench_1v1['elapsed_sec']}s")
    print(f"  Throughput: {bench_1v1['sims_per_sec']} sims/sec")

    print("\nTeam Combat Benchmark (100 sims, 4v4)...")
    bench_team = benchmark_team_combat(engine, 100)
    print(f"  Elapsed: {bench_team['elapsed_sec']}s")
    print(f"  Throughput: {bench_team['sims_per_sec']} sims/sec")

    print("\nFull Game Benchmark (5 games, 8 players each)...")
    bench_game = benchmark_full_game(5)
    print(f"  Total: {bench_game['total_sec']}s")
    print(f"  Avg: {bench_game['avg_sec_per_game']}s/game "
          f"(min={bench_game['min_sec']}s, max={bench_game['max_sec']}s)")
    print(f"  Avg rounds: {bench_game['avg_rounds']}")
    print(f"  Throughput: {bench_game['games_per_hour']:.0f} games/hour")

    # Determinism tests
    print()
    print("-" * 60)
    print("DETERMINISM TESTS")
    print("-" * 60)

    print("\n1v1 Determinism (100 runs, same seed)...")
    det_1v1 = test_determinism(engine, 100)
    if det_1v1['deterministic']:
        print(f"  [PASS] - All {det_1v1['num_runs']} runs identical")
    else:
        print(f"  [FAIL] - {det_1v1['num_differences']} runs differed!")
        print(f"  First difference: {det_1v1['first_difference']}")

    print("\nTeam Combat Determinism (50 runs, same seed)...")
    det_team = test_determinism_team_combat(engine, 50)
    if det_team['deterministic']:
        print(f"  [PASS] - All {det_team['num_runs']} runs identical")
    else:
        print(f"  [FAIL] - {det_team['num_differences']} runs differed!")

    print("\nFull Game Determinism (5 runs, same seed)...")
    det_game = test_determinism_full_game(5)
    if det_game['deterministic']:
        print(f"  [PASS] - All {det_game['num_runs']} runs identical")
        print(f"    Placements: {det_game['sample_result']['placements']}")
    else:
        print(f"  [FAIL] - {det_game['num_differences']} runs differed!")

    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Engine load time | {load_time:.3f}s |")
    print(f"| 1v1 throughput | {bench_1v1['sims_per_sec']} sims/sec |")
    print(f"| Team combat throughput | {bench_team['sims_per_sec']} sims/sec |")
    print(f"| 1v1 deterministic | {'Yes' if det_1v1['deterministic'] else 'No'} |")
    print(f"| Team combat deterministic | {'Yes' if det_team['deterministic'] else 'No'} |")
    print(f"| Full game throughput | {bench_game['avg_sec_per_game']}s/game ({bench_game['games_per_hour']:.0f}/hr) |")
    print(f"| Full game deterministic | {'Yes' if det_game['deterministic'] else 'No'} |")
    print()

    # Cost projections
    print("Cost Projections (estimated):")
    sims_per_hour_1v1 = bench_1v1['sims_per_sec'] * 3600
    sims_per_hour_team = bench_team['sims_per_sec'] * 3600
    games_per_hour = bench_game['games_per_hour']
    print(f"  1M 1v1 sims: {1_000_000 / sims_per_hour_1v1:.1f} hours")
    print(f"  1M team sims: {1_000_000 / sims_per_hour_team:.1f} hours")
    print(f"  1M full games (1 core): {1_000_000 / games_per_hour:.1f} hours")
    print(f"  1M full games (32 cores): {1_000_000 / (games_per_hour * 32):.1f} hours")
    print(f"  1M full games (32x32 cluster): {1_000_000 / (games_per_hour * 1024):.2f} hours")
    print()

    return {
        'load_time': load_time,
        'benchmark_1v1': bench_1v1,
        'benchmark_team': bench_team,
        'benchmark_game': bench_game,
        'determinism_1v1': det_1v1,
        'determinism_team': det_team,
        'determinism_game': det_game,
    }


if __name__ == "__main__":
    results = run_full_benchmark()
