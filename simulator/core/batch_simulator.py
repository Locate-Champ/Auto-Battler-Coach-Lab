"""Multiprocessing batch combat simulator.

Runs many combat simulations in parallel across CPU cores for near-linear
speedup on batch workloads (Monte Carlo evaluations, item comparison sweeps,
position optimization).

Usage:
    from simulator.core.batch_simulator import batch_simulate_1v1, batch_run_combats

    # Parallel 1v1 with 1000 sims across 4 workers
    result = batch_simulate_1v1(
        "TFT16_Draven", "TFT16_Leona",
        star1=2, star2=2,
        items1=["InfinityEdge"], items2=["WarmogsArmor"],
        num_simulations=1000, workers=4, seed=42,
    )
"""

import os
import multiprocessing as mp
from typing import List, Dict, Optional, Tuple
from functools import partial


def _worker_simulate_1v1(args: Tuple) -> Dict:
    """Worker function for parallel 1v1 simulation.

    Each worker creates its own CombatEngine to avoid pickle overhead.
    """
    (champ1, champ2, star1, star2, items1, items2,
     augments1, augments2, sim_range_start, sim_count, base_seed, use_fast) = args

    # Import inside worker to avoid pickling the engine
    from simulator.core.combat_engine import CombatEngine
    engine = CombatEngine(logging_enabled=False)

    wins = {champ1: 0, champ2: 0}
    total_damage = {champ1: 0.0, champ2: 0.0}
    abilities_cast = {champ1: 0, champ2: 0}
    combat_times = []

    for i in range(sim_count):
        sim_seed = (base_seed + sim_range_start + i) if base_seed is not None else None
        unit1 = engine.create_unit(champ1, star1, (0, 3), 0, items1)
        unit2 = engine.create_unit(champ2, star2, (3, 3), 1, items2)

        if not unit1 or not unit2:
            continue

        if use_fast:
            result = engine.run_combat_fast(
                [unit1], [unit2],
                team0_augments=augments1,
                team1_augments=augments2,
                seed=sim_seed,
            )
        else:
            result = engine.run_combat(
                [unit1], [unit2],
                team0_augments=augments1,
                team1_augments=augments2,
                seed=sim_seed,
            )

        if result['winner'] == 0:
            wins[champ1] += 1
        else:
            wins[champ2] += 1

        total_damage[champ1] += result['team0_total_damage']
        total_damage[champ2] += result['team1_total_damage']
        abilities_cast[champ1] += result['team0_abilities_cast']
        abilities_cast[champ2] += result['team1_abilities_cast']
        combat_times.append(result['combat_time'])

    return {
        'wins': wins,
        'total_damage': total_damage,
        'abilities_cast': abilities_cast,
        'combat_times': combat_times,
        'count': sim_count,
    }


