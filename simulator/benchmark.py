#!/usr/bin/env python3
"""
TFT Combat Simulator Benchmark & Determinism Tests.

Validates combat throughput and determinism, and can run Phase 6
cross-engine statistical checks.
"""

from __future__ import annotations

import argparse
import json
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
from simulator.game.collector import GameCollector
from simulator.game.constants import BOARD_COLS, BOARD_ROWS
from simulator.game.game import TFTGame

UnitSnapshotSig = Tuple[str, int, Tuple[str, ...], int]
TakedownSig = Tuple[int, str, int, str]


def _create_engine(engine_name: str) -> Any:
    if engine_name in ("rust", "rust_full"):
        try:
            from tft_combat_engine import RustCombatEngine
        except Exception as exc:
            raise RuntimeError(
                "Rust engine requested but tft_combat_engine is unavailable. "
                "Build/install simulator/core/rust_engine via maturin first."
            ) from exc
        combat_data_path = Path(__file__).parent / "data" / "combat_data.json"
        return RustCombatEngine(str(combat_data_path))

    if engine_name != "python":
        raise ValueError(f"Unknown engine '{engine_name}'")
    return CombatEngine()


def _engine_champion_count(engine: Any, engine_name: str) -> int:
    if engine_name in ("rust", "rust_full"):
        return int(engine.num_champions())
    return len(engine.champions)


def _build_unit(
    engine: Any,
    engine_name: str,
    api_name: str,
    team: int,
    position: Tuple[int, int],
    star_level: int = 2,
    items: List[str] | None = None,
    traits: List[str] | None = None,
) -> Any:
    item_list = items or []
    trait_list = traits or []
    if engine_name in ("rust", "rust_full"):
        return {
            "api_name": api_name,
            "star_level": star_level,
            "position": [position[0], position[1]],
            "team": team,
            "items": item_list,
            "traits": trait_list,
        }
    return engine.create_unit(
        api_name,
        star_level=star_level,
        team=team,
        position=position,
        items=item_list,
    )


