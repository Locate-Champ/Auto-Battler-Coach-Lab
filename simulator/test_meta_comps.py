#!/usr/bin/env python3
"""
Test positioning optimizer with real meta comps from MetaTFT data.

This script:
1. Loads meta comps from data/meta/comps.json
2. Validates unit costs against player level
3. Tests two meta comps against each other
4. Runs positioning optimization on a late-game board
"""

import json
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.combat_engine import CombatEngine
from core.positioning_optimizer import PositioningOptimizer

# TFT Level -> Max units on board
LEVEL_UNIT_SLOTS = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9, 10: 10
}

# Champion cost -> Required level to field (based on shop odds)
# Level at which the champion first appears in shop
COST_MIN_LEVEL = {
    1: 1,   # 1-cost: Available from level 1
    2: 2,   # 2-cost: Available from level 2
    3: 2,   # 3-cost: Available from level 2 (rare)
    4: 5,   # 4-cost: Available from level 5
    5: 7,   # 5-cost: Available from level 7
}


def load_meta_comps(data_path: str = None) -> list:
    """Load meta comps from JSON file."""
    if data_path is None:
        data_path = Path(__file__).parent.parent / "data" / "meta" / "comps.json"

    with open(data_path) as f:
        data = json.load(f)

    return data.get('comps', [])


def get_champion_cost(engine: CombatEngine, champion_id: str) -> int:
    """Get the cost of a champion from combat data."""
    champ_data = engine.champions.get(champion_id, {})
    return champ_data.get('cost', 1)


def validate_comp_for_level(engine: CombatEngine, units: list, player_level: int) -> dict:
    """
    Validate if a comp is legal for a given player level.

    Returns:
        dict with 'valid' bool and 'issues' list
    """
    issues = []

    # Check unit count
    max_units = LEVEL_UNIT_SLOTS.get(player_level, 10)
    if len(units) > max_units:
        issues.append(f"Too many units: {len(units)} > {max_units} (level {player_level})")

    # Check each unit's cost
    for unit_id in units:
        cost = get_champion_cost(engine, unit_id)
        min_level = COST_MIN_LEVEL.get(cost, 1)

        if player_level < min_level:
            issues.append(f"{unit_id} (cost {cost}) requires level {min_level}, have level {player_level}")

    return {
        'valid': len(issues) == 0,
        'issues': issues
    }


def classify_unit_role(engine: CombatEngine, champion_id: str) -> str:
    """
    Classify a unit as 'frontline', 'backline', or 'flexible'.

    Based on:
    - Traits (Defender, Bruiser, Warden = frontline)
    - Range (melee = frontline, ranged = backline)
    - HP pool (high HP = frontline)
    """
    champ_data = engine.champions.get(champion_id, {})
    traits = champ_data.get('traits', [])
    stats = champ_data.get('stats', {})
    range_val = stats.get('range', 1)
    hp = stats.get('hp', 600)

    # Frontline traits (tanks)
    frontline_traits = {'Defender', 'Bruiser', 'Warden', 'Juggernaut', 'Colossus', 'Bastion'}

    # Backline traits (carries/mages)
    backline_traits = {'Gunslinger', 'Longshot', 'Arcanist', 'Invoker', 'Star Forger',
                       'Sorcerer', 'Eternal', 'Sage'}

    # Check traits first
    has_frontline_trait = any(t in frontline_traits for t in traits)
    has_backline_trait = any(t in backline_traits for t in traits)

    if has_frontline_trait and not has_backline_trait:
        return 'frontline'
    if has_backline_trait and not has_frontline_trait:
        return 'backline'

    # Fall back to range + HP
    if range_val <= 1:
        return 'frontline'
    elif range_val >= 4:
        return 'backline'
    elif hp >= 800:  # Tanky unit
        return 'frontline'
    else:
        return 'flexible'


