"""
Build comprehensive combat data for TFT Set 16 simulator.

Merges:
1. CommunityDragon champion stats (set16_champions.json)
2. Wiki timing data (wiki_timing_data.json)
3. Existing timing constants (timing_constants.json)

Output: combat_data.json - Ready for combat simulation
"""

import json
from pathlib import Path

# TFT Combat Constants
TFT_CONSTANTS = {
    "hex_size_units": 180,  # Game units per hex
    "default_missile_speed": 1800,  # Default projectile speed
    "base_crit_chance": 0.25,
    "base_crit_multiplier": 1.4,

    # Star level scaling
    "hp_scaling": {
        "1star": 1.0,
        "2star": 1.8,
        "3star": 3.24  # 1.8^2
    },
    "ad_scaling": {
        "1star": 1.0,
        "2star": 1.5,
        "3star": 2.25  # 1.5^2
    },

    # Damage reduction formula: final = raw * (100 / (100 + resist))
    # This means:
    # 50 armor/mr = 33% reduction
    # 100 armor/mr = 50% reduction
    # 200 armor/mr = 66% reduction

    # Attack speed formula
    # attacks_per_second = base_as * (1 + bonus_as)
    # attack_interval = 1 / attacks_per_second
}


def load_json(path: Path) -> dict:
    """Load JSON file, return empty dict if not found."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {path} not found")
        return {}


def calculate_attack_windup(base_as: float, windup_percent: float = None) -> float:
    """
    Calculate attack windup time in seconds.

    For TFT, windup is typically ~30-40% of attack time for most champions.
    Ranged champions with projectiles have additional travel time.

    Args:
        base_as: Base attack speed (attacks per second)
        windup_percent: Windup as percentage of attack time (0.0-1.0)

    Returns:
        Windup time in seconds
    """
    if base_as <= 0:
        return 0.5  # Default fallback

    attack_time = 1.0 / base_as

    if windup_percent is not None:
        return attack_time * windup_percent

    # Default windup estimate: 30% of attack time
    return attack_time * 0.30


def build_combat_data():
    """Build comprehensive combat data from all sources."""

    base_path = Path(__file__).parent.parent / "wad_extraction"
    data_path = Path(__file__).parent
    calibration_path = Path(__file__).parent.parent / "calibration"

    # Load source files
    print("Loading data sources...")

    champions_data = load_json(base_path / "set16_champions.json")
    wiki_timing = load_json(calibration_path / "wiki_timing_data.json")
    timing_constants = load_json(data_path / "timing_constants.json")

    if not champions_data:
        print("ERROR: Could not load set16_champions.json")
        return

    champions = champions_data.get('champions', {})
    print(f"Loaded {len(champions)} champions from CommunityDragon")
    print(f"Loaded {len(wiki_timing)} champions with wiki timing data")
    print(f"Loaded {len(timing_constants)} champions from timing constants")

    # Build combat data
    combat_data = {
        "version": "16.2",
        "constants": TFT_CONSTANTS,
        "champions": {},
        "traits": champions_data.get('traits', {})
    }

    for api_name, champ in champions.items():
        stats = champ.get('stats', {})
        ability = champ.get('ability', {})

        # Get base stats
        base_as = stats.get('attackSpeed', 0.7)
        attack_range = stats.get('range', 1)

        # Check for wiki timing data
        display_name = champ.get('name', '').strip()
        wiki_data = wiki_timing.get(display_name, {})

        # Check for existing timing constants
        timing_data = timing_constants.get(api_name, {})

        # Calculate windup
        windup_percent = wiki_data.get('windup_percent')
        if windup_percent:
            windup_percent = windup_percent / 100.0  # Convert from percentage

        attack_windup = calculate_attack_windup(base_as, windup_percent)

        # Get missile speed (for ranged champions)
        missile_speed = wiki_data.get('missile_speed') or timing_data.get('timing', {}).get('missile_speed')

        # Determine if ranged
        is_ranged = attack_range >= 2

        # Build champion combat data
        combat_champ = {
            "apiName": api_name,
            "name": display_name,
            "cost": champ.get('cost', 0),
            "traits": champ.get('traits', []),
            "role": champ.get('role', ''),

            # Base stats (1-star values)
            "stats": {
                "hp": stats.get('hp', 500),
                "ad": stats.get('damage', 50),
                "attackSpeed": base_as,
                "armor": stats.get('armor', 20),
                "magicResist": stats.get('magicResist', 20),
                "range": attack_range,
                "mana": stats.get('mana', 100),
                "startMana": stats.get('initialMana', 0),
                "critChance": stats.get('critChance', 0.25),
                "critMultiplier": stats.get('critMultiplier', 1.4),
            },

            # Timing data
            "timing": {
                "attackWindup": round(attack_windup, 3),
                "windupPercent": round((windup_percent or 0.30) * 100, 1),
                "missileSpeed": missile_speed,
                "isRanged": is_ranged,
                "timingSource": "wiki" if wiki_data else ("extracted" if timing_data else "estimated"),
            },

            # Ability data
            "ability": {
                "name": ability.get('name', '').strip(),
                "variables": ability.get('variables', {}),
            }
        }

        combat_data["champions"][api_name] = combat_champ

    # Add derived calculations
    for api_name, champ in combat_data["champions"].items():
        stats = champ["stats"]
        timing = champ["timing"]

        # Calculate DPS at 1-star (without abilities)
        attacks_per_sec = stats["attackSpeed"] or 0.7
        base_ad = stats["ad"] or 50
        crit_chance = stats["critChance"] or 0.25
        crit_mult = stats["critMultiplier"] or 1.4

        # Average damage per attack including crits
        avg_damage = base_ad * (1 - crit_chance + crit_chance * crit_mult)

        # DPS
        dps = avg_damage * attacks_per_sec

        champ["derived"] = {
            "attackInterval": round(1.0 / attacks_per_sec, 3) if attacks_per_sec > 0 else 999,
            "avgDamagePerAttack": round(avg_damage, 1),
            "baseDPS": round(dps, 1),
        }

        # Calculate projectile travel time for ranged (at max range)
        if timing["isRanged"] and timing["missileSpeed"]:
            max_range_hexes = stats["range"]
            travel_distance = max_range_hexes * TFT_CONSTANTS["hex_size_units"]
            travel_time = travel_distance / timing["missileSpeed"]
            champ["derived"]["maxRangeProjectileTime"] = round(travel_time, 3)

    # Save output
    output_path = data_path / "combat_data.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combat_data, f, indent=2)

    print(f"\nSaved combat data to: {output_path}")

    # Print summary
    print("\n=== COMBAT DATA SUMMARY ===")
    print(f"Total champions: {len(combat_data['champions'])}")

    # Count by timing source
    sources = {}
    for champ in combat_data['champions'].values():
        src = champ['timing']['timingSource']
        sources[src] = sources.get(src, 0) + 1

    print(f"Timing sources: {sources}")

    # Show ranged champions
    ranged = [c for c in combat_data['champions'].values() if c['timing']['isRanged']]
    print(f"Ranged champions: {len(ranged)}")

    # Top DPS champions
    print("\n=== TOP 10 BASE DPS (1-star) ===")
    sorted_by_dps = sorted(combat_data['champions'].values(),
                          key=lambda x: x['derived']['baseDPS'],
                          reverse=True)[:10]

    for i, champ in enumerate(sorted_by_dps, 1):
        print(f"{i}. {champ['name']}: {champ['derived']['baseDPS']} DPS "
              f"({champ['stats']['ad']} AD @ {champ['stats']['attackSpeed']:.2f} AS)")

    return combat_data


if __name__ == '__main__':
    build_combat_data()