def _build_duel_teams(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [_build_unit(engine, engine_name, "TFT16_Draven", 0, (0, 3))]
    team1 = [_build_unit(engine, engine_name, "TFT16_Leona", 1, (3, 3))]
    return team0, team1


def _build_teamfight_teams(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [
        _build_unit(engine, engine_name, "TFT16_Draven", 0, (0, 0)),
        _build_unit(engine, engine_name, "TFT16_Leona", 0, (1, 0)),
        _build_unit(engine, engine_name, "TFT16_Lux", 0, (2, 0)),
        _build_unit(engine, engine_name, "TFT16_Yasuo", 0, (3, 0)),
    ]
    team1 = [
        _build_unit(engine, engine_name, "TFT16_Draven", 1, (3, 6)),
        _build_unit(engine, engine_name, "TFT16_Leona", 1, (2, 6)),
        _build_unit(engine, engine_name, "TFT16_Lux", 1, (1, 6)),
        _build_unit(engine, engine_name, "TFT16_Yasuo", 1, (0, 6)),
    ]
    return team0, team1


def _build_teamfight_teams_8v8(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [
        _build_unit(engine, engine_name, "TFT16_Leona", 0, (0, 0), items=["WarmogsArmor"]),
        _build_unit(engine, engine_name, "TFT16_Braum", 0, (1, 0), items=["SunfireCape"]),
        _build_unit(engine, engine_name, "TFT16_Nautilus", 0, (2, 0), items=["GargoyleStoneplate"]),
        _build_unit(engine, engine_name, "TFT16_Sejuani", 0, (3, 0), items=["ProtectorsVow"]),
        _build_unit(
            engine, engine_name, "TFT16_Draven", 0, (0, 2), items=["InfinityEdge", "LastWhisper"]
        ),
        _build_unit(
            engine, engine_name, "TFT16_Lux", 0, (1, 2), items=["JeweledGauntlet", "BlueBuff"]
        ),
        _build_unit(engine, engine_name, "TFT16_Ryze", 0, (2, 2), items=["ArchangelsStaff"]),
        _build_unit(
            engine, engine_name, "TFT16_Jinx", 0, (3, 2), items=["GuinsoosRageblade", "GiantSlayer"]
        ),
    ]
    team1 = [
        _build_unit(engine, engine_name, "TFT16_Sion", 1, (0, 6), items=["WarmogsArmor"]),
        _build_unit(engine, engine_name, "TFT16_Taric", 1, (1, 6), items=["GargoyleStoneplate"]),
        _build_unit(engine, engine_name, "TFT16_ChoGath", 1, (2, 6), items=["SunfireCape"]),
        _build_unit(engine, engine_name, "TFT16_Vi", 1, (3, 6), items=["TitansResolve"]),
        _build_unit(
            engine, engine_name, "TFT16_Caitlyn", 1, (0, 4), items=["InfinityEdge", "LastWhisper"]
        ),
        _build_unit(
            engine, engine_name, "TFT16_Leblanc", 1, (1, 4), items=["JeweledGauntlet", "BlueBuff"]
        ),
        _build_unit(engine, engine_name, "TFT16_Xerath", 1, (2, 4), items=["ArchangelsStaff"]),
        _build_unit(engine, engine_name, "TFT16_Yasuo", 1, (3, 4), items=["Bloodthirster"]),
    ]
    return team0, team1


def _build_focus_case_draven_vs_leona(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [
        _build_unit(
            engine,
            engine_name,
            "TFT16_Draven",
            0,
            (0, 3),
        ),
    ]
    team1 = [
        _build_unit(
            engine,
            engine_name,
            "TFT16_Leona",
            1,
            (3, 3),
        ),
    ]
    return team0, team1


def _build_focus_case_sion_vs_draven(engine: Any, engine_name: str) -> Tuple[List[Any], List[Any]]:
    team0 = [
        _build_unit(
            engine,
            engine_name,
            "TFT16_Sion",
            0,
            (0, 3),
            items=["WarmogsArmor", "DragonsClaw"],
        ),
    ]
    team1 = [
        _build_unit(
            engine,
            engine_name,
            "TFT16_Draven",
            1,
            (3, 3),
            items=["InfinityEdge", "LastWhisper", "GiantSlayer"],
        ),
    ]
    return team0, team1


def _run_combat(
    engine: Any, engine_name: str, team0: List[Any], team1: List[Any], seed: int
) -> Dict[str, Any]:
    if engine_name in ("rust", "rust_full"):
        return engine.run_combat(team0, team1, seed=seed)
    return engine.run_combat(team0, team1, verbose=False, seed=seed)


def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    damage_map = result.get("total_damage_dealt", {}) or {}
    team0_damage = result.get("team0_total_damage", damage_map.get("team0", 0.0))
    team1_damage = result.get("team1_total_damage", damage_map.get("team1", 0.0))
    return {
        "winner": int(result.get("winner", -1)),
        "combat_time": round(float(result.get("combat_time", 0.0)), 6),
        "team0_survivors": int(result.get("team0_survivors", 0)),
        "team1_survivors": int(result.get("team1_survivors", 0)),
        "team0_damage": round(float(team0_damage), 6),
        "team1_damage": round(float(team1_damage), 6),
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
        result = _normalize_result(
            _run_combat(engine, engine_name, team0, team1, seed=1_000_000 + i)
        )
        if result["winner"] == 0:
            team0_wins += 1
        elif result["winner"] == 1:
            team1_wins += 1
        else:
            draws += 1
        total_damage += result["team0_damage"] + result["team1_damage"]
        total_time += result["combat_time"]

    elapsed = time.perf_counter() - start
    return {
        "num_sims": num_sims,
        "elapsed_sec": round(elapsed, 3),
        "sims_per_sec": round(num_sims / elapsed, 1),
        "result": {
            "team0_win_rate": round(team0_wins / max(1, num_sims), 4),
            "team1_win_rate": round(team1_wins / max(1, num_sims), 4),
            "draw_rate": round(draws / max(1, num_sims), 4),
            "avg_total_damage": round(total_damage / max(1, num_sims), 2),
            "avg_combat_time": round(total_time / max(1, num_sims), 3),
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
        "num_sims": num_sims,
        "team_size": 4,
        "elapsed_sec": round(elapsed, 3),
        "sims_per_sec": round(num_sims / elapsed, 1),
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
            differences.append({"run": i, "expected": first, "got": r})

    return {
        "num_runs": num_runs,
        "seed": seed,
        "deterministic": all_identical,
        "num_differences": len(differences),
        "first_difference": differences[0] if differences else None,
        "sample_result": first,
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
        "num_runs": num_runs,
        "seed": seed,
        "deterministic": all_identical,
        "num_differences": sum(1 for r in results if r != first),
        "sample_result": first,
    }


def _create_rust_game_simulator() -> Any:
    try:
        from tft_combat_engine import RustGameSimulator
    except Exception as exc:
        raise RuntimeError(
            "Rust full-game engine requested but RustGameSimulator is unavailable. "
            "Build/install simulator/core/rust_engine via maturin first."
        ) from exc
    combat_data_path = Path(__file__).parent / "data" / "combat_data.json"
    return RustGameSimulator(str(combat_data_path))


def benchmark_full_game(engine_name: str = "python", num_games: int = 5) -> dict:
    """Benchmark full 8-player game throughput."""
    times: List[float] = []
    rounds_list: List[int] = []

    rust_sim = _create_rust_game_simulator() if engine_name == "rust_full" else None

    for i in range(num_games):
        start = time.perf_counter()
        if engine_name == "rust_full":
            result = rust_sim.run_game(i, i, None, False)
            rounds_list.append(int(result.get("rounds", 0)))
        else:
            game = TFTGame(
                num_players=8, seed=i, verbose=False, logging_enabled=False, engine=engine_name
            )
            game.play()
            rounds_list.append(game.round_num)
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    avg_rounds = sum(rounds_list) / len(rounds_list)
    return {
        "num_games": num_games,
        "total_sec": round(sum(times), 3),
        "avg_sec_per_game": round(avg_time, 3),
        "min_sec": round(min(times), 3),
        "max_sec": round(max(times), 3),
        "avg_rounds": round(avg_rounds, 1),
        "games_per_hour": round(3600 / avg_time, 0),
    }


def test_determinism_full_game(engine_name: str = "python", num_runs: int = 5) -> dict:
    """Test determinism for full 8-player games."""
    results = []
    seed = 99
    rust_sim = _create_rust_game_simulator() if engine_name == "rust_full" else None

    for _ in range(num_runs):
        random.seed(seed)
        if engine_name == "rust_full":
            result = rust_sim.run_game(seed, seed, None, False)
            placements = [
                (int(row.get("player_id", -1)), int(row.get("placement", 0)))
                for row in result.get("placements", [])
            ]
            placements.sort(key=lambda x: x[1])
            results.append({"placements": placements, "round_num": int(result.get("rounds", 0))})
        else:
            game = TFTGame(
                num_players=8,
                seed=seed,
                verbose=False,
                logging_enabled=False,
                engine=engine_name,
            )
            placements = game.play()
            results.append({"placements": placements, "round_num": game.round_num})

    first = results[0]
    all_identical = all(r == first for r in results)
    return {
        "num_runs": num_runs,
        "seed": seed,
        "deterministic": all_identical,
        "num_differences": sum(1 for r in results if r != first),
        "sample_result": first,
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
    rust_sim = _create_rust_game_simulator() if engine_name == "rust_full" else None

    for i in range(num_games):
        game_seed = seed_start + i
        if engine_name == "rust_full":
            result = rust_sim.run_game(game_seed, game_seed, None, False)
            for row in result.get("placements", []):
                placement_counts[int(row.get("placement", 0))] += 1
            round_counts.append(int(result.get("rounds", 0)))
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
    placement_var = (
        sum(((p - placement_mean) ** 2) * placement_counts.get(p, 0) for p in range(1, 9))
        / total_placements
    )
    placement_std = math.sqrt(placement_var)

    round_mean = statistics.mean(round_counts) if round_counts else 0.0
    round_std = statistics.pstdev(round_counts) if len(round_counts) > 1 else 0.0
    round_p50 = statistics.median(round_counts) if round_counts else 0.0
    round_p90 = sorted(round_counts)[int((len(round_counts) - 1) * 0.9)] if round_counts else 0.0

    return {
        "engine": engine_name,
        "num_games": num_games,
        "elapsed_sec": round(elapsed, 2),
        "games_per_sec": round(num_games / elapsed, 3) if elapsed > 0 else 0.0,
        "placement_mean": round(placement_mean, 4),
        "placement_std": round(placement_std, 4),
        "round_mean": round(round_mean, 4),
        "round_std": round(round_std, 4),
        "round_p50": round(float(round_p50), 2),
        "round_p90": round(float(round_p90), 2),
        "placement_distribution": {
            str(p): round(placement_counts.get(p, 0) / total_placements, 4) for p in range(1, 9)
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

    python_stats = _collect_distribution_stats("python", num_games, seed_start)
    rust_stats = _collect_distribution_stats("rust", num_games, seed_start)

    placement_share_deltas = {}
    max_share_delta = -1.0
    max_share_delta_place = 1
    for place in range(1, 9):
        key = str(place)
        delta = abs(
            rust_stats["placement_distribution"][key] - python_stats["placement_distribution"][key]
        )
        placement_share_deltas[key] = round(delta, 4)
        if delta > max_share_delta:
            max_share_delta = delta
            max_share_delta_place = place

    placement_mean_delta = rust_stats["placement_mean"] - python_stats["placement_mean"]
    round_mean_delta = rust_stats["round_mean"] - python_stats["round_mean"]

    comparison = {
        "placement_mean_delta": round(placement_mean_delta, 4),
        "round_mean_delta": round(round_mean_delta, 4),
        "max_placement_share_delta": round(max_share_delta, 4),
        "max_placement_share_delta_place": max_share_delta_place,
        "placement_share_deltas": placement_share_deltas,
        "placement_mean_within_target": abs(placement_mean_delta) <= 0.1,
        "round_mean_within_target": abs(round_mean_delta) <= 1.0,
    }
    comparison["statistically_similar"] = (
        comparison["placement_mean_within_target"] and comparison["round_mean_within_target"]
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
        "python": python_stats,
        "rust": rust_stats,
        "comparison": comparison,
    }


def _run_single_full_game(
    engine_name: str,
    game_seed: int,
    rust_sim_cache: Dict[str, Any],
) -> Dict[str, Any]:
    if engine_name == "rust_full":
        sim = rust_sim_cache.get("rust_full")
        if sim is None:
            sim = _create_rust_game_simulator()
            rust_sim_cache["rust_full"] = sim
        result = sim.run_game(game_seed, game_seed, None, False)
        placements = [
            (int(row.get("player_id", -1)), int(row.get("placement", 0)))
            for row in result.get("placements", [])
        ]
        round_num = int(result.get("rounds", 0))
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
        "placements": placements,
        "placement_vector": placement_vector,
        "rank_order": rank_order,
        "top4_set": top4_set,
        "round_num": int(round_num),
    }


def _run_single_full_game_with_rows(
    engine_name: str,
    game_seed: int,
    rust_sim_cache: Dict[str, Any],
) -> Dict[str, Any]:
    if engine_name == "rust_full":
        sim = rust_sim_cache.get("rust_full")
        if sim is None:
            sim = _create_rust_game_simulator()
            rust_sim_cache["rust_full"] = sim
        result = sim.run_game(game_seed, game_seed, None, True)
        placements = [
            (int(row.get("player_id", -1)), int(row.get("placement", 0)))
            for row in result.get("placements", [])
        ]
        round_num = int(result.get("rounds", 0))
        training_rows = result.get("training_rows", []) or []
        combat_debug = result.get("combat_debug", []) or []
    else:
        collector = GameCollector(game_id=game_seed)
        game = TFTGame(
            num_players=8,
            seed=game_seed,
            verbose=False,
            logging_enabled=False,
            collector=collector,
            engine=engine_name,
        )
        placements = game.play()
        round_num = game.round_num
        training_rows = collector.get_training_rows()
        combat_debug = []
        for round_data in collector.rounds:
            round_num_value = int(round_data.get("round", 0))
            for combat in round_data.get("combats", []):
                combat_debug.append(
                    {
                        "round": round_num_value,
                        "p1": int(combat.get("p1", -1)),
                        "p2": int(combat.get("p2", -1)),
                        "is_ghost": bool(combat.get("is_ghost", False)),
                        "debug_takedowns": combat.get("debug_takedowns", []) or [],
                    }
                )

    placements = [(pid, place) for pid, place in placements if pid >= 0]
    placements.sort(key=lambda x: (x[1], x[0]))
    placement_map = {pid: place for pid, place in placements}
    placement_vector = tuple(int(placement_map.get(pid, 0)) for pid in range(8))
    top4_set = tuple(sorted(pid for pid, place in placements if place <= 4))
    rank_order = tuple(pid for pid, _ in placements)

    return {
        "placements": placements,
        "placement_vector": placement_vector,
        "rank_order": rank_order,
        "top4_set": top4_set,
        "round_num": int(round_num),
        "training_rows": training_rows,
        "combat_debug": combat_debug,
    }


def _normalize_unit_snapshot(unit: Dict[str, Any]) -> UnitSnapshotSig:
    champion_id = str(unit.get("champion_id") or unit.get("api_name") or unit.get("name") or "")
    star_level = int(unit.get("star_level", unit.get("star", 1)) or 1)
    items = tuple(sorted(str(item) for item in (unit.get("items") or [])))

    position = unit.get("position")
    if position is None:
        pos = unit.get("pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            position = int(pos[0]) * 7 + int(pos[1])

    return champion_id, star_level, items, int(position) if position is not None else -1


def _normalize_trait_map(value: Any) -> Tuple[Tuple[str, int], ...]:
    if not isinstance(value, dict):
        return tuple()
    return tuple(sorted((str(name), int(count)) for name, count in value.items()))


def _normalize_training_row(row: Dict[str, Any]) -> Dict[str, Any]:
    traits = row.get("traits") or {}
    opponent_traits = row.get("opponent_traits") or {}
    augments = tuple(sorted(str(augment) for augment in (row.get("augments") or [])))
    units = tuple(sorted(_normalize_unit_snapshot(unit) for unit in (row.get("units") or [])))
    opponent_units = tuple(
        sorted(_normalize_unit_snapshot(unit) for unit in (row.get("opponent_units") or []))
    )

    return {
        "round": int(row.get("round", 0)),
        "player_id": int(row.get("player_id", -1)),
        "hp": int(row.get("hp", 0)),
        "gold": int(row.get("gold", 0)),
        "level": int(row.get("level", 0)),
        "streak": int(row.get("streak", 0)),
        "board_count": int(row.get("board_count", 0)),
        "win_streak": int(row.get("win_streak", 0)),
        "loss_streak": int(row.get("loss_streak", 0)),
        "num_augments": int(row.get("num_augments", len(augments))),
        "num_traits": int(row.get("num_traits", len(traits))),
        "alive_count": int(row.get("alive_count", 0)),
        "combat_result": None
        if row.get("combat_result") is None
        else int(row.get("combat_result", 0)),
        "damage_dealt": round(float(row.get("damage_dealt", 0.0)), 6),
        "damage_taken": round(float(row.get("damage_taken", 0.0)), 6),
        "opponent_hp": int(row.get("opponent_hp", 0)),
        "traits": _normalize_trait_map(traits),
        "opponent_traits": _normalize_trait_map(opponent_traits),
        "augments": augments,
        "units": units,
        "opponent_units": opponent_units,
    }


def _rows_by_round_player(rows: List[Dict[str, Any]]) -> Dict[Tuple[int, int], Dict[str, Any]]:
    normalized: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for row in rows:
        entry = _normalize_training_row(row)
        key = (entry["round"], entry["player_id"])
        normalized[key] = entry
    return normalized


def _normalize_takedown_entry(entry: Dict[str, Any]) -> TakedownSig:
    return (
        int(entry.get("killer_team", -1)),
        str(entry.get("killer_api_name", "")),
        int(entry.get("victim_team", -1)),
        str(entry.get("victim_api_name", "")),
    )


def _summarize_takedowns_for_player(
    takedowns: List[TakedownSig],
    *,
    player_team: int,
) -> Dict[str, Any]:
    counts: Counter[TakedownSig] = Counter(takedowns)
    total_signature = tuple(
        sorted(
            (killer_team, killer_api_name, victim_team, victim_api_name, count)
            for (
                killer_team,
                killer_api_name,
                victim_team,
                victim_api_name,
            ), count in counts.items()
        )
    )
    player_signature = tuple(
        sorted(
            (killer_api_name, victim_api_name, count)
            for (
                killer_team,
                killer_api_name,
                _victim_team,
                victim_api_name,
            ), count in counts.items()
            if killer_team == player_team
        )
    )
    opponent_signature = tuple(
        sorted(
            (killer_api_name, victim_api_name, count)
            for (
                killer_team,
                killer_api_name,
                _victim_team,
                victim_api_name,
            ), count in counts.items()
            if killer_team != player_team
        )
    )
    return {
        "takedown_count": int(sum(counts.values())),
        "player_kill_count": int(
            sum(
                count
                for (killer_team, _, _, _), count in counts.items()
                if killer_team == player_team
            )
        ),
        "opponent_kill_count": int(
            sum(
                count
                for (killer_team, _, _, _), count in counts.items()
                if killer_team != player_team
            )
        ),
        "takedown_signature": total_signature,
        "player_last_hit_signature": player_signature,
        "opponent_last_hit_signature": opponent_signature,
    }


def _build_combat_debug_context_by_key(
    combat_debug_rows: List[Dict[str, Any]],
    *,
    include_raw_takedowns: bool = True,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    debug_by_key: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for row in combat_debug_rows:
        round_num = int(row.get("round", 0))
        p1 = int(row.get("p1", -1))
        p2 = int(row.get("p2", -1))
        is_ghost = bool(row.get("is_ghost", False))
        if p1 < 0:
            continue

        normalized_takedowns = [
            _normalize_takedown_entry(entry)
            for entry in (row.get("debug_takedowns") or [])
            if isinstance(entry, dict)
        ]
        summary_team0 = _summarize_takedowns_for_player(normalized_takedowns, player_team=0)
        team0_context = {
            "opponent_id": p2,
            "is_ghost": is_ghost,
            "player_team": 0,
            **summary_team0,
        }
        if include_raw_takedowns:
            team0_context["debug_takedowns"] = normalized_takedowns
        debug_by_key[(round_num, p1)] = team0_context

        if is_ghost or p2 < 0:
            continue

        summary_team1 = _summarize_takedowns_for_player(normalized_takedowns, player_team=1)
        team1_context = {
            "opponent_id": p1,
            "is_ghost": False,
            "player_team": 1,
            **summary_team1,
        }
        if include_raw_takedowns:
            team1_context["debug_takedowns"] = normalized_takedowns
        debug_by_key[(round_num, p2)] = team1_context
    return debug_by_key


def _mirror_hex_position(position: int) -> int:
    if position < 0:
        return position

    row = position // BOARD_COLS
    col = position % BOARD_COLS
    if row < 0 or row >= BOARD_ROWS or col < 0 or col >= BOARD_COLS:
        return position
    return (BOARD_ROWS - 1 - row) * BOARD_COLS + col


def _mirror_units_signature(units: Tuple[UnitSnapshotSig, ...]) -> Tuple[UnitSnapshotSig, ...]:
    mirrored_units: List[UnitSnapshotSig] = []
    for champion_id, star_level, items, position in units:
        mirrored_units.append((champion_id, star_level, items, _mirror_hex_position(position)))
    return tuple(sorted(mirrored_units))


def _build_matchup_context_map(
    rows_by_key: Dict[Tuple[int, int], Dict[str, Any]],
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    rows_by_round: Dict[int, Dict[int, Dict[str, Any]]] = {}
    for (round_num, player_id), row in rows_by_key.items():
        rows_by_round.setdefault(round_num, {})[player_id] = row

    context_map: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for round_num, round_rows in rows_by_round.items():
        board_to_player_ids: Dict[Tuple[UnitSnapshotSig, ...], List[int]] = {}
        for player_id, row in round_rows.items():
            board_to_player_ids.setdefault(row["units"], []).append(player_id)

        for player_id, row in round_rows.items():
            candidates_by_units = [
                opp_id
                for opp_id in board_to_player_ids.get(row["opponent_units"], [])
                if opp_id != player_id
            ]
            candidate_ids = candidates_by_units[:]

            if len(candidate_ids) > 1:
                by_traits_hp = [
                    opp_id
                    for opp_id in candidate_ids
                    if round_rows[opp_id]["traits"] == row["opponent_traits"]
                    and round_rows[opp_id]["hp"] == row["opponent_hp"]
                ]
                if by_traits_hp:
                    candidate_ids = by_traits_hp

            if len(candidate_ids) > 1:
                by_hp = [
                    opp_id
                    for opp_id in candidate_ids
                    if round_rows[opp_id]["hp"] == row["opponent_hp"]
                ]
                if by_hp:
                    candidate_ids = by_hp

            if len(candidate_ids) > 1:
                by_traits = [
                    opp_id
                    for opp_id in candidate_ids
                    if round_rows[opp_id]["traits"] == row["opponent_traits"]
                ]
                if by_traits:
                    candidate_ids = by_traits

            inferred_opponent = candidate_ids[0] if len(candidate_ids) == 1 else None
            if inferred_opponent is not None:
                inference = "exact"
            elif candidate_ids:
                inference = "ambiguous"
            else:
                inference = "unresolved"

            context_map[(round_num, player_id)] = {
                "inferred_opponent_id": inferred_opponent,
                "opponent_candidates": candidate_ids,
                "opponent_candidates_by_units": candidates_by_units,
                "matchup_inference": inference,
                "player_units_mirrored": _mirror_units_signature(row["units"]),
                "opponent_units_mirrored": _mirror_units_signature(row["opponent_units"]),
            }

    return context_map


def _summarize_row_context(
    row: Dict[str, Any] | None,
    context: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    if row is None:
        return None

    player_units = row["units"]
    opponent_units = row["opponent_units"]
    return {
        "inferred_opponent_id": context.get("inferred_opponent_id")
        if context is not None
        else None,
        "matchup_inference": context.get("matchup_inference") if context is not None else "missing",
        "opponent_candidates": context.get("opponent_candidates", [])
        if context is not None
        else [],
        "opponent_candidates_by_units": (
            context.get("opponent_candidates_by_units", []) if context is not None else []
        ),
        "player_units": player_units,
        "player_units_mirrored": (
            context.get("player_units_mirrored")
            if context is not None
            else _mirror_units_signature(player_units)
        ),
        "opponent_units": opponent_units,
        "opponent_units_mirrored": (
            context.get("opponent_units_mirrored")
            if context is not None
            else _mirror_units_signature(opponent_units)
        ),
    }


def _infer_divergence_origin(
    baseline_row: Dict[str, Any] | None,
    candidate_row: Dict[str, Any] | None,
    baseline_context: Dict[str, Any] | None,
    candidate_context: Dict[str, Any] | None,
    field_diffs: List[Dict[str, Any]] | None,
    baseline_combat_debug: Dict[str, Any] | None = None,
    candidate_combat_debug: Dict[str, Any] | None = None,
) -> str:
    if baseline_row is None or candidate_row is None:
        return "matchmaking_or_snapshot_presence"

    baseline_opponent_id = (
        baseline_context.get("inferred_opponent_id") if baseline_context is not None else None
    )
    candidate_opponent_id = (
        candidate_context.get("inferred_opponent_id") if candidate_context is not None else None
    )
    if (
        baseline_opponent_id is not None
        and candidate_opponent_id is not None
        and baseline_opponent_id != candidate_opponent_id
    ):
        return "matchmaking"

    baseline_opponents = baseline_row["opponent_units"]
    candidate_opponents = candidate_row["opponent_units"]
    if baseline_opponents != candidate_opponents:
        if _mirror_units_signature(baseline_opponents) == candidate_opponents:
            return "board_transform"
        if _mirror_units_signature(candidate_opponents) == baseline_opponents:
            return "board_transform"
        if baseline_opponent_id is None or candidate_opponent_id is None:
            return "matchmaking_or_board_state"

    diff_fields = {diff["field"] for diff in (field_diffs or [])}
    combat_fields = {"combat_result", "damage_dealt", "damage_taken"}
    downstream_combat_fields = {
        "hp",
        "opponent_hp",
        "streak",
        "win_streak",
        "loss_streak",
        "alive_count",
    }
    if baseline_combat_debug is not None and candidate_combat_debug is not None:
        baseline_last_hit = tuple(
            tuple(item) for item in baseline_combat_debug.get("player_last_hit_signature", ())
        )
        candidate_last_hit = tuple(
            tuple(item) for item in candidate_combat_debug.get("player_last_hit_signature", ())
        )
        baseline_has_last_hit = bool(baseline_last_hit)
        candidate_has_last_hit = bool(candidate_last_hit)
        if (
            baseline_has_last_hit
            and candidate_has_last_hit
            and baseline_last_hit != candidate_last_hit
            and diff_fields
            and diff_fields.issubset(combat_fields | downstream_combat_fields)
        ):
            return "last_hit_attribution_drift"

    if not diff_fields:
        return "unknown"

    if diff_fields.issubset(combat_fields):
        return "combat_resolution"
    if diff_fields.issubset(combat_fields | downstream_combat_fields):
        return "combat_resolution_or_downstream"

    return "unknown"


def _build_divergence_context(
    baseline_row: Dict[str, Any] | None,
    candidate_row: Dict[str, Any] | None,
    baseline_context: Dict[str, Any] | None,
    candidate_context: Dict[str, Any] | None,
    field_diffs: List[Dict[str, Any]] | None,
    baseline_combat_debug: Dict[str, Any] | None = None,
    candidate_combat_debug: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    baseline_summary = _summarize_row_context(baseline_row, baseline_context)
    candidate_summary = _summarize_row_context(candidate_row, candidate_context)

    matchup_alignment = "unknown"
    if baseline_context is not None and candidate_context is not None:
        baseline_opponent = baseline_context.get("inferred_opponent_id")
        candidate_opponent = candidate_context.get("inferred_opponent_id")
        if baseline_opponent is not None and candidate_opponent is not None:
            matchup_alignment = (
                "same_inferred_opponent"
                if baseline_opponent == candidate_opponent
                else "different_inferred_opponent"
            )
        elif baseline_context.get("opponent_candidates_by_units") == candidate_context.get(
            "opponent_candidates_by_units"
        ):
            matchup_alignment = "same_matchup_candidates"

    baseline_equals_candidate_mirrored = False
    candidate_equals_baseline_mirrored = False
    mirror_alignment = "unknown"
    if baseline_row is not None and candidate_row is not None:
        baseline_opponents = baseline_row["opponent_units"]
        candidate_opponents = candidate_row["opponent_units"]
        baseline_equals_candidate_mirrored = baseline_opponents == _mirror_units_signature(
            candidate_opponents
        )
        candidate_equals_baseline_mirrored = candidate_opponents == _mirror_units_signature(
            baseline_opponents
        )

        if baseline_opponents == candidate_opponents:
            mirror_alignment = "same_positions"
        elif baseline_equals_candidate_mirrored or candidate_equals_baseline_mirrored:
            mirror_alignment = "mirrored_positions"
        else:
            mirror_alignment = "different_positions"

    origin_hint = _infer_divergence_origin(
        baseline_row=baseline_row,
        candidate_row=candidate_row,
        baseline_context=baseline_context,
        candidate_context=candidate_context,
        field_diffs=field_diffs,
        baseline_combat_debug=baseline_combat_debug,
        candidate_combat_debug=candidate_combat_debug,
    )
    last_hit_alignment = "missing"
    if baseline_combat_debug is not None and candidate_combat_debug is not None:
        baseline_sig = tuple(
            tuple(item) for item in baseline_combat_debug.get("player_last_hit_signature", ())
        )
        candidate_sig = tuple(
            tuple(item) for item in candidate_combat_debug.get("player_last_hit_signature", ())
        )
        last_hit_alignment = (
            "same_last_hit_signature"
            if baseline_sig == candidate_sig
            else "different_last_hit_signature"
        )
    elif baseline_combat_debug is not None:
        last_hit_alignment = "missing_candidate_debug"
    elif candidate_combat_debug is not None:
        last_hit_alignment = "missing_baseline_debug"

    return {
        "origin_hint": origin_hint,
        "matchup_alignment": matchup_alignment,
        "mirror_alignment": mirror_alignment,
        "last_hit_alignment": last_hit_alignment,
        "baseline_equals_candidate_mirrored": baseline_equals_candidate_mirrored,
        "candidate_equals_baseline_mirrored": candidate_equals_baseline_mirrored,
        "baseline": baseline_summary,
        "candidate": candidate_summary,
        "baseline_combat_debug": baseline_combat_debug,
        "candidate_combat_debug": candidate_combat_debug,
    }


def run_parity_dump_seed(
    baseline_engine: str,
    candidate_engine: str,
    seed: int,
    sample_limit: int = 20,
    output_path: str | None = None,
    parity_dump_signatures_only: bool = False,
) -> Dict[str, Any]:
    print()
    print("=" * 60)
    print("PARITY DUMP (SINGLE SEED)")
    print("=" * 60)
    print(f"Seed:             {seed}")
    print(f"Baseline engine:  {baseline_engine}")
    print(f"Candidate engine: {candidate_engine}")
    print(f"Signatures only:  {'yes' if parity_dump_signatures_only else 'no'}")
    print()

    rust_sim_cache: Dict[str, Any] = {}
    baseline = _run_single_full_game_with_rows(baseline_engine, seed, rust_sim_cache)
    candidate = _run_single_full_game_with_rows(candidate_engine, seed, rust_sim_cache)

    baseline_rows = _rows_by_round_player(baseline["training_rows"])
    candidate_rows = _rows_by_round_player(candidate["training_rows"])
    baseline_matchup_context = _build_matchup_context_map(baseline_rows)
    candidate_matchup_context = _build_matchup_context_map(candidate_rows)
    include_raw_takedowns = not parity_dump_signatures_only
    baseline_combat_debug = _build_combat_debug_context_by_key(
        baseline.get("combat_debug", []) or [],
        include_raw_takedowns=include_raw_takedowns,
    )
    candidate_combat_debug = _build_combat_debug_context_by_key(
        candidate.get("combat_debug", []) or [],
        include_raw_takedowns=include_raw_takedowns,
    )
    keys = sorted(set(baseline_rows.keys()) | set(candidate_rows.keys()))

    compare_fields = (
        "hp",
        "gold",
        "level",
        "streak",
        "board_count",
        "win_streak",
        "loss_streak",
        "num_augments",
        "num_traits",
        "alive_count",
        "combat_result",
        "damage_dealt",
        "damage_taken",
        "opponent_hp",
        "traits",
        "opponent_traits",
        "augments",
        "units",
        "opponent_units",
    )
    float_fields = {"damage_dealt", "damage_taken"}

    first_divergence: Dict[str, Any] | None = None
    divergence_count = 0
    sampled_divergences: List[Dict[str, Any]] = []
    missing_baseline = 0
    missing_candidate = 0
    divergence_origin_counts: Counter[str] = Counter()

    for key in keys:
        baseline_row = baseline_rows.get(key)
        candidate_row = candidate_rows.get(key)
        baseline_context = baseline_matchup_context.get(key)
        candidate_context = candidate_matchup_context.get(key)
        baseline_debug_context = baseline_combat_debug.get(key)
        candidate_debug_context = candidate_combat_debug.get(key)

        if baseline_row is None:
            missing_baseline += 1
            divergence_context = _build_divergence_context(
                baseline_row=None,
                candidate_row=candidate_row,
                baseline_context=None,
                candidate_context=candidate_context,
                field_diffs=None,
                baseline_combat_debug=None,
                candidate_combat_debug=candidate_debug_context,
            )
            divergence = {
                "round": key[0],
                "player_id": key[1],
                "type": "missing_baseline_snapshot",
                "baseline": None,
                "candidate": candidate_row,
                "origin_hint": divergence_context["origin_hint"],
                "context": divergence_context,
            }
        elif candidate_row is None:
            missing_candidate += 1
            divergence_context = _build_divergence_context(
                baseline_row=baseline_row,
                candidate_row=None,
                baseline_context=baseline_context,
                candidate_context=None,
                field_diffs=None,
                baseline_combat_debug=baseline_debug_context,
                candidate_combat_debug=None,
            )
            divergence = {
                "round": key[0],
                "player_id": key[1],
                "type": "missing_candidate_snapshot",
                "baseline": baseline_row,
                "candidate": None,
                "origin_hint": divergence_context["origin_hint"],
                "context": divergence_context,
            }
        else:
            field_diffs: List[Dict[str, Any]] = []
            for field in compare_fields:
                bval = baseline_row[field]
                cval = candidate_row[field]
                if field in float_fields:
                    if abs(float(bval) - float(cval)) <= 1e-6:
                        continue
                elif bval == cval:
                    continue
                field_diffs.append(
                    {
                        "field": field,
                        "baseline": bval,
                        "candidate": cval,
                    }
                )

            if not field_diffs:
                continue
            divergence_context = _build_divergence_context(
                baseline_row=baseline_row,
                candidate_row=candidate_row,
                baseline_context=baseline_context,
                candidate_context=candidate_context,
                field_diffs=field_diffs,
                baseline_combat_debug=baseline_debug_context,
                candidate_combat_debug=candidate_debug_context,
            )
            divergence = {
                "round": key[0],
                "player_id": key[1],
                "type": "snapshot_mismatch",
                "field_diffs": field_diffs,
                "origin_hint": divergence_context["origin_hint"],
                "context": divergence_context,
            }

        divergence_count += 1
        divergence_origin_counts[divergence["origin_hint"]] += 1
        if first_divergence is None:
            first_divergence = divergence
        if len(sampled_divergences) < sample_limit:
            sampled_divergences.append(divergence)

    placement_match = baseline["placement_vector"] == candidate["placement_vector"]
    round_match = baseline["round_num"] == candidate["round_num"]

    print(f"  Placement vectors match: {'yes' if placement_match else 'no'}")
    print(f"  Round count match:       {'yes' if round_match else 'no'}")
    print(f"  Baseline round-rows:     {len(baseline_rows)}")
    print(f"  Candidate round-rows:    {len(candidate_rows)}")
    print(f"  Total snapshot diffs:    {divergence_count}")
    if first_divergence is None:
        print("  First divergence:        none")
    else:
        print(
            "  First divergence:        "
            f"round={first_divergence['round']} player={first_divergence['player_id']} "
            f"origin={first_divergence.get('origin_hint', 'unknown')}"
        )
    if divergence_origin_counts:
        print(f"  Divergence origins:      {dict(divergence_origin_counts)}")
    print()

    payload = {
        "seed": seed,
        "baseline_engine": baseline_engine,
        "candidate_engine": candidate_engine,
        "placement_vector_match": placement_match,
        "round_count_match": round_match,
        "baseline": {
            "round_num": baseline["round_num"],
            "placements": baseline["placements"],
            "placement_vector": baseline["placement_vector"],
            "rank_order": baseline["rank_order"],
            "top4_set": baseline["top4_set"],
            "row_count": len(baseline_rows),
        },
        "candidate": {
            "round_num": candidate["round_num"],
            "placements": candidate["placements"],
            "placement_vector": candidate["placement_vector"],
            "rank_order": candidate["rank_order"],
            "top4_set": candidate["top4_set"],
            "row_count": len(candidate_rows),
        },
        "snapshot_key_count": len(keys),
        "missing_baseline_snapshots": missing_baseline,
        "missing_candidate_snapshots": missing_candidate,
        "divergence_count": divergence_count,
        "divergence_origin_counts": dict(divergence_origin_counts),
        "parity_dump_signatures_only": parity_dump_signatures_only,
        "first_divergence": first_divergence,
        "divergence_samples": sampled_divergences,
    }

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  Saved parity dump: {output_file}")
        print()

    return payload


def _get_combat_engine(engine_name: str, engine_cache: Dict[str, Any]) -> Any:
    cache_key = f"combat::{engine_name}"
    engine = engine_cache.get(cache_key)
    if engine is None:
        engine = _create_engine(engine_name)
        engine_cache[cache_key] = engine
    return engine


def _run_combat_parity_layer(
    layer_name: str,
    baseline_engine: str,
    candidate_engine: str,
    num_sims: int,
    seed_start: int,
    sample_limit: int,
    team_builder: Any,
    engine_cache: Dict[str, Any],
) -> Dict[str, Any]:
    print(f"{layer_name}: {num_sims} sims ({seed_start}..{seed_start + num_sims - 1})")
    progress_every = max(1, num_sims // 10)

    winner_matches = 0
    mismatch_samples: List[Dict[str, Any]] = []
    baseline_elapsed = 0.0
    candidate_elapsed = 0.0
    baseline_timeouts = 0
    candidate_timeouts = 0
    mismatch_with_candidate_timeout = 0

    baseline_combat = _get_combat_engine(baseline_engine, engine_cache)
    candidate_combat = _get_combat_engine(candidate_engine, engine_cache)

    for i in range(num_sims):
        seed = seed_start + i
        team0_b, team1_b = team_builder(baseline_combat, baseline_engine)
        team0_c, team1_c = team_builder(candidate_combat, candidate_engine)

        start = time.perf_counter()
        baseline_result = _normalize_result(
            _run_combat(baseline_combat, baseline_engine, team0_b, team1_b, seed=seed)
        )
        baseline_elapsed += time.perf_counter() - start

        start = time.perf_counter()
        candidate_result = _normalize_result(
            _run_combat(candidate_combat, candidate_engine, team0_c, team1_c, seed=seed)
        )
        candidate_elapsed += time.perf_counter() - start

        baseline_timed_out = baseline_result["combat_time"] >= 59.99
        candidate_timed_out = candidate_result["combat_time"] >= 59.99
        if baseline_timed_out:
            baseline_timeouts += 1
        if candidate_timed_out:
            candidate_timeouts += 1

        winner_match = baseline_result["winner"] == candidate_result["winner"]
        if winner_match:
            winner_matches += 1
        elif candidate_timed_out:
            mismatch_with_candidate_timeout += 1
        elif len(mismatch_samples) < sample_limit:
            mismatch_samples.append(
                {
                    "seed": seed,
                    "baseline": baseline_result,
                    "candidate": candidate_result,
                }
            )

        done = i + 1
        if done % progress_every == 0 or done == num_sims:
            print(f"  [{done}/{num_sims}] complete")

    winner_match_rate = winner_matches / max(1, num_sims)
    baseline_timeout_rate = baseline_timeouts / max(1, num_sims)
    candidate_timeout_rate = candidate_timeouts / max(1, num_sims)
    mismatch_total = num_sims - winner_matches
    mismatch_timeout_share = (
        mismatch_with_candidate_timeout / mismatch_total if mismatch_total > 0 else 0.0
    )
    print(f"  Winner match rate: {winner_match_rate:.2%}")
    print(
        f"  Timeout rate ({baseline_engine}/{candidate_engine}): "
        f"{baseline_timeout_rate:.2%}/{candidate_timeout_rate:.2%}"
    )
    print(f"  Mismatch share with candidate timeout: {mismatch_timeout_share:.2%}")
    print(
        f"  Throughput ({baseline_engine}/{candidate_engine}): "
        f"{(num_sims / baseline_elapsed) if baseline_elapsed > 0 else 0.0:.2f}/"
        f"{(num_sims / candidate_elapsed) if candidate_elapsed > 0 else 0.0:.2f} sims/sec"
    )
    print()

    return {
        "layer": layer_name,
        "num_sims": num_sims,
        "seed_start": seed_start,
        "seed_end": seed_start + num_sims - 1,
        "winner_match_rate": round(winner_match_rate, 4),
        "baseline_timeout_rate": round(baseline_timeout_rate, 4),
        "candidate_timeout_rate": round(candidate_timeout_rate, 4),
        "mismatch_candidate_timeout_share": round(mismatch_timeout_share, 4),
        "baseline_sims_per_sec": round(
            (num_sims / baseline_elapsed) if baseline_elapsed > 0 else 0.0, 4
        ),
        "candidate_sims_per_sec": round(
            (num_sims / candidate_elapsed) if candidate_elapsed > 0 else 0.0, 4
        ),
        "mismatch_samples": mismatch_samples,
    }


def run_layered_parity_harness(
    baseline_engine: str,
    candidate_engine: str,
    layer1_sims: int = 1000,
    layer2_sims: int = 1000,
    layer3_games: int = 100,
    seed_start: int = 0,
    sample_limit: int = 10,
) -> Dict[str, Any]:
    print()
    print("=" * 60)
    print("LAYERED PARITY HARNESS")
    print("=" * 60)
    print(f"Baseline engine:  {baseline_engine}")
    print(f"Candidate engine: {candidate_engine}")
    print()

    combat_engine_cache: Dict[str, Any] = {}
    layer1 = _run_combat_parity_layer(
        layer_name="Layer 1 (1v1)",
        baseline_engine=baseline_engine,
        candidate_engine=candidate_engine,
        num_sims=layer1_sims,
        seed_start=seed_start,
        sample_limit=sample_limit,
        team_builder=_build_duel_teams,
        engine_cache=combat_engine_cache,
    )
    layer2 = _run_combat_parity_layer(
        layer_name="Layer 2 (8v8 Team Combat)",
        baseline_engine=baseline_engine,
        candidate_engine=candidate_engine,
        num_sims=layer2_sims,
        seed_start=seed_start,
        sample_limit=sample_limit,
        team_builder=_build_teamfight_teams_8v8,
        engine_cache=combat_engine_cache,
    )
    layer3 = run_seed_parity_harness(
        baseline_engine=baseline_engine,
        candidate_engine=candidate_engine,
        num_games=layer3_games,
        seed_start=seed_start,
        sample_limit=sample_limit,
    )

    return {
        "baseline_engine": baseline_engine,
        "candidate_engine": candidate_engine,
        "layer1_1v1": layer1,
        "layer2_team_combat": layer2,
        "layer3_full_game": layer3,
    }


def run_focused_combat_parity_suite(
    baseline_engine: str,
    candidate_engine: str,
    sims_per_case: int = 200,
    seed_start: int = 0,
    sample_limit: int = 10,
) -> Dict[str, Any]:
    print()
    print("=" * 60)
    print("FOCUSED CHAMPION PARITY SUITE")
    print("=" * 60)
    print(f"Baseline engine:  {baseline_engine}")
    print(f"Candidate engine: {candidate_engine}")
    print(f"Sims per case:    {sims_per_case}")
    print()

    scenarios = [
        ("Draven vs Leona", _build_focus_case_draven_vs_leona),
        ("Sion vs Draven", _build_focus_case_sion_vs_draven),
        ("4v4 Mixed Board", _build_teamfight_teams),
    ]

    combat_engine_cache: Dict[str, Any] = {}
    case_results: Dict[str, Dict[str, Any]] = {}
    winner_rates: List[float] = []
    worst_case_name = ""
    worst_case_rate = 1.0

    for idx, (name, team_builder) in enumerate(scenarios):
        case_seed_start = seed_start + idx * max(1_000_000, sims_per_case)
        case_result = _run_combat_parity_layer(
            layer_name=f"Focused: {name}",
            baseline_engine=baseline_engine,
            candidate_engine=candidate_engine,
            num_sims=sims_per_case,
            seed_start=case_seed_start,
            sample_limit=sample_limit,
            team_builder=team_builder,
            engine_cache=combat_engine_cache,
        )
        case_results[name] = case_result
        rate = float(case_result["winner_match_rate"])
        winner_rates.append(rate)
        if rate < worst_case_rate:
            worst_case_rate = rate
            worst_case_name = name

    mean_rate = statistics.mean(winner_rates) if winner_rates else 0.0
    print("Focused parity summary:")
    print(f"  Mean winner-match rate: {mean_rate:.2%}")
    print(f"  Worst case:             {worst_case_name} ({worst_case_rate:.2%})")
    print()

    return {
        "baseline_engine": baseline_engine,
        "candidate_engine": candidate_engine,
        "sims_per_case": sims_per_case,
        "mean_winner_match_rate": round(mean_rate, 4),
        "worst_case_name": worst_case_name,
        "worst_case_winner_match_rate": round(worst_case_rate, 4),
        "cases": case_results,
    }


def enforce_parity_gate(
    layered_result: Dict[str, Any] | None,
    focused_result: Dict[str, Any] | None,
    min_layer1_match: float,
    min_layer2_match: float,
    max_layer2_timeout: float,
    min_focused_mean: float,
    min_focused_case: float,
) -> None:
    failures: List[str] = []

    if layered_result is not None:
        layer1 = layered_result.get("layer1_1v1", {})
        layer2 = layered_result.get("layer2_team_combat", {})

        layer1_rate = float(layer1.get("winner_match_rate", 0.0))
        layer2_rate = float(layer2.get("winner_match_rate", 0.0))
        layer2_timeout = float(layer2.get("candidate_timeout_rate", 1.0))

        if layer1_rate < min_layer1_match:
            failures.append(
                f"Layer1 winner-match {layer1_rate:.4f} < required {min_layer1_match:.4f}"
            )
        if layer2_rate < min_layer2_match:
            failures.append(
                f"Layer2 winner-match {layer2_rate:.4f} < required {min_layer2_match:.4f}"
            )
        if layer2_timeout > max_layer2_timeout:
            failures.append(
                f"Layer2 candidate-timeout {layer2_timeout:.4f} > allowed {max_layer2_timeout:.4f}"
            )

    if focused_result is not None:
        focused_mean = float(focused_result.get("mean_winner_match_rate", 0.0))
        focused_case = float(focused_result.get("worst_case_winner_match_rate", 0.0))

        if focused_mean < min_focused_mean:
            failures.append(
                f"Focused mean winner-match {focused_mean:.4f} < required {min_focused_mean:.4f}"
            )
        if focused_case < min_focused_case:
            failures.append(
                f"Focused worst-case winner-match {focused_case:.4f} < required {min_focused_case:.4f}"
            )

    if failures:
        print("=" * 60)
        print("PARITY GATE FAILED")
        print("=" * 60)
        for failure in failures:
            print(f"  - {failure}")
        print()
        raise SystemExit(1)

    print("=" * 60)
    print("PARITY GATE PASSED")
    print("=" * 60)
    print()


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

        placement_match = baseline["placement_vector"] == candidate["placement_vector"]
        rank_match = baseline["rank_order"] == candidate["rank_order"]
        top4_match = baseline["top4_set"] == candidate["top4_set"]
        round_match = baseline["round_num"] == candidate["round_num"]

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
            for a, b in zip(
                baseline["placement_vector"], candidate["placement_vector"], strict=True
            )
        )
        total_l1 += l1
        round_delta = abs(int(baseline["round_num"]) - int(candidate["round_num"]))
        round_abs_deltas.append(round_delta)

        if (not placement_match or not round_match) and len(mismatch_samples) < sample_limit:
            mismatch_samples.append(
                {
                    "seed": seed,
                    "baseline": {
                        "placements": baseline["placements"],
                        "round_num": baseline["round_num"],
                    },
                    "candidate": {
                        "placements": candidate["placements"],
                        "round_num": candidate["round_num"],
                    },
                    "placement_l1": l1,
                    "round_abs_delta": round_delta,
                }
            )

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
        "baseline_engine": baseline_engine,
        "candidate_engine": candidate_engine,
        "num_games": num_games,
        "seed_start": seed_start,
        "seed_end": seed_start + num_games - 1,
        "placement_vector_match_rate": round(placement_match_rate, 4),
        "rank_order_match_rate": round(rank_match_rate, 4),
        "top4_set_match_rate": round(top4_match_rate, 4),
        "round_match_rate": round(round_match_rate, 4),
        "mean_placement_l1_delta": round(avg_l1, 4),
        "mean_round_abs_delta": round(float(round_mean_abs_delta), 4),
        "max_round_abs_delta": int(round_max_abs_delta),
        "baseline_games_per_sec": round(
            (num_games / baseline_time) if baseline_time > 0 else 0.0, 4
        ),
        "candidate_games_per_sec": round(
            (num_games / candidate_time) if candidate_time > 0 else 0.0, 4
        ),
        "mismatch_samples": mismatch_samples,
    }


def run_full_benchmark(
    engine_name: str = "python",
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
    if engine_name == "python":
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
    if det_1v1["deterministic"]:
        print(f"  [PASS] - All {det_1v1['num_runs']} runs identical")
    else:
        print(f"  [FAIL] - {det_1v1['num_differences']} runs differed!")
        print(f"  First difference: {det_1v1['first_difference']}")

    print(f"\nTeam Combat Determinism ({det_team_runs} runs, same seed)...")
    det_team = test_determinism_team_combat(engine, engine_name, det_team_runs)
    if det_team["deterministic"]:
        print(f"  [PASS] - All {det_team['num_runs']} runs identical")
    else:
        print(f"  [FAIL] - {det_team['num_differences']} runs differed!")

    print(f"\nFull Game Determinism ({det_game_runs} runs, same seed)...")
    det_game = test_determinism_full_game(engine_name=engine_name, num_runs=det_game_runs)
    if det_game["deterministic"]:
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
        "engine": engine_name,
        "load_time": load_time,
        "benchmark_1v1": bench_1v1,
        "benchmark_team": bench_team,
        "benchmark_game": bench_game,
        "determinism_1v1": det_1v1,
        "determinism_team": det_team,
        "determinism_game": det_game,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark TFT python/rust combat engines")
    parser.add_argument(
        "--engine",
        choices=["python", "rust", "rust_full", "both"],
        default="python",
        help="Engine backend to benchmark (default: python)",
    )
    parser.add_argument("--sims-1v1", type=int, default=1000, help="1v1 benchmark simulation count")
    parser.add_argument(
        "--sims-team", type=int, default=100, help="Team benchmark simulation count"
    )
    parser.add_argument("--games", type=int, default=5, help="Full-game benchmark count")
    parser.add_argument("--det-1v1", type=int, default=100, help="1v1 determinism run count")
    parser.add_argument("--det-team", type=int, default=50, help="Team determinism run count")
    parser.add_argument("--det-games", type=int, default=5, help="Full-game determinism run count")
    parser.add_argument(
        "--compare-games",
        type=int,
        default=0,
        help="Phase 6: run cross-engine distribution comparison with this many games per engine",
    )
    parser.add_argument(
        "--compare-seed-start",
        type=int,
        default=0,
        help="Starting seed for Phase 6 distribution comparison",
    )
    parser.add_argument(
        "--parity-only",
        action="store_true",
        help="Skip throughput/determinism benchmarks and run parity checks only",
    )
    parser.add_argument(
        "--parity-games",
        type=int,
        default=0,
        help="Run seed-level parity harness with this many games (0 disables)",
    )
    parser.add_argument(
        "--parity-seed-start",
        type=int,
        default=0,
        help="Starting seed for parity harness",
    )
    parser.add_argument(
        "--parity-engines",
        type=str,
        default="python,rust_full",
        help="Comma-separated engine pair for parity harness, e.g. python,rust_full",
    )
    parser.add_argument(
        "--parity-sample-limit",
        type=int,
        default=10,
        help="Maximum mismatch samples to include in parity output",
    )
    parser.add_argument(
        "--parity-layered",
        action="store_true",
        help="Run layered parity harness (1v1, 8v8 combat, full game)",
    )
    parser.add_argument(
        "--parity-layer1-sims",
        type=int,
        default=1000,
        help="Layered parity: number of 1v1 combat simulations",
    )
    parser.add_argument(
        "--parity-layer2-sims",
        type=int,
        default=1000,
        help="Layered parity: number of 8v8 team combat simulations",
    )
    parser.add_argument(
        "--parity-layer3-games",
        type=int,
        default=100,
        help="Layered parity: number of full-game comparisons",
    )
    parser.add_argument(
        "--parity-focused",
        action="store_true",
        help="Run focused champion parity suite (targeted combat cases)",
    )
    parser.add_argument(
        "--parity-focused-sims",
        type=int,
        default=200,
        help="Focused parity: simulations per champion scenario",
    )
    parser.add_argument(
        "--parity-dump-seed",
        type=int,
        default=None,
        help="Run single-seed full-game parity dump with first divergence details",
    )
    parser.add_argument(
        "--parity-dump-max-diffs",
        type=int,
        default=20,
        help="Maximum divergence entries to retain in parity dump output",
    )
    parser.add_argument(
        "--parity-dump-output",
        type=str,
        default="",
        help="Optional output path for parity dump JSON payload",
    )
    parser.add_argument(
        "--parity-dump-signatures-only",
        action="store_true",
        help="Parity dump: keep takedown signatures only (omit raw debug_takedowns event lists)",
    )
    parser.add_argument(
        "--parity-gate",
        action="store_true",
        help="Fail with non-zero exit when parity thresholds are not met",
    )
    parser.add_argument(
        "--parity-gate-min-layer1-match",
        type=float,
        default=0.55,
        help="Parity gate: minimum Layer1 winner-match rate",
    )
    parser.add_argument(
        "--parity-gate-min-layer2-match",
        type=float,
        default=0.70,
        help="Parity gate: minimum Layer2 winner-match rate",
    )
    parser.add_argument(
        "--parity-gate-max-layer2-timeout",
        type=float,
        default=0.40,
        help="Parity gate: maximum Layer2 candidate timeout rate",
    )
    parser.add_argument(
        "--parity-gate-min-focused-mean",
        type=float,
        default=0.60,
        help="Parity gate: minimum focused-suite mean winner-match rate",
    )
    parser.add_argument(
        "--parity-gate-min-focused-case",
        type=float,
        default=0.45,
        help="Parity gate: minimum focused-suite worst-case winner-match rate",
    )
    args = parser.parse_args()

    if args.compare_games < 0:
        parser.error("--compare-games must be >= 0")
    if not args.parity_only:
        for field in (
            "sims_1v1",
            "sims_team",
            "games",
            "det_1v1",
            "det_team",
            "det_games",
        ):
            if getattr(args, field) <= 0:
                parser.error(f"--{field.replace('_', '-')} must be > 0")
        if args.compare_games > 0 and args.engine != "both":
            parser.error("--compare-games requires --engine both")
    elif args.compare_games > 0:
        parser.error("--compare-games cannot be used with --parity-only")
    if args.parity_games < 0:
        parser.error("--parity-games must be >= 0")
    if args.parity_sample_limit <= 0:
        parser.error("--parity-sample-limit must be > 0")
    if args.parity_layer1_sims <= 0:
        parser.error("--parity-layer1-sims must be > 0")
    if args.parity_layer2_sims <= 0:
        parser.error("--parity-layer2-sims must be > 0")
    if args.parity_layer3_games <= 0:
        parser.error("--parity-layer3-games must be > 0")
    if args.parity_focused_sims <= 0:
        parser.error("--parity-focused-sims must be > 0")
    if args.parity_dump_seed is not None and args.parity_dump_seed < 0:
        parser.error("--parity-dump-seed must be >= 0")
    if args.parity_dump_max_diffs <= 0:
        parser.error("--parity-dump-max-diffs must be > 0")
    for field in (
        "parity_gate_min_layer1_match",
        "parity_gate_min_layer2_match",
        "parity_gate_max_layer2_timeout",
        "parity_gate_min_focused_mean",
        "parity_gate_min_focused_case",
    ):
        value = float(getattr(args, field))
        if value < 0.0 or value > 1.0:
            parser.error(f"--{field.replace('_', '-')} must be in [0, 1]")
    parsed_parity_engines = [
        value.strip() for value in args.parity_engines.split(",") if value.strip()
    ]
    parity_requested = (
        args.parity_games > 0
        or args.parity_layered
        or args.parity_focused
        or args.parity_dump_seed is not None
    )
    if args.parity_only and not parity_requested:
        parser.error(
            "--parity-only requires at least one parity check "
            "(--parity-games, --parity-layered, --parity-focused, or --parity-dump-seed)"
        )
    if parity_requested:
        valid_engines = {"python", "rust", "rust_full"}
        if len(parsed_parity_engines) != 2:
            parser.error("--parity-engines must provide exactly two engines")
        if parsed_parity_engines[0] == parsed_parity_engines[1]:
            parser.error("--parity-engines must contain two different engines")
        for engine_name in parsed_parity_engines:
            if engine_name not in valid_engines:
                parser.error(f"Unknown parity engine '{engine_name}'")
    if args.parity_gate and not (args.parity_layered or args.parity_focused):
        parser.error("--parity-gate requires --parity-layered and/or --parity-focused")
    args.parity_engine_pair = parsed_parity_engines
    return args


def main() -> Dict[str, Any]:
    args = _parse_args()
    layered_result: Dict[str, Any] | None = None
    focused_result: Dict[str, Any] | None = None

    results: Dict[str, Any]
    if args.parity_only:
        print("=" * 60)
        print("PARITY-ONLY MODE")
        print("=" * 60)
        print("Skipping throughput and determinism benchmark sections.")
        print()
        results = {
            "mode": "parity_only",
            "parity_engine_pair": args.parity_engine_pair,
        }
    elif args.engine == "both":
        python_results = run_full_benchmark(
            engine_name="python",
            sims_1v1=args.sims_1v1,
            sims_team=args.sims_team,
            full_games=args.games,
            det_1v1_runs=args.det_1v1,
            det_team_runs=args.det_team,
            det_game_runs=args.det_games,
        )
        rust_results = run_full_benchmark(
            engine_name="rust",
            sims_1v1=args.sims_1v1,
            sims_team=args.sims_team,
            full_games=args.games,
            det_1v1_runs=args.det_1v1,
            det_team_runs=args.det_team,
            det_game_runs=args.det_games,
        )
        results: Dict[str, Any] = {"python": python_results, "rust": rust_results}

        python_avg = python_results["benchmark_game"]["avg_sec_per_game"]
        rust_avg = rust_results["benchmark_game"]["avg_sec_per_game"]
        speedup = (python_avg / rust_avg) if rust_avg > 0 else float("inf")

        print("=" * 60)
        print("CROSS-ENGINE BENCHMARK SUMMARY")
        print("=" * 60)
        print(f"Python avg full-game time: {python_avg:.3f}s")
        print(f"Rust avg full-game time:   {rust_avg:.3f}s")
        print(f"Rust speedup vs python:    {speedup:.2f}x")
        print()

        if args.compare_games > 0:
            results["distribution_compare"] = run_phase6_distribution_compare(
                num_games=args.compare_games,
                seed_start=args.compare_seed_start,
            )
    else:
        results = run_full_benchmark(
            engine_name=args.engine,
            sims_1v1=args.sims_1v1,
            sims_team=args.sims_team,
            full_games=args.games,
            det_1v1_runs=args.det_1v1,
            det_team_runs=args.det_team,
            det_game_runs=args.det_games,
        )

    if args.parity_games > 0:
        results["parity_harness"] = run_seed_parity_harness(
            baseline_engine=args.parity_engine_pair[0],
            candidate_engine=args.parity_engine_pair[1],
            num_games=args.parity_games,
            seed_start=args.parity_seed_start,
            sample_limit=args.parity_sample_limit,
        )
    if args.parity_layered:
        layered_result = run_layered_parity_harness(
            baseline_engine=args.parity_engine_pair[0],
            candidate_engine=args.parity_engine_pair[1],
            layer1_sims=args.parity_layer1_sims,
            layer2_sims=args.parity_layer2_sims,
            layer3_games=args.parity_layer3_games,
            seed_start=args.parity_seed_start,
            sample_limit=args.parity_sample_limit,
        )
        results["parity_layered"] = layered_result
    if args.parity_focused:
        focused_result = run_focused_combat_parity_suite(
            baseline_engine=args.parity_engine_pair[0],
            candidate_engine=args.parity_engine_pair[1],
            sims_per_case=args.parity_focused_sims,
            seed_start=args.parity_seed_start,
            sample_limit=args.parity_sample_limit,
        )
        results["parity_focused"] = focused_result
    if args.parity_dump_seed is not None:
        results["parity_dump"] = run_parity_dump_seed(
            baseline_engine=args.parity_engine_pair[0],
            candidate_engine=args.parity_engine_pair[1],
            seed=args.parity_dump_seed,
            sample_limit=args.parity_dump_max_diffs,
            output_path=args.parity_dump_output if args.parity_dump_output else None,
            parity_dump_signatures_only=args.parity_dump_signatures_only,
        )

    if args.parity_gate:
        enforce_parity_gate(
            layered_result=layered_result,
            focused_result=focused_result,
            min_layer1_match=args.parity_gate_min_layer1_match,
            min_layer2_match=args.parity_gate_min_layer2_match,
            max_layer2_timeout=args.parity_gate_max_layer2_timeout,
            min_focused_mean=args.parity_gate_min_focused_mean,
            min_focused_case=args.parity_gate_min_focused_case,
        )

    return results


if __name__ == "__main__":
    main()
