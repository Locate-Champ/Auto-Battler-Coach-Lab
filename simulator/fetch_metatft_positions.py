#!/usr/bin/env python3
"""
Fetch positioning heatmap data from MetaTFT API.

This script fetches real-world positioning statistics for Set 16 units
and can be used to inform positioning strategies.

API Endpoint:
https://api-hc.metatft.com/tft-stat-api/unit_detail?queue=1100&patch=current&days=3&rank=CHALLENGER,DIAMOND,EMERALD,GRANDMASTER,MASTER&permit_filter_adjustment=true&server=NA1&unit=<UNIT_ID>&region_hint=na1

Data includes:
- position: Array of {position: "cell_X", unit, count, win} for each of 28 board cells
- items: Best items for the unit
- builds: Best item combinations
- levels: Star level performance data
"""

import json
import urllib.request
import urllib.error
from typing import Dict, List, Optional
from pathlib import Path


# MetaTFT API base URL
API_BASE = "https://api-hc.metatft.com/tft-stat-api/unit_detail"

# Default query parameters
DEFAULT_PARAMS = {
    "queue": "1100",
    "patch": "current",
    "days": "3",
    "rank": "CHALLENGER,DIAMOND,EMERALD,GRANDMASTER,MASTER",
    "permit_filter_adjustment": "true",
    "server": "NA1",
    "region_hint": "na1",
}

# Cell number to (col, row) mapping
# MetaTFT uses cell_1 to cell_28, numbered from TOP-LEFT of the visual board.
#
# From PLAYER'S perspective (what we use in our simulator):
#   - Row 3 = BACK row (closest to you, where you place carries)
#   - Row 0 = FRONT row (closest to enemy, where tanks go)
#
# MetaTFT cell numbering (cells 1-28) - from BOARD VISUAL perspective:
#   - Cells 1-7 = Top row of visual = BACK row (row 3, closest to player, carries go here)
#   - Cells 8-14 = Second row of visual = row 2
#   - Cells 15-21 = Third row of visual = row 1
#   - Cells 22-28 = Bottom row of visual = FRONT row (row 0, closest to enemy, tanks go here)
#
# So we need to FLIP the row: row = 3 - ((cell_num - 1) // 7)
CELL_TO_POSITION = {}
for visual_row in range(4):
    for col in range(7):
        cell_num = visual_row * 7 + col + 1
        # Flip the row: visual top (cells 1-7) = game row 3 (back)
        game_row = 3 - visual_row
        CELL_TO_POSITION[f"cell_{cell_num}"] = (col, game_row)

# Reverse mapping
POSITION_TO_CELL = {v: k for k, v in CELL_TO_POSITION.items()}


def fetch_unit_data(unit_id: str) -> Optional[Dict]:
    """
    Fetch detailed statistics for a unit from MetaTFT API.

    Args:
        unit_id: Unit ID like 'TFT16_BaronNashor'

    Returns:
        Dict with unit stats or None if fetch failed
    """
    params = DEFAULT_PARAMS.copy()
    params["unit"] = unit_id

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API_BASE}?{query_string}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data
    except urllib.error.URLError as e:
        print(f"Error fetching {unit_id}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing response for {unit_id}: {e}")
        return None


def get_position_heatmap(unit_data: Dict) -> Dict[tuple, Dict]:
    """
    Extract position heatmap from unit data.

    Returns dict mapping (col, row) to {count, win, win_rate}
    """
    heatmap = {}

    for pos_data in unit_data.get('position', []):
        cell = pos_data.get('position')
        if cell not in CELL_TO_POSITION:
            continue

        col, row = CELL_TO_POSITION[cell]
        count = pos_data.get('count', 0)
        wins = pos_data.get('win', 0)
        win_rate = wins / count if count > 0 else 0

        heatmap[(col, row)] = {
            'count': count,
            'win': wins,
            'win_rate': win_rate,
            'cell': cell
        }

    return heatmap


