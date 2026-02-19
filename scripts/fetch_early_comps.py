#!/usr/bin/env python3
"""
Fetch early game composition data from MetaTFT API.
This script fetches stage-2 comps with transition links to late game comps.

Data source: https://api.metatft.com/tft-early-comps/comps_overview
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import requests

# Base paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "meta"

# MetaTFT Early Comps API endpoint
EARLY_COMPS_API_URL = "https://api.metatft.com/tft-early-comps/comps_overview"

# Request headers
HEADERS = {
    "User-Agent": "TFT-Coach/1.0",
    "Accept": "application/json",
}


def fetch_early_comps_data():
    """
    Fetch early game composition data from MetaTFT API.

    Returns:
        dict: Raw API response or None if fetch fails
    """
    print("Fetching early comps from MetaTFT API...")
    print(f"URL: {EARLY_COMPS_API_URL}")

    try:
        response = requests.get(EARLY_COMPS_API_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching Early Comps API: {e}")
        return None

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None

    print("Successfully fetched early comps data")
    return data


def extract_early_comps(raw_data):
    """
    Extract and normalize early game composition data.

    Args:
        raw_data: Raw API response

    Returns:
        dict: Normalized early comp data with transition links
    """
    if not raw_data:
        return None

    try:
        comps_overview = raw_data.get("comps_overview", {})
        stage_2_data = comps_overview.get("stage-2", {})
        raw_comps = stage_2_data.get("comps", [])
        stage_stats = stage_2_data.get("stats", {})

        comps = []

        for comp in raw_comps:
            cluster_id = comp.get("cluster", "0")

            # Parse unit names from the "name" field (comma-separated)
            name_string = comp.get("name", "")
            units = [u.strip() for u in name_string.split(",") if u.strip()]

            # Get comp stats
            comp_stats = comp.get("stats", {})
            avg_placement = comp_stats.get("final_place_avg", 4.5)
            games = comp_stats.get("final_place_count", 0)
            winrate = comp_stats.get("final_place_winrate", 0)
            matchup_winrate = comp_stats.get("matchup_winrate", 0.5)
            avg_hp = comp_stats.get("avg_hp", 90)

            # Parse forwards_links (transitions to late game comps)
            # Format: list where index maps to late game cluster ID (387000 + index)
            # Values are transition percentages
            forwards_links_raw = comp.get("forwards_links", [])
            forwards_links = []
            for idx, prob in enumerate(forwards_links_raw):
                if isinstance(prob, (int, float)) and prob > 0:
                    # Index maps to late game cluster ID (387000 + index)
                    target_cluster_id = 387000 + idx
                    forwards_links.append(
                        {
                            "target_cluster_id": target_cluster_id,
                            "probability": (
                                round(prob / 100, 3) if prob > 1 else round(prob, 3)
                            ),  # Normalize to 0-1
                        }
                    )

            # Sort by probability descending
            forwards_links.sort(key=lambda x: x["probability"], reverse=True)

            # Get void probability (chance of not transitioning to a known comp)
            void_prob = comp.get("forwards_link_void", 0)

            # Parse unit star level data
            units_data = comp.get("units", {})
            star_levels = {}
            for unit_name, unit_info in units_data.items():
                # Determine most common star level
                stars_1 = unit_info.get("1-star", {}).get("matchup_count", 0)
                stars_2 = unit_info.get("2-star", {}).get("matchup_count", 0)
                stars_3 = unit_info.get("3-star", {}).get("matchup_count", 0)

                if stars_3 > stars_2 and stars_3 > stars_1:
                    star_levels[unit_name] = 3
                elif stars_2 > stars_1:
                    star_levels[unit_name] = 2
                else:
                    star_levels[unit_name] = 1

            early_comp = {
                "comp_id": f"early_{cluster_id}",
                "cluster": cluster_id,
                "units": units,
                "stats": {
                    "avg_placement": round(avg_placement, 2),
                    "games": games,
                    "winrate": round(winrate, 3),
                    "matchup_winrate": round(matchup_winrate, 3),
                    "avg_hp": round(avg_hp, 1),
                },
                "star_levels": star_levels,
                "forwards_links": forwards_links[:5],  # Top 5 transitions
                "void_probability": round(void_prob, 3),
            }

            comps.append(early_comp)

        # Sort by games played (most popular first)
        comps.sort(key=lambda x: x["stats"]["games"], reverse=True)

        result = {
            "stage": "stage-2",
            "source": "metatft",
            "total_comps": len(comps),
            "total_matchups": stage_stats.get("matchup_count", 0),
            "overall_stats": {
                "avg_placement": round(stage_stats.get("final_place_avg", 4.5), 2),
                "avg_hp": round(stage_stats.get("avg_hp", 90), 1),
            },
            "comps": comps,
        }

        print(f"Extracted {len(comps)} early game compositions")
        print(f"Total matchups analyzed: {result['total_matchups']:,}")

        return result

    except (KeyError, TypeError) as e:
        print(f"Error extracting early comp data: {e}")
        import traceback

        traceback.print_exc()
        return None


def save_early_comps(data):
    """Save early composition data to JSON file."""
    if not data:
        print("No data to save")
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / "early_comps.json"

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved early comp data to {output_file}")
    return True


def main():
    print("=" * 50)
    print("TFT Early Comps Fetcher (MetaTFT API)")
    print("=" * 50)
    print(f"Running at: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Fetch data from MetaTFT API
    raw_data = fetch_early_comps_data()

    if raw_data:
        # Extract and save early comp data
        early_data = extract_early_comps(raw_data)
        if early_data:
            save_early_comps(early_data)
        else:
            print("Failed to extract early comp data")
    else:
        print("Failed to fetch data - skipping save")

    print()
    print("Early comps fetch complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