def batch_simulate_1v1(
    champ1: str,
    champ2: str,
    star1: int = 1,
    star2: int = 1,
    items1: Optional[List[str]] = None,
    items2: Optional[List[str]] = None,
    augments1: Optional[List[str]] = None,
    augments2: Optional[List[str]] = None,
    num_simulations: int = 1000,
    workers: Optional[int] = None,
    seed: Optional[int] = None,
    use_fast: bool = True,
) -> Dict:
    """Run parallel 1v1 simulations across multiple CPU cores.

    Args:
        champ1, champ2: API names of the champions
        star1, star2: Star levels (1-3)
        items1, items2: Item lists for each champion
        augments1, augments2: Augment lists for each team
        num_simulations: Total number of simulations to run
        workers: Number of processes (default: CPU count)
        seed: Base random seed for deterministic results
        use_fast: Use run_combat_fast() with adaptive tick skipping

    Returns:
        Same format as CombatEngine.simulate_1v1()
    """
    if workers is None:
        workers = min(mp.cpu_count(), num_simulations)
    workers = max(1, min(workers, num_simulations))

    # Split simulations across workers
    sims_per_worker = num_simulations // workers
    remainder = num_simulations % workers

    work_items = []
    offset = 0
    for w in range(workers):
        count = sims_per_worker + (1 if w < remainder else 0)
        work_items.append((
            champ1, champ2, star1, star2,
            items1 or [], items2 or [],
            augments1, augments2,
            offset, count, seed, use_fast,
        ))
        offset += count

    # Run in parallel
    if workers == 1:
        # Skip multiprocessing overhead for single worker
        results = [_worker_simulate_1v1(work_items[0])]
    else:
        with mp.Pool(workers) as pool:
            results = pool.map(_worker_simulate_1v1, work_items)

    # Aggregate results
    total_wins = {champ1: 0, champ2: 0}
    total_damage = {champ1: 0.0, champ2: 0.0}
    total_abilities = {champ1: 0, champ2: 0}
    all_times = []

    for r in results:
        for c in [champ1, champ2]:
            total_wins[c] += r['wins'][c]
            total_damage[c] += r['total_damage'][c]
            total_abilities[c] += r['abilities_cast'][c]
        all_times.extend(r['combat_times'])

    n = num_simulations
    return {
        'simulations': n,
        'workers': workers,
        'win_rate': {
            champ1: round(total_wins[champ1] / n * 100, 1),
            champ2: round(total_wins[champ2] / n * 100, 1),
        },
        'avg_damage': {
            champ1: round(total_damage[champ1] / n, 1),
            champ2: round(total_damage[champ2] / n, 1),
        },
        'avg_abilities_cast': {
            champ1: round(total_abilities[champ1] / n, 2),
            champ2: round(total_abilities[champ2] / n, 2),
        },
        'avg_combat_time': round(sum(all_times) / len(all_times), 2) if all_times else 0,
    }


def _worker_run_combat(args: Tuple) -> Dict:
    """Worker function for parallel team combat."""
    (team0_specs, team1_specs, team0_augments, team1_augments,
     sim_seed, use_fast) = args

    from simulator.core.combat_engine import CombatEngine
    engine = CombatEngine(logging_enabled=False)

    team0 = [engine.create_unit(s['api_name'], s['star_level'],
             tuple(s['position']), 0, s.get('items'))
             for s in team0_specs]
    team1 = [engine.create_unit(s['api_name'], s['star_level'],
             tuple(s['position']), 1, s.get('items'))
             for s in team1_specs]

    team0 = [u for u in team0 if u is not None]
    team1 = [u for u in team1 if u is not None]

    if use_fast:
        return engine.run_combat_fast(
            team0, team1,
            team0_augments=team0_augments,
            team1_augments=team1_augments,
            seed=sim_seed,
        )
    else:
        return engine.run_combat(
            team0, team1,
            team0_augments=team0_augments,
            team1_augments=team1_augments,
            seed=sim_seed,
        )


def batch_run_combats(
    scenarios: List[Dict],
    workers: Optional[int] = None,
    use_fast: bool = True,
) -> List[Dict]:
    """Run multiple team combat scenarios in parallel.

    Args:
        scenarios: List of dicts, each with:
            - team0: List of unit spec dicts (api_name, star_level, position, items)
            - team1: Same format
            - team0_augments: Optional augment list
            - team1_augments: Optional augment list
            - seed: Optional int seed
        workers: Number of processes (default: CPU count)
        use_fast: Use adaptive tick skipping

    Returns:
        List of combat result dicts (same order as input scenarios).
    """
    if workers is None:
        workers = min(mp.cpu_count(), len(scenarios))
    workers = max(1, workers)

    work_items = []
    for s in scenarios:
        work_items.append((
            s['team0'], s['team1'],
            s.get('team0_augments'), s.get('team1_augments'),
            s.get('seed'), use_fast,
        ))

    if workers == 1:
        return [_worker_run_combat(w) for w in work_items]

    with mp.Pool(workers) as pool:
        return pool.map(_worker_run_combat, work_items)
