#!/usr/bin/env python3
"""
TFT Combat Simulator Benchmark & Determinism Tests.

Validates combat throughput and determinism, and can run Phase 6
cross-engine statistical checks.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add parent directory to path for imports
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from simulator.core.combat_engine import CombatEngine
from simulator.game.game import TFTGame


def _create_engine(engine_name: str) -> Any:
    if engine_name in ('rust', 'rust_full'):
        try:
            from tft_combat_engine import RustCombatEngine
        except Exception as exc:
            raise RuntimeError(
                "Rust engine requested but tft_combat_engine is unavailable. "
                "Build/install simulator/core/rust_engine via maturin first."
            ) from exc
        combat_data_path = Path(__file__).parent / 'data' / 'combat_data.json'
        return RustCombatEngine(str(combat_data_path))

    if engine_name != 'python':
        raise ValueError(f"Unknown engine '{engine_name}'")
    return CombatEngine()


def _engine_champion_count(engine: Any, engine_name: str) -> int:
    if engine_name in ('rust', 'rust_full'):
        return int(engine.num_champions())
    return len(engine.champions)


def _build_unit(
    engine: Any,
    engine_name: str,
    api_name: str,
    team: int,
    position: Tuple[int, int],
    star_level: int = 2,
) -> Any:
    if engine_name in ('rust', 'rust_full'):
        return {
            'api_name': api_name,
            'star_level': star_level,
            'position': [position[0], position[1]],
            'team': team,
            'items': [],
            'traits': [],
        }
    return engine.create_unit(api_name, star_level=star_level, team=team, position=position)


def _build_duel_teams(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [_build_unit(engine, engine_name, 'TFT16_Draven', 0, (0, 3))]
    team1 = [_build_unit(engine, engine_name, 'TFT16_Leona', 1, (3, 3))]
    return team0, team1


def _build_teamfight_teams(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [
        _build_unit(engine, engine_name, 'TFT16_Draven', 0, (0, 0)),
        _build_unit(engine, engine_name, 'TFT16_Leona', 0, (1, 0)),
        _build_unit(engine, engine_name, 'TFT16_Lux', 0, (2, 0)),
        _build_unit(engine, engine_name, 'TFT16_Yasuo', 0, (3, 0)),
    ]
    team1 = [
        _build_unit(engine, engine_name, 'TFT16_Draven', 1, (3, 6)),
        _build_unit(engine, engine_name, 'TFT16_Leona', 1, (2, 6)),
        _build_unit(engine, engine_name, 'TFT16_Lux', 1, (1, 6)),
        _build_unit(engine, engine_name, 'TFT16_Yasuo', 1, (0, 6)),
    ]
    return team0, team1


def _run_combat(engine: Any, engine_name: str, team0: List[Any], team1: List[Any], seed: int) -> Dict[str, Any]:
    if engine_name in ('rust', 'rust_full'):
        return engine.run_combat(team0, team1, seed=seed)
    return engine.run_combat(team0, team1, verbose=False, seed=seed)


def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    damage_map = result.get('total_damage_dealt', {}) or {}
    team0_damage = result.get('team0_total_damage', damage_map.get('team0', 0.0))
    team1_damage = result.get('team1_total_damage', damage_map.get('team1', 0.0))
    return {
        'winner': int(result.get('winner', -1)),
        'combat_time': round(float(result.get('combat_time', 0.0)), 6),
        'team0_survivors': int(result.get('team0_survivors', 0)),
        'team1_survivors': int(result.get('team1_survivors', 0)),
        'team0_damage': round(float(team0_damage), 6),
        'team1_damage': round(float(team1_damage), 6),
    }


def benchmark_1v1(engine: Any, engine_name: str, num_sims: int = 1000) -> dict:
    """Benchmark 1v1 simulation throughput."""
    team0_wins = 0
    team1_wins = 0
    draws = 0
    total_damage = 0.0
    total_time = 0.0

    start = time.perf_counter()
    for i in range(num_sims):
        team0, team1 = _build_duel_teams(engine, engine_name)
        result = _normalize_result(_run_combat(engine, engine_name, team0, team1, seed=1_000_000 + i))
        if result['winner'] == 0:
            team0_wins += 1
        elif result['winner'] == 1:
            team1_wins += 1
        else:
            draws += 1
        total_damage += result['team0_damage'] + result['team1_damage']
        total_time += result['combat_time']

    elapsed = time.perf_counter() - start
    return {
        'num_sims': num_sims,
        'elapsed_sec': round(elapsed, 3),
        'sims_per_sec': round(num_sims / elapsed, 1),
        'result': {
            'team0_win_rate': round(team0_wins / max(1, num_sims), 4),
            'team1_win_rate': round(team1_wins / max(1, num_sims), 4),
            'draw_rate': round(draws / max(1, num_sims), 4),
            'avg_total_damage': round(total_damage / max(1, num_sims), 2),
            'avg_combat_time': round(total_time / max(1, num_sims), 3),
        },
    }


def benchmark_team_combat(engine: Any, engine_name: str, num_sims: int = 100) -> dict:
    """Benchmark team vs team combat throughput."""
    start = time.perf_counter()
    for i in range(num_sims):
        team0, team1 = _build_teamfight_teams(engine, engine_name)
        _run_combat(engine, engine_name, team0, team1, seed=2_000_000 + i)

    elapsed = time.perf_counter() - start
    return {
        'num_sims': num_sims,
        'team_size': 4,
        'elapsed_sec': round(elapsed, 3),
        'sims_per_sec': round(num_sims / elapsed, 1),
    }


def test_determinism(engine: Any, engine_name: str, num_runs: int = 100) -> dict:
    """Test deterministic 1v1 combat (same seed should produce same result)."""
    results = []
    seed = 42

    for _ in range(num_runs):
        random.seed(seed)
        team0, team1 = _build_duel_teams(engine, engine_name)
        result = _normalize_result(_run_combat(engine, engine_name, team0, team1, seed=seed))
        results.append(result)

    first = results[0]
    all_identical = all(r == first for r in results)
    differences = []
    for i, r in enumerate(results):
        if r != first:
            differences.append({'run': i, 'expected': first, 'got': r})

    return {
        'num_runs': num_runs,
        'seed': seed,
        'deterministic': all_identical,
        'num_differences': len(differences),
        'first_difference': differences[0] if differences else None,
        'sample_result': first,
    }


def test_determinism_team_combat(engine: Any, engine_name: str, num_runs: int = 50) -> dict:
    """Test determinism for full team combat."""
    results = []
    seed = 12345

    for _ in range(num_runs):
        random.seed(seed)
        team0, team1 = _build_teamfight_teams(engine, engine_name)
        result = _normalize_result(_run_combat(engine, engine_name, team0, team1, seed=seed))
        results.append(result)

    first = results[0]
    all_identical = all(r == first for r in results)
    return {
        'num_runs': num_runs,
        'seed': seed,
        'deterministic': all_identical,
        'num_differences': sum(1 for r in results if r != first),
        'sample_result': first,
    }


def _create_rust_game_simulator() -> Any:
    try:
        from tft_combat_engine import RustGameSimulator
    except Exception as exc:
        raise RuntimeError(
            "Rust full-game engine requested but RustGameSimulator is unavailable. "
            "Build/install simulator/core/rust_engine via maturin first."
        ) from exc
    combat_data_path = Path(__file__).parent / 'data' / 'combat_data.json'
    return RustGameSimulator(str(combat_data_path))


def benchmark_full_game(engine_name: str = 'python', num_games: int = 5) -> dict:
    """Benchmark full 8-player game throughput."""
    times: List[float] = []
    rounds_list: List[int] = []

    rust_sim = _create_rust_game_simulator() if engine_name == 'rust_full' else None

    for i in range(num_games):
        start = time.perf_counter()
        if engine_name == 'rust_full':
            result = rust_sim.run_game(i, i, None, False)
            rounds_list.append(int(result.get('rounds', 0)))
        else:
            game = TFTGame(num_players=8, seed=i, verbose=False, logging_enabled=False, engine=engine_name)
            game.play()
            rounds_list.append(game.round_num)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

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


def test_determinism_full_game(engine_name: str = 'python', num_runs: int = 5) -> dict:
    """Test determinism for full 8-player games."""
    results = []
    seed = 99
    rust_sim = _create_rust_game_simulator() if engine_name == 'rust_full' else None

    for _ in range(num_runs):
        random.seed(seed)
        if engine_name == 'rust_full':
            result = rust_sim.run_game(seed, seed, None, False)
            placements = [
                (int(row.get('player_id', -1)), int(row.get('placement', 0)))
                for row in result.get('placements', [])
            ]
            placements.sort(key=lambda x: x[1])
            results.append({'placements': placements, 'round_num': int(result.get('rounds', 0))})
        else:
            game = TFTGame(
                num_players=8,
                seed=seed,
                verbose=False,
                logging_enabled=False,
                engine=engine_name,
            )
            placements = game.play()
            results.append({'placements': placements, 'round_num': game.round_num})

    first = results[0]
    all_identical = all(r == first for r in results)
    return {
        'num_runs': num_runs,
        'seed': seed,
        'deterministic': all_identical,
        'num_differences': sum(1 for r in results if r != first),
        'sample_result': first,
    }


def _collect_distribution_stats(
    engine_name: str,
    num_games: int,
    seed_start: int,
) -> Dict[str, Any]:
    placement_counts: Counter = Counter()
    round_counts: List[int] = []
    progress_every = max(1, num_games // 10)
    start = time.perf_counter()
    rust_sim = _create_rust_game_simulator() if engine_name == 'rust_full' else None

    for i in range(num_games):
        game_seed = seed_start + i
        if engine_name == 'rust_full':
            result = rust_sim.run_game(game_seed, game_seed, None, False)
            for row in result.get('placements', []):
                placement_counts[int(row.get('placement', 0))] += 1
            round_counts.append(int(result.get('rounds', 0)))
        else:
            game = TFTGame(
                num_players=8,
                seed=game_seed,
                verbose=False,
                logging_enabled=False,
                engine=engine_name,
            )
            placements = game.play()
            for _, placement in placements:
                placement_counts[int(placement)] += 1
            round_counts.append(game.round_num)

        done = i + 1
        if done % progress_every == 0 or done == num_games:
            print(f"  [{engine_name}] {done}/{num_games} games")

    elapsed = time.perf_counter() - start
    total_placements = max(1, sum(placement_counts.values()))

    placement_mean = sum(p * placement_counts.get(p, 0) for p in range(1, 9)) / total_placements
    placement_var = sum(
        ((p - placement_mean) ** 2) * placement_counts.get(p, 0)
        for p in range(1, 9)
    ) / total_placements
    placement_std = math.sqrt(placement_var)

    round_mean = statistics.mean(round_counts) if round_counts else 0.0
    round_std = statistics.pstdev(round_counts) if len(round_counts) > 1 else 0.0
    round_p50 = statistics.median(round_counts) if round_counts else 0.0
    round_p90 = sorted(round_counts)[int((len(round_counts) - 1) * 0.9)] if round_counts else 0.0

    return {
        'engine': engine_name,
        'num_games': num_games,
        'elapsed_sec': round(elapsed, 2),
        'games_per_sec': round(num_games / elapsed, 3) if elapsed > 0 else 0.0,
        'placement_mean': round(placement_mean, 4),
        'placement_std': round(placement_std, 4),
        'round_mean': round(round_mean, 4),
        'round_std': round(round_std, 4),
        'round_p50': round(float(round_p50), 2),
        'round_p90': round(float(round_p90), 2),
        'placement_distribution': {
            str(p): round(placement_counts.get(p, 0) / total_placements, 4)
            for p in range(1, 9)
        },
    }


def run_phase6_distribution_compare(num_games: int, seed_start: int = 0) -> Dict[str, Any]:
    """Run Phase 6 statistical comparison between Python and Rust engines."""
    print()
    print("=" * 60)
    print("PHASE 6: CROSS-ENGINE DISTRIBUTION COMPARISON")
    print("=" * 60)
    print(f"Games per engine: {num_games}")
    print(f"Seed range: {seed_start} to {seed_start + num_games - 1}")
    print()

    python_stats = _collect_distribution_stats('python', num_games, seed_start)
    rust_stats = _collect_distribution_stats('rust', num_games, seed_start)

    placement_share_deltas = {}
    max_share_delta = -1.0
    max_share_delta_place = 1
    for place in range(1, 9):
        key = str(place)
        delta = abs(rust_stats['placement_distribution'][key] - python_stats['placement_distribution'][key])
        placement_share_deltas[key] = round(delta, 4)
        if delta > max_share_delta:
            max_share_delta = delta
            max_share_delta_place = place

    placement_mean_delta = rust_stats['placement_mean'] - python_stats['placement_mean']
    round_mean_delta = rust_stats['round_mean'] - python_stats['round_mean']

    comparison = {
        'placement_mean_delta': round(placement_mean_delta, 4),
        'round_mean_delta': round(round_mean_delta, 4),
        'max_placement_share_delta': round(max_share_delta, 4),
        'max_placement_share_delta_place': max_share_delta_place,
        'placement_share_deltas': placement_share_deltas,
        'placement_mean_within_target': abs(placement_mean_delta) <= 0.1,
        'round_mean_within_target': abs(round_mean_delta) <= 1.0,
    }
    comparison['statistically_similar'] = (
        comparison['placement_mean_within_target']
        and comparison['round_mean_within_target']
    )

    print()
    print("Phase 6 distribution summary:")
    print(f"  Placement mean delta (rust - python): {comparison['placement_mean_delta']:+.4f}")
    print(f"  Round mean delta (rust - python): {comparison['round_mean_delta']:+.4f}")
    print(
        "  Max placement share delta: "
        f"{comparison['max_placement_share_delta']:.4f} "
        f"(place {comparison['max_placement_share_delta_place']})"
    )
    print(f"  Statistically similar: {'Yes' if comparison['statistically_similar'] else 'No'}")
    print()

    return {
        'python': python_stats,
        'rust': rust_stats,
        'comparison': comparison,
    }


def _run_single_full_game(
    engine_name: str,
    game_seed: int,
    rust_sim_cache: Dict[str, Any],
) -> Dict[str, Any]:
    if engine_name == 'rust_full':
        sim = rust_sim_cache.get('rust_full')
        if sim is None:
            sim = _create_rust_game_simulator()
            rust_sim_cache['rust_full'] = sim
        result = sim.run_game(game_seed, game_seed, None, False)
        placements = [
            (int(row.get('player_id', -1)), int(row.get('placement', 0)))
            for row in result.get('placements', [])
        ]
        round_num = int(result.get('rounds', 0))
    else:
        game = TFTGame(
            num_players=8,
            seed=game_seed,
            verbose=False,
            logging_enabled=False,
            engine=engine_name,
        )
        placements = game.play()
        round_num = game.round_num

    placements = [(pid, place) for pid, place in placements if pid >= 0]
    placements.sort(key=lambda x: (x[1], x[0]))
    placement_map = {pid: place for pid, place in placements}
    placement_vector = tuple(int(placement_map.get(pid, 0)) for pid in range(8))
    top4_set = tuple(sorted(pid for pid, place in placements if place <= 4))
    rank_order = tuple(pid for pid, _ in placements)

    return {
        'placements': placements,
        'placement_vector': placement_vector,
        'rank_order': rank_order,
        'top4_set': top4_set,
        'round_num': int(round_num),
    }


def run_seed_parity_harness(
    baseline_engine: str,
    candidate_engine: str,
    num_games: int,
    seed_start: int = 0,
    sample_limit: int = 10,
) -> Dict[str, Any]:
    print()
    print("=" * 60)
    print("SEED PARITY HARNESS")
    print("=" * 60)
    print(f"Baseline engine:  {baseline_engine}")
    print(f"Candidate engine: {candidate_engine}")
    print(f"Games:            {num_games}")
    print(f"Seed range:       {seed_start} to {seed_start + num_games - 1}")
    print()

    mismatch_samples: List[Dict[str, Any]] = []
    exact_placement_matches = 0
    exact_rank_order_matches = 0
    exact_top4_matches = 0
    exact_round_matches = 0
    total_l1 = 0
    round_abs_deltas: List[int] = []

    baseline_time = 0.0
    candidate_time = 0.0
    rust_sim_cache: Dict[str, Any] = {}
    progress_every = max(1, num_games // 10)

    for i in range(num_games):
        seed = seed_start + i

        start = time.perf_counter()
        baseline = _run_single_full_game(baseline_engine, seed, rust_sim_cache)
        baseline_time += time.perf_counter() - start

        start = time.perf_counter()
        candidate = _run_single_full_game(candidate_engine, seed, rust_sim_cache)
        candidate_time += time.perf_counter() - start

        placement_match = baseline['placement_vector'] == candidate['placement_vector']
        rank_match = baseline['rank_order'] == candidate['rank_order']
        top4_match = baseline['top4_set'] == candidate['top4_set']
        round_match = baseline['round_num'] == candidate['round_num']

        if placement_match:
            exact_placement_matches += 1
        if rank_match:
            exact_rank_order_matches += 1
        if top4_match:
            exact_top4_matches += 1
        if round_match:
            exact_round_matches += 1

        l1 = sum(
            abs(int(a) - int(b))
            for a, b in zip(baseline['placement_vector'], candidate['placement_vector'])
        )
        total_l1 += l1
        round_delta = abs(int(baseline['round_num']) - int(candidate['round_num']))
        round_abs_deltas.append(round_delta)

        if (not placement_match or not round_match) and len(mismatch_samples) < sample_limit:
            mismatch_samples.append({
                'seed': seed,
                'baseline': {
                    'placements': baseline['placements'],
                    'round_num': baseline['round_num'],
                },
                'candidate': {
                    'placements': candidate['placements'],
                    'round_num': candidate['round_num'],
                },
                'placement_l1': l1,
                'round_abs_delta': round_delta,
            })

        done = i + 1
        if done % progress_every == 0 or done == num_games:
            print(f"  [{done}/{num_games}] parity comparisons complete")

    placement_match_rate = exact_placement_matches / num_games if num_games else 0.0
    rank_match_rate = exact_rank_order_matches / num_games if num_games else 0.0
    top4_match_rate = exact_top4_matches / num_games if num_games else 0.0
    round_match_rate = exact_round_matches / num_games if num_games else 0.0
    avg_l1 = total_l1 / num_games if num_games else 0.0
    round_mean_abs_delta = statistics.mean(round_abs_deltas) if round_abs_deltas else 0.0
    round_max_abs_delta = max(round_abs_deltas) if round_abs_deltas else 0

    print()
    print("Parity summary:")
    print(f"  Exact placement-vector match rate: {placement_match_rate:.2%}")
    print(f"  Exact rank-order match rate:       {rank_match_rate:.2%}")
    print(f"  Exact top-4 set match rate:        {top4_match_rate:.2%}")
    print(f"  Exact round-count match rate:      {round_match_rate:.2%}")
    print(f"  Mean placement L1 delta/game:      {avg_l1:.3f}")
    print(f"  Mean round abs delta:              {round_mean_abs_delta:.3f}")
    print(f"  Max round abs delta:               {round_max_abs_delta}")
    print(
        f"  Throughput ({baseline_engine}/{candidate_engine}): "
        f"{(num_games / baseline_time) if baseline_time > 0 else 0.0:.2f}/"
        f"{(num_games / candidate_time) if candidate_time > 0 else 0.0:.2f} games/sec"
    )
    print()

    return {
        'baseline_engine': baseline_engine,
        'candidate_engine': candidate_engine,
        'num_games': num_games,
        'seed_start': seed_start,
        'seed_end': seed_start + num_games - 1,
        'placement_vector_match_rate': round(placement_match_rate, 4),
        'rank_order_match_rate': round(rank_match_rate, 4),
        'top4_set_match_rate': round(top4_match_rate, 4),
        'round_match_rate': round(round_match_rate, 4),
        'mean_placement_l1_delta': round(avg_l1, 4),
        'mean_round_abs_delta': round(float(round_mean_abs_delta), 4),
        'max_round_abs_delta': int(round_max_abs_delta),
        'baseline_games_per_sec': round((num_games / baseline_time) if baseline_time > 0 else 0.0, 4),
        'candidate_games_per_sec': round((num_games / candidate_time) if candidate_time > 0 else 0.0, 4),
        'mismatch_samples': mismatch_samples,
    }


def run_full_benchmark(
    engine_name: str = 'python',
    sims_1v1: int = 1000,
    sims_team: int = 100,
    full_games: int = 5,
    det_1v1_runs: int = 100,
    det_team_runs: int = 50,
    det_game_runs: int = 5,
) -> Dict[str, Any]:
    """Run throughput and determinism benchmarks for one engine backend."""
    print("=" * 60)
    print(f"TFT Combat Simulator Benchmark & Validation ({engine_name})")
    print("=" * 60)
    print()

    print("Loading combat engine...")
    load_start = time.perf_counter()
    engine = _create_engine(engine_name)
    load_time = time.perf_counter() - load_start
    print(f"  Engine loaded in {load_time:.2f}s")
    print(f"  Champions: {_engine_champion_count(engine, engine_name)}")
    if engine_name == 'python':
        print(
            "  Augments: "
            f"{len(engine.augment_manager.augment_data) if hasattr(engine, 'augment_manager') else 'N/A'}"
        )
    else:
        print("  Augments: N/A")
    print()

    print("-" * 60)
    print("THROUGHPUT BENCHMARKS")
    print("-" * 60)

    print(f"\n1v1 Benchmark ({sims_1v1} sims)...")
    bench_1v1 = benchmark_1v1(engine, engine_name, sims_1v1)
    print(f"  Elapsed: {bench_1v1['elapsed_sec']}s")
    print(f"  Throughput: {bench_1v1['sims_per_sec']} sims/sec")

    print(f"\nTeam Combat Benchmark ({sims_team} sims, 4v4)...")
    bench_team = benchmark_team_combat(engine, engine_name, sims_team)
    print(f"  Elapsed: {bench_team['elapsed_sec']}s")
    print(f"  Throughput: {bench_team['sims_per_sec']} sims/sec")

    print(f"\nFull Game Benchmark ({full_games} games, 8 players each)...")
    bench_game = benchmark_full_game(engine_name=engine_name, num_games=full_games)
    print(f"  Total: {bench_game['total_sec']}s")
    print(
        f"  Avg: {bench_game['avg_sec_per_game']}s/game "
        f"(min={bench_game['min_sec']}s, max={bench_game['max_sec']}s)"
    )
    print(f"  Avg rounds: {bench_game['avg_rounds']}")
    print(f"  Throughput: {bench_game['games_per_hour']:.0f} games/hour")

    print()
    print("-" * 60)
    print("DETERMINISM TESTS")
    print("-" * 60)

    print(f"\n1v1 Determinism ({det_1v1_runs} runs, same seed)...")
    det_1v1 = test_determinism(engine, engine_name, det_1v1_runs)
    if det_1v1['deterministic']:
        print(f"  [PASS] - All {det_1v1['num_runs']} runs identical")
    else:
        print(f"  [FAIL] - {det_1v1['num_differences']} runs differed!")
        print(f"  First difference: {det_1v1['first_difference']}")

    print(f"\nTeam Combat Determinism ({det_team_runs} runs, same seed)...")
    det_team = test_determinism_team_combat(engine, engine_name, det_team_runs)
    if det_team['deterministic']:
        print(f"  [PASS] - All {det_team['num_runs']} runs identical")
    else:
        print(f"  [FAIL] - {det_team['num_differences']} runs differed!")

    print(f"\nFull Game Determinism ({det_game_runs} runs, same seed)...")
    det_game = test_determinism_full_game(engine_name=engine_name, num_runs=det_game_runs)
    if det_game['deterministic']:
        print(f"  [PASS] - All {det_game['num_runs']} runs identical")
        print(f"    Placements: {det_game['sample_result']['placements']}")
    else:
        print(f"  [FAIL] - {det_game['num_differences']} runs differed!")

    print()
    print("=" * 60)
    print(f"SUMMARY ({engine_name})")
    print("=" * 60)
    print()
    print("| Metric | Value |")
    print("|--------|-------|")
    print(f"| Engine load time | {load_time:.3f}s |")
    print(f"| 1v1 throughput | {bench_1v1['sims_per_sec']} sims/sec |")
    print(f"| Team combat throughput | {bench_team['sims_per_sec']} sims/sec |")
    print(f"| 1v1 deterministic | {'Yes' if det_1v1['deterministic'] else 'No'} |")
    print(f"| Team combat deterministic | {'Yes' if det_team['deterministic'] else 'No'} |")
    print(
        f"| Full game throughput | {bench_game['avg_sec_per_game']}s/game "
        f"({bench_game['games_per_hour']:.0f}/hr) |"
    )
    print(f"| Full game deterministic | {'Yes' if det_game['deterministic'] else 'No'} |")
    print()

    return {
        'engine': engine_name,
        'load_time': load_time,
        'benchmark_1v1': bench_1v1,
        'benchmark_team': bench_team,
        'benchmark_game': bench_game,
        'determinism_1v1': det_1v1,
        'determinism_team': det_team,
        'determinism_game': det_game,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Benchmark TFT python/rust combat engines')
    parser.add_argument(
        '--engine',
        choices=['python', 'rust', 'rust_full', 'both'],
        default='python',
        help='Engine backend to benchmark (default: python)',
    )
    parser.add_argument('--sims-1v1', type=int, default=1000, help='1v1 benchmark simulation count')
    parser.add_argument('--sims-team', type=int, default=100, help='Team benchmark simulation count')
    parser.add_argument('--games', type=int, default=5, help='Full-game benchmark count')
    parser.add_argument('--det-1v1', type=int, default=100, help='1v1 determinism run count')
    parser.add_argument('--det-team', type=int, default=50, help='Team determinism run count')
    parser.add_argument('--det-games', type=int, default=5, help='Full-game determinism run count')
    parser.add_argument(
        '--compare-games',
        type=int,
        default=0,
        help='Phase 6: run cross-engine distribution comparison with this many games per engine',
    )
    parser.add_argument(
        '--compare-seed-start',
        type=int,
        default=0,
        help='Starting seed for Phase 6 distribution comparison',
    )
    parser.add_argument(
        '--parity-games',
        type=int,
        default=0,
        help='Run seed-level parity harness with this many games (0 disables)',
    )
    parser.add_argument(
        '--parity-seed-start',
        type=int,
        default=0,
        help='Starting seed for parity harness',
    )
    parser.add_argument(
        '--parity-engines',
        type=str,
        default='python,rust_full',
        help='Comma-separated engine pair for parity harness, e.g. python,rust_full',
    )
    parser.add_argument(
        '--parity-sample-limit',
        type=int,
        default=10,
        help='Maximum mismatch samples to include in parity output',
    )
    args = parser.parse_args()

    for field in (
        'sims_1v1',
        'sims_team',
        'games',
        'det_1v1',
        'det_team',
        'det_games',
        'compare_games',
    ):
        if getattr(args, field) <= 0 and field != 'compare_games':
            parser.error(f"--{field.replace('_', '-')} must be > 0")
    if args.compare_games < 0:
        parser.error("--compare-games must be >= 0")
    if args.compare_games > 0 and args.engine != 'both':
        parser.error("--compare-games requires --engine both")
    if args.parity_games < 0:
        parser.error("--parity-games must be >= 0")
    if args.parity_sample_limit <= 0:
        parser.error("--parity-sample-limit must be > 0")
    parsed_parity_engines = [value.strip() for value in args.parity_engines.split(',') if value.strip()]
    if args.parity_games > 0:
        valid_engines = {'python', 'rust', 'rust_full'}
        if len(parsed_parity_engines) != 2:
            parser.error("--parity-engines must provide exactly two engines")
        if parsed_parity_engines[0] == parsed_parity_engines[1]:
            parser.error("--parity-engines must contain two different engines")
        for engine_name in parsed_parity_engines:
            if engine_name not in valid_engines:
                parser.error(f"Unknown parity engine '{engine_name}'")
    args.parity_engine_pair = parsed_parity_engines
    return args


def main() -> Dict[str, Any]:
    args = _parse_args()
    parity_result: Dict[str, Any] | None = None

    if args.engine == 'both':
        python_results = run_full_benchmark(
            engine_name='python',
            sims_1v1=args.sims_1v1,
            sims_team=args.sims_team,
            full_games=args.games,
            det_1v1_runs=args.det_1v1,
            det_team_runs=args.det_team,
            det_game_runs=args.det_games,
        )
        rust_results = run_full_benchmark(
            engine_name='rust',
            sims_1v1=args.sims_1v1,
            sims_team=args.sims_team,
            full_games=args.games,
            det_1v1_runs=args.det_1v1,
            det_team_runs=args.det_team,
            det_game_runs=args.det_games,
        )
        results: Dict[str, Any] = {'python': python_results, 'rust': rust_results}

        python_avg = python_results['benchmark_game']['avg_sec_per_game']
        rust_avg = rust_results['benchmark_game']['avg_sec_per_game']
        speedup = (python_avg / rust_avg) if rust_avg > 0 else float('inf')

        print("=" * 60)
        print("CROSS-ENGINE BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Python avg full-game time: {python_avg:.3f}s")
        print(f"Rust avg full-game time:   {rust_avg:.3f}s")
        print(f"Rust speedup vs python:    {speedup:.2f}x")
        print()

        if args.compare_games > 0:
            results['distribution_compare'] = run_phase6_distribution_compare(
                num_games=args.compare_games,
                seed_start=args.compare_seed_start,
            )
        if args.parity_games > 0:
            parity_result = run_seed_parity_harness(
                baseline_engine=args.parity_engine_pair[0],
                candidate_engine=args.parity_engine_pair[1],
                num_games=args.parity_games,
                seed_start=args.parity_seed_start,
                sample_limit=args.parity_sample_limit,
            )
            results['parity_harness'] = parity_result
        return results

    result = run_full_benchmark(
        engine_name=args.engine,
        sims_1v1=args.sims_1v1,
        sims_team=args.sims_team,
        full_games=args.games,
        det_1v1_runs=args.det_1v1,
        det_team_runs=args.det_team,
        det_game_runs=args.det_games,
    )
    if args.parity_games > 0:
        parity_result = run_seed_parity_harness(
            baseline_engine=args.parity_engine_pair[0],
            candidate_engine=args.parity_engine_pair[1],
            num_games=args.parity_games,
            seed_start=args.parity_seed_start,
            sample_limit=args.parity_sample_limit,
        )
        result['parity_harness'] = parity_result
    return result


if __name__ == "__main__":
    main()