def create_comp_with_positions(engine: CombatEngine, units: list, star_levels: dict = None) -> list:
    """
    Create a comp definition with smart initial positions based on role.

    Args:
        engine: CombatEngine instance
        units: List of champion IDs
        star_levels: Optional dict of champion_id -> star_level (default 2)

    Returns:
        List of unit definitions with champion, star, and position
    """
    star_levels = star_levels or {}

    # Classify units
    frontline = []
    backline = []
    flexible = []

    for unit_id in units:
        role = classify_unit_role(engine, unit_id)
        if role == 'frontline':
            frontline.append(unit_id)
        elif role == 'backline':
            backline.append(unit_id)
        else:
            flexible.append(unit_id)

    # Assign positions
    # Frontline: row 0 (front)
    # Backline: row 3 (back)
    # Flexible: row 1-2 (middle)

    comp = []
    col = 0

    # Place frontline in row 0
    for unit_id in frontline:
        pos = (col % 7, 0)
        comp.append({
            'champion': unit_id,
            'star': star_levels.get(unit_id, 2),
            'items': [],
            'position': pos
        })
        col += 1

    # Place backline in row 3
    col = 0
    for unit_id in backline:
        pos = (col % 7, 3)
        comp.append({
            'champion': unit_id,
            'star': star_levels.get(unit_id, 2),
            'items': [],
            'position': pos
        })
        col += 1

    # Place flexible in middle rows
    col = 0
    for unit_id in flexible:
        row = 1 + (col // 7)
        pos = (col % 7, min(row, 2))
        comp.append({
            'champion': unit_id,
            'star': star_levels.get(unit_id, 2),
            'items': [],
            'position': pos
        })
        col += 1

    return comp


def run_comp_vs_comp(engine: CombatEngine, comp1_units: list, comp2_units: list,
                    num_sims: int = 100, player_level: int = 8) -> dict:
    """
    Run simulations of comp1 vs comp2.

    Returns win rate, avg damage, and other stats.
    """
    # Validate both comps
    val1 = validate_comp_for_level(engine, comp1_units, player_level)
    val2 = validate_comp_for_level(engine, comp2_units, player_level)

    if not val1['valid']:
        print(f"Comp 1 validation issues: {val1['issues']}")
    if not val2['valid']:
        print(f"Comp 2 validation issues: {val2['issues']}")

    # Create positioned comps
    comp1 = create_comp_with_positions(engine, comp1_units)
    comp2 = create_comp_with_positions(engine, comp2_units)

    # Run simulations
    wins = 0
    total_damage = 0
    total_survivors = 0

    for i in range(num_sims):
        # Create teams
        team1 = []
        for unit_def in comp1:
            unit = engine.create_unit(
                api_name=unit_def['champion'],
                star_level=unit_def['star'],
                team=0,
                position=unit_def['position'],
                items=unit_def.get('items', [])
            )
            if unit:
                team1.append(unit)

        team2 = []
        for unit_def in comp2:
            unit = engine.create_unit(
                api_name=unit_def['champion'],
                star_level=unit_def['star'],
                team=1,
                position=unit_def['position'],
                items=unit_def.get('items', [])
            )
            if unit:
                team2.append(unit)

        # Run combat
        result = engine.run_combat(team1, team2, verbose=False, seed=42 + i)

        if result['winner'] == 0:
            wins += 1
        total_damage += result['total_damage_dealt']['team0']
        total_survivors += result['team0_survivors']

    return {
        'win_rate': wins / num_sims,
        'avg_damage': total_damage / num_sims,
        'avg_survivors': total_survivors / num_sims,
        'num_sims': num_sims,
        'comp1_units': len(comp1),
        'comp2_units': len(comp2)
    }


def main():
    print("=" * 70)
    print("TFT Meta Comp Position Testing")
    print("=" * 70)
    print()

    # Initialize
    engine = CombatEngine()
    print(f"Loaded {len(engine.champions)} champions")

    # Load meta comps
    comps = load_meta_comps()
    print(f"Loaded {len(comps)} meta comps")
    print()

    # Show top 3 comps
    print("-" * 70)
    print("Top Meta Comps:")
    print("-" * 70)
    for i, comp in enumerate(comps[:3]):
        print(f"\n{i+1}. {comp['name']}")
        print(f"   Units: {', '.join(u.replace('TFT16_', '') for u in comp['units'])}")
        print(f"   Avg Placement: {comp['avg_placement']:.2f}")
        print(f"   Games: {comp['games_played']:,}")

        # Validate for level 8
        val = validate_comp_for_level(engine, comp['units'], 8)
        if val['valid']:
            print(f"   Level 8 Valid: YES")
        else:
            print(f"   Level 8 Issues: {val['issues']}")

    # Pick two comps to test (both must be valid for level 8)
    # For fair testing, let's do a mirror match to show positioning value
    valid_comps = []
    for comp in comps:
        val = validate_comp_for_level(engine, comp['units'], 8)
        if val['valid']:
            valid_comps.append(comp)
        if len(valid_comps) >= 2:
            break

    if len(valid_comps) < 1:
        print("Not enough valid comps for level 8 testing!")
        comp1_data = {'units': comps[0]['units'][:8], 'name': comps[0]['name']}
    else:
        comp1_data = valid_comps[0]

    # Mirror match - same comp vs itself to show positioning value
    comp2_data = {'units': comp1_data['units'], 'name': comp1_data['name'] + ' (Mirror)'}

    print()
    print("=" * 70)
    print(f"Testing: {comp1_data['name']} vs {comp2_data['name']}")
    print("=" * 70)

    # Show unit classifications
    print("\nComp 1 Role Classification:")
    for unit_id in comp1_data['units']:
        role = classify_unit_role(engine, unit_id)
        cost = get_champion_cost(engine, unit_id)
        print(f"  {unit_id.replace('TFT16_', ''):<15} Cost {cost}  {role}")

    print("\nComp 2 Role Classification:")
    for unit_id in comp2_data['units']:
        role = classify_unit_role(engine, unit_id)
        cost = get_champion_cost(engine, unit_id)
        print(f"  {unit_id.replace('TFT16_', ''):<15} Cost {cost}  {role}")

    # Run comp vs comp
    print()
    print("-" * 70)
    print("Running 100 simulations...")
    print("-" * 70)

    result = run_comp_vs_comp(
        engine,
        comp1_data['units'],
        comp2_data['units'],
        num_sims=100,
        player_level=8
    )

    print(f"\n{comp1_data['name']} vs {comp2_data['name']}:")
    print(f"  Comp 1 Win Rate: {result['win_rate']:.1%}")
    print(f"  Comp 1 Avg Damage: {result['avg_damage']:.0f}")
    print(f"  Comp 1 Avg Survivors: {result['avg_survivors']:.2f} / {result['comp1_units']}")

    # Now run positioning optimization for comp 1
    print()
    print("=" * 70)
    print(f"Position Optimization for {comp1_data['name']}")
    print("=" * 70)

    # Create comp definition for optimizer
    comp1_for_optimizer = []
    for unit_id in comp1_data['units']:
        comp1_for_optimizer.append({
            'champion': unit_id,
            'star': 2,
            'items': []
        })

    # Create opponent based on comp2
    comp2_opponent = create_comp_with_positions(engine, comp2_data['units'])

    optimizer = PositioningOptimizer(engine)

    print(f"\nOptimizing {len(comp1_for_optimizer)} units against {comp2_data['name']}...")
    print("(This may take a few minutes for 8 units)")

    result = optimizer.optimize(
        comp1_for_optimizer,
        opponents=[comp2_opponent],  # Use comp2 as opponent
        strategy='strategic',
        num_configs=200,  # Fewer configs for speed with 8 units
        sims_per_opponent=10,
        seed=42,
        verbose=True
    )

    # Show optimal positions
    print()
    print(optimizer.visualize_board(result['best_positions'], "Optimal Positions"))

    # Show top 5 configs
    print("\nTop 5 Configurations:")
    print("-" * 70)
    for i, res in enumerate(result['all_results'][:5]):
        print(f"{i+1}. Win rate: {res.win_rate:.1%}, Damage: {res.avg_damage_dealt:.0f}")


if __name__ == "__main__":
    main()