def print_position_heatmap(unit_id: str, heatmap: Dict[tuple, Dict]):
    """Print ASCII visualization of position heatmap."""
    print(f"\nPosition Heatmap for {unit_id}")
    print("=" * 50)
    print("Win Rate by Position (higher = better)")
    print()

    # Print header
    print("     ", end="")
    for col in range(7):
        print(f"  {col}   ", end="")
    print()
    print("     " + "-" * 42)

    # Print rows (3 = back, 0 = front)
    for row in range(3, -1, -1):
        print(f"  {row} |", end="")
        for col in range(7):
            data = heatmap.get((col, row))
            if data and data['count'] > 0:
                wr = data['win_rate'] * 100
                print(f" {wr:4.1f}%", end="")
            else:
                print("   -  ", end="")
        print()

    print()
    print("Row 0 = Front (enemy side), Row 3 = Back (your side)")


def get_best_positions(heatmap: Dict[tuple, Dict], n: int = 5) -> List[tuple]:
    """Get the N best positions by win rate (with minimum sample size)."""
    # Filter positions with at least 100 games
    valid = [(pos, data) for pos, data in heatmap.items() if data['count'] >= 100]

    # Sort by win rate descending
    sorted_positions = sorted(valid, key=lambda x: -x[1]['win_rate'])

    return [pos for pos, _ in sorted_positions[:n]]


def classify_unit_by_position(heatmap: Dict[tuple, Dict]) -> str:
    """
    Classify a unit as 'frontline', 'backline', or 'flexible'
    based on where it's most commonly played.
    """
    front_count = sum(d['count'] for (c, r), d in heatmap.items() if r <= 1)
    back_count = sum(d['count'] for (c, r), d in heatmap.items() if r >= 2)
    total = front_count + back_count

    if total == 0:
        return 'flexible'

    front_pct = front_count / total
    back_pct = back_count / total

    if front_pct > 0.65:
        return 'frontline'
    elif back_pct > 0.65:
        return 'backline'
    else:
        return 'flexible'


def demo():
    """Demonstrate fetching position data."""
    print("Fetching MetaTFT Position Data")
    print("=" * 50)

    # Example units to fetch
    units = [
        "TFT16_BaronNashor",  # 5-cost carry
        "TFT16_Braum",        # Tank
        "TFT16_Seraphine",    # Support/carry
    ]

    for unit_id in units:
        print(f"\nFetching {unit_id}...")
        data = fetch_unit_data(unit_id)

        if data:
            heatmap = get_position_heatmap(data)
            print_position_heatmap(unit_id, heatmap)

            best = get_best_positions(heatmap)
            print(f"Best positions: {best}")

            role = classify_unit_by_position(heatmap)
            print(f"Position classification: {role}")
        else:
            print(f"Failed to fetch {unit_id}")


def save_all_unit_positions(output_path: str = None):
    """
    Fetch and save position data for all Set 16 units.

    This can be used to build a positioning database.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from core.combat_engine import CombatEngine

    engine = CombatEngine()
    all_positions = {}

    print(f"Fetching position data for {len(engine.champions)} champions...")

    for i, unit_id in enumerate(engine.champions.keys()):
        print(f"  [{i+1}/{len(engine.champions)}] {unit_id}...", end=" ")

        data = fetch_unit_data(unit_id)
        if data and data.get('position'):
            heatmap = get_position_heatmap(data)
            best_positions = get_best_positions(heatmap)
            role = classify_unit_by_position(heatmap)

            all_positions[unit_id] = {
                'heatmap': {f"{c},{r}": d for (c, r), d in heatmap.items()},
                'best_positions': best_positions,
                'role': role
            }
            print(f"OK ({role})")
        else:
            print("SKIP (no data)")

    # Save to file
    if output_path is None:
        output_path = Path(__file__).parent / "data" / "metatft_positions.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(all_positions, f, indent=2)

    print(f"\nSaved position data for {len(all_positions)} units to {output_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--save-all":
        save_all_unit_positions()
    else:
        demo()
