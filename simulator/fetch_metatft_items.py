#!/usr/bin/env python3
"""
Fetch item statistics from MetaTFT API.

This script fetches real-world item usage and win rate data for Set 16 units.
Data includes:
- Best items per unit (ranked by frequency and win rate)
- Item builds (combinations)
- Placement distribution per item

API Endpoints:
1. unit_items_processed - Quick overview of top items per unit (frequency-ranked)
2. unit_detail - Detailed stats with placement distributions per item
"""

import json
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from pathlib import Path


# MetaTFT API endpoints
ITEMS_OVERVIEW_URL = "https://api-hc.metatft.com/tft-comps-api/unit_items_processed?region_hint=na1"
UNIT_DETAIL_URL = "https://api-hc.metatft.com/tft-stat-api/unit_detail"

# Default query parameters for unit_detail
DEFAULT_PARAMS = {
    "queue": "1100",
    "patch": "current",
    "days": "3",
    "rank": "CHALLENGER,DIAMOND,EMERALD,GRANDMASTER,MASTER",
    "permit_filter_adjustment": "true",
    "server": "NA1",
    "region_hint": "na1",
}


def fetch_items_overview() -> Optional[Dict]:
    """
    Fetch quick overview of top items per unit.

    Returns dict with 'units' key containing per-unit item rankings.
    Items are ranked by frequency (most used first).
    """
    try:
        with urllib.request.urlopen(ITEMS_OVERVIEW_URL, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Error fetching items overview: {e}")
        return None


def fetch_unit_item_details(unit_id: str) -> Optional[Dict]:
    """
    Fetch detailed item statistics for a specific unit.

    Returns dict with:
    - items: List of items with placement distributions
    - builds: List of item combinations with placement distributions
    """
    params = DEFAULT_PARAMS.copy()
    params["unit"] = unit_id

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{UNIT_DETAIL_URL}?{query_string}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Error fetching details for {unit_id}: {e}")
        return None


def calculate_item_stats(places: List[int]) -> Dict:
    """
    Calculate statistics from placement distribution.

    Args:
        places: List of 8 counts [1st_place, 2nd_place, ..., 8th_place]

    Returns:
        Dict with avg_place, top4_rate, win_rate, total_games
    """
    total = sum(places)
    if total == 0:
        return {'avg_place': 0, 'top4_rate': 0, 'win_rate': 0, 'total_games': 0}

    # Calculate weighted average placement (1-indexed)
    avg_place = sum((i + 1) * count for i, count in enumerate(places)) / total

    # Top 4 rate (places 1-4)
    top4 = sum(places[:4])
    top4_rate = top4 / total

    # Win rate (1st place)
    win_rate = places[0] / total

    return {
        'avg_place': round(avg_place, 3),
        'top4_rate': round(top4_rate, 4),
        'win_rate': round(win_rate, 4),
        'total_games': total
    }


def process_unit_items(unit_data: Dict, min_games: int = 50) -> Dict:
    """
    Process item data for a unit, calculating win rates and rankings.

    Args:
        unit_data: Raw data from unit_detail API
        min_games: Minimum games to include an item

    Returns:
        Dict with processed item stats
    """
    items_raw = unit_data.get('items', [])
    builds_raw = unit_data.get('builds', [])

    # Process individual items
    items_processed = []
    for item in items_raw:
        name = item.get('itemName', '')
        places = item.get('places', [0] * 8)

        stats = calculate_item_stats(places)
        if stats['total_games'] >= min_games:
            items_processed.append({
                'item': name,
                **stats
            })

    # Sort by top4_rate descending
    items_processed.sort(key=lambda x: -x['top4_rate'])

    # Process builds (item combinations)
    builds_processed = []
    for build in builds_raw:
        names = build.get('buildNames', '')
        places = build.get('places', [0] * 8)

        stats = calculate_item_stats(places)
        if stats['total_games'] >= min_games:
            # Split build names
            item_list = names.split('|') if names else []
            builds_processed.append({
                'items': item_list,
                'build_string': names,
                **stats
            })

    # Sort builds by top4_rate
    builds_processed.sort(key=lambda x: -x['top4_rate'])

    return {
        'items': items_processed,
        'builds': builds_processed[:20]  # Top 20 builds
    }


def get_best_items_for_unit(unit_id: str, n: int = 5,
                            by: str = 'top4_rate') -> List[Dict]:
    """
    Get the N best items for a unit.

    Args:
        unit_id: Unit ID like 'TFT16_Seraphine'
        n: Number of items to return
        by: Sort key ('top4_rate', 'win_rate', 'avg_place')

    Returns:
        List of item dicts with stats
    """
    data = fetch_unit_item_details(unit_id)
    if not data:
        return []

    processed = process_unit_items(data)
    items = processed['items']

    # Re-sort if needed
    if by == 'win_rate':
        items.sort(key=lambda x: -x['win_rate'])
    elif by == 'avg_place':
        items.sort(key=lambda x: x['avg_place'])

    return items[:n]


def get_best_build_for_unit(unit_id: str) -> Optional[Dict]:
    """
    Get the best item build (combination) for a unit.

    Returns:
        Dict with items list and stats, or None
    """
    data = fetch_unit_item_details(unit_id)
    if not data:
        return None

    processed = process_unit_items(data)
    builds = processed['builds']

    # Find best 3-item build
    for build in builds:
        if len(build['items']) == 3:
            return build

    # Fall back to any build
    return builds[0] if builds else None


def classify_item_type(item_name: str) -> str:
    """
    Classify an item as offensive, defensive, utility, or emblem.
    """
    # Emblems
    if 'Emblem' in item_name:
        return 'emblem'

    # Offensive items
    offensive = {
        'InfinityEdge', 'Deathblade', 'GiantSlayer', 'LastWhisper',
        'JeweledGauntlet', 'RabadonsDeathcap', 'Morellonomicon',
        'StatikkShiv', 'GuinsoosRageblade', 'RunaansHurricane',
        'HandOfJustice', 'HextechGunblade', 'Bloodthirster',
        'TitansResolve', 'Leviathan', 'SpearOfShojin', 'BlueBuff',
        'ArchangelsStaff', 'NashorsTooth', 'RedBuff'
    }

    # Defensive items
    defensive = {
        'BrambleVest', 'DragonsClaw', 'GargoyleStoneplate',
        'Redemption', 'SunfireCape', 'WarmogsArmor', 'FrozenHeart',
        'IonicSpark', 'Quicksilver', 'EdgeOfNight', 'SteraksGage',
        'GuardianAngel', 'Crownguard'
    }

    # Check
    for off_item in offensive:
        if off_item in item_name:
            return 'offensive'

    for def_item in defensive:
        if def_item in item_name:
            return 'defensive'

    return 'utility'


def save_all_unit_items(output_path: str = None, min_games: int = 30):
    """
    Fetch and save item data for all Set 16 units.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from core.combat_engine import CombatEngine

    engine = CombatEngine()
    all_items = {}

    # Also get overview data for frequency rankings
    overview = fetch_items_overview()
    overview_units = overview.get('units', {}) if overview else {}

    print(f"Fetching item data for {len(engine.champions)} champions...")

    for i, unit_id in enumerate(engine.champions.keys()):
        print(f"  [{i+1}/{len(engine.champions)}] {unit_id}...", end=" ")

        # Get detailed data
        data = fetch_unit_item_details(unit_id)
        if data and data.get('items'):
            processed = process_unit_items(data, min_games=min_games)

            # Also add frequency ranking from overview
            overview_items = overview_units.get(unit_id, {}).get('items', [])
            frequency_ranked = [item.get('itemName') for item in overview_items]

            all_items[unit_id] = {
                'best_items': processed['items'][:10],  # Top 10 by win rate
                'best_builds': processed['builds'][:5],  # Top 5 builds
                'frequency_ranked': frequency_ranked[:10],  # Top 10 by frequency
            }
            print(f"OK ({len(processed['items'])} items)")
        else:
            print("SKIP (no data)")

    # Save to file
    if output_path is None:
        output_path = Path(__file__).parent / "data" / "metatft_items.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(all_items, f, indent=2)

    print(f"\nSaved item data for {len(all_items)} units to {output_path}")


def demo():
    """Demonstrate fetching item data."""
    print("Fetching MetaTFT Item Data")
    print("=" * 50)

    units = [
        "TFT16_Seraphine",  # AP carry
        "TFT16_Shyvana",    # AD carry
        "TFT16_Braum",      # Tank
    ]

    for unit_id in units:
        print(f"\n{unit_id}")
        print("-" * 40)

        items = get_best_items_for_unit(unit_id, n=5)
        if items:
            print("Best items by top4 rate:")
            for item in items:
                print(f"  {item['item']:40} | Top4: {item['top4_rate']:.1%} | "
                      f"Avg: {item['avg_place']:.2f} | Games: {item['total_games']}")

        build = get_best_build_for_unit(unit_id)
        if build:
            print(f"\nBest 3-item build:")
            print(f"  Items: {build['items']}")
            print(f"  Top4 rate: {build['top4_rate']:.1%}")
            print(f"  Avg place: {build['avg_place']:.2f}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--save-all":
        save_all_unit_items()
    else:
        demo()
