"""
TFT Timing Utilities

Functions for calculating attack timing, projectile travel, and DPS.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


# TFT Constants
HEX_SIZE_UNITS = 180  # Approximate game units per hex
DEFAULT_MISSILE_SPEED = 2000  # Fallback for unknown missile speeds
ANIMATION_FPS = 30  # Standard animation framerate


def load_timing_constants() -> Dict[str, Any]:
    """Load timing constants from JSON file."""
    timing_file = Path(__file__).parent.parent / "data" / "timing_constants.json"
    with open(timing_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_champion_timing(api_name: str) -> Optional[Dict[str, Any]]:
    """Get timing data for a specific champion."""
    data = load_timing_constants()
    return data.get(api_name)


def calculate_projectile_travel_time(
    hex_distance: int,
    missile_speed: Optional[int] = None
) -> float:
    """
    Calculate time for a projectile to travel a given distance.

    Args:
        hex_distance: Number of hexes between attacker and target
        missile_speed: Projectile speed in game units/second (default: 2000)

    Returns:
        Travel time in seconds
    """
    if missile_speed is None:
        missile_speed = DEFAULT_MISSILE_SPEED

    distance_units = hex_distance * HEX_SIZE_UNITS
    return distance_units / missile_speed


def calculate_total_attack_delay(
    windup_seconds: float,
    hex_distance: int,
    missile_speed: Optional[int] = None,
    is_melee: bool = False
) -> float:
    """
    Calculate total time from attack start to damage dealt.

    Args:
        windup_seconds: Attack windup time (animation before projectile/hit)
        hex_distance: Distance to target in hexes
        missile_speed: Projectile speed (ignored for melee)
        is_melee: If True, no projectile travel time

    Returns:
        Total delay in seconds from attack command to damage
    """
    if is_melee:
        return windup_seconds

    travel_time = calculate_projectile_travel_time(hex_distance, missile_speed)
    return windup_seconds + travel_time


def calculate_effective_dps(
    base_damage: float,
    attack_speed: float,
    crit_chance: float = 0.25,
    crit_multiplier: float = 1.4,
    windup_seconds: Optional[float] = None,
    hex_distance: int = 1,
    missile_speed: Optional[int] = None
) -> Dict[str, float]:
    """
    Calculate effective DPS accounting for attack timing.

    Args:
        base_damage: Base attack damage
        attack_speed: Attacks per second
        crit_chance: Critical strike chance (0-1)
        crit_multiplier: Critical damage multiplier
        windup_seconds: Attack windup time (optional, for delay calculation)
        hex_distance: Distance to target
        missile_speed: Projectile speed

    Returns:
        Dictionary with DPS metrics
    """
    # Time between attacks
    attack_period = 1 / attack_speed

    # Average damage per attack (accounting for crits)
    avg_damage = base_damage * (1 + crit_chance * (crit_multiplier - 1))

    # Raw DPS (ignoring delays)
    raw_dps = avg_damage * attack_speed

    # If we have timing data, calculate effective DPS
    if windup_seconds is not None:
        total_delay = calculate_total_attack_delay(
            windup_seconds, hex_distance, missile_speed
        )
        # First attack is delayed, subsequent attacks follow attack_period
        # For sustained combat, raw_dps is accurate
        # For short fights, initial delay matters more
        first_attack_delay = total_delay
    else:
        first_attack_delay = None
        total_delay = None

    return {
        'raw_dps': raw_dps,
        'avg_damage_per_attack': avg_damage,
        'attack_period': attack_period,
        'first_attack_delay': first_attack_delay,
        'total_delay_per_attack': total_delay,
    }


def calculate_champion_attack_timing(
    api_name: str,
    target_distance: int = 1
) -> Dict[str, Any]:
    """
    Calculate full attack timing breakdown for a champion.

    Args:
        api_name: Champion API name (e.g., 'TFT16_Caitlyn')
        target_distance: Distance to target in hexes

    Returns:
        Dictionary with timing breakdown
    """
    champ = get_champion_timing(api_name)
    if not champ:
        return {'error': f'Champion {api_name} not found'}

    stats = champ['stats']
    timing = champ['timing']

    # Get values
    attack_speed = stats.get('attack_speed', 1.0)
    attack_range = stats.get('range', 1)
    windup = timing.get('attack_windup_seconds')
    missile = timing.get('missile_speed')

    is_melee = attack_range <= 1

    result = {
        'champion': champ['display_name'],
        'api_name': api_name,
        'attack_speed': attack_speed,
        'attack_range': attack_range,
        'is_melee': is_melee,
        'target_distance': target_distance,

        # Timing data
        'windup_seconds': windup,
        'missile_speed': missile,
        'timing_source': timing.get('source', 'unknown'),
        'timing_confidence': timing.get('confidence', 'unknown'),
    }

    # Calculate attack period
    if attack_speed > 0:
        result['attack_period'] = 1 / attack_speed
    else:
        result['attack_period'] = None

    # Calculate projectile travel (ranged only)
    if not is_melee and target_distance > 0:
        result['projectile_travel_time'] = calculate_projectile_travel_time(
            target_distance,
            missile
        )
    else:
        result['projectile_travel_time'] = 0

    # Total delay
    if windup is not None:
        result['total_attack_delay'] = calculate_total_attack_delay(
            windup,
            target_distance if not is_melee else 0,
            missile,
            is_melee
        )
    else:
        result['total_attack_delay'] = None

    # DPS calculation
    base_damage = stats.get('damage', 0)
    crit_chance = stats.get('crit_chance', 0.25)
    crit_mult = stats.get('crit_multiplier', 1.4)

    if base_damage and attack_speed:
        dps_info = calculate_effective_dps(
            base_damage, attack_speed, crit_chance, crit_mult,
            windup, target_distance, missile
        )
        result['dps'] = dps_info

    return result


def frames_to_seconds(frames: float, fps: float = ANIMATION_FPS) -> float:
    """Convert animation frames to seconds."""
    return frames / fps


def seconds_to_frames(seconds: float, fps: float = ANIMATION_FPS) -> float:
    """Convert seconds to animation frames."""
    return seconds * fps


# Quick reference table
def print_ranged_timing_table():
    """Print a reference table of ranged champion timing."""
    data = load_timing_constants()

    print(f"{'Champion':<20} {'Range':<6} {'AS':<6} {'Windup':<10} {'Missile':<8} {'4-hex delay':<12}")
    print("-" * 70)

    for api_name, champ in sorted(data.items(), key=lambda x: -x[1]['stats']['range']):
        stats = champ['stats']
        timing = champ['timing']

        if stats['range'] <= 1:
            continue

        windup = timing.get('attack_windup_seconds')
        missile = timing.get('missile_speed')

        windup_str = f"{windup:.3f}s" if windup else "?"
        missile_str = str(missile) if missile else "?"

        # Calculate 4-hex delay
        if windup and missile:
            delay = calculate_total_attack_delay(windup, 4, missile)
            delay_str = f"{delay:.3f}s"
        elif windup:
            delay_str = f"~{windup + 0.36:.3f}s"  # Estimate with default missile
        else:
            delay_str = "?"

        print(f"{champ['display_name']:<20} {stats['range']:<6.0f} {stats['attack_speed']:<6.2f} {windup_str:<10} {missile_str:<8} {delay_str:<12}")


if __name__ == "__main__":
    print("=== TFT Ranged Champion Timing Reference ===\n")
    print_ranged_timing_table()

    print("\n\n=== Example: Caitlyn at 4 hex range ===")
    cait = calculate_champion_attack_timing("TFT16_Caitlyn", target_distance=4)
    for k, v in cait.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for k2, v2 in v.items():
                print(f"  {k2}: {v2}")
        else:
            print(f"{k}: {v}")
