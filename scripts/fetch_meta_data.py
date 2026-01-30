#!/usr/bin/env python3
"""
Fetch fresh TFT meta data from tactics.tools.
This script is run by GitHub Actions on a daily schedule.

Data source: https://tactics.tools/team-compositions
Extracts the __NEXT_DATA__ JSON block containing current meta compositions.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

# Base paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "meta"

# Data source
TACTICS_TOOLS_URL = "https://tactics.tools/team-compositions"

# Request headers to avoid being blocked
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_tactics_tools_data():
    """
    Fetch composition data from tactics.tools by extracting __NEXT_DATA__ JSON.

    Returns:
        dict: Parsed composition data or None if fetch fails
    """
    print(f"Fetching data from {TACTICS_TOOLS_URL}...")

    try:
        response = requests.get(TACTICS_TOOLS_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching tactics.tools: {e}")
        return None

    # Extract __NEXT_DATA__ JSON from HTML
    html = response.text
    pattern = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
    match = re.search(pattern, html, re.DOTALL)

    if not match:
        print("Error: Could not find __NEXT_DATA__ in response")
        return None

    try:
        next_data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"Error parsing __NEXT_DATA__ JSON: {e}")
        return None

    print("Successfully extracted __NEXT_DATA__ JSON")
    return next_data


def extract_comps_data(next_data):
    """
    Extract and normalize composition data from __NEXT_DATA__.

    Args:
        next_data: Raw __NEXT_DATA__ JSON object

    Returns:
        dict: Normalized composition data
    """
    if not next_data:
        return None

    try:
        # Navigate to the page props where comp data lives
        page_props = next_data.get("props", {}).get("pageProps", {})

        # Extract aperture (filter settings) for metadata
        aperture = page_props.get("aperture", {})
        patch_data = aperture.get("patch", {})
        # Patch is stored as {"_0": 16021} meaning patch 16.2.1
        patch_num = patch_data.get("_0", 0) if isinstance(patch_data, dict) else patch_data
        patch_str = f"{patch_num // 1000}.{(patch_num % 1000) // 10}.{patch_num % 10}" if patch_num else "unknown"

        # Get initial data containing the groups
        initial_data = page_props.get("initialData", {})

        # Extract comps from all groups
        comps = []
        groups = initial_data.get("groups", [])

        for group in groups:
            full_data = group.get("full", {})
            raw_comps = full_data.get("comps", [])

            for comp in raw_comps:
                normalized = {
                    "units": comp.get("units", []),
                    "games_played": comp.get("count", 0),
                    "avg_placement": round(comp.get("place", 0), 2),
                    "top4_count": comp.get("top4", 0),
                    "wins": comp.get("win", 0),
                    "spat_items": comp.get("spatItems", []),
                    "extra_traits": comp.get("extraTraits", []),
                }

                # Calculate rates
                if normalized["games_played"] > 0:
                    normalized["top4_rate"] = round(
                        normalized["top4_count"] / normalized["games_played"] * 100, 2
                    )
                    normalized["win_rate"] = round(
                        normalized["wins"] / normalized["games_played"] * 100, 2
                    )
                else:
                    normalized["top4_rate"] = 0
                    normalized["win_rate"] = 0

                comps.append(normalized)

        # Sort by games played (popularity) then top4 rate
        comps.sort(key=lambda x: (-x["games_played"], -x["top4_rate"]))

        # Extract metadata
        result = {
            "patch": patch_str,
            "total_games": initial_data.get("count", 0),
            "avg_placement": round(initial_data.get("place", 0), 2),
            "total_comps": len(comps),
            "comps": comps,
        }

        print(f"Extracted {len(comps)} compositions for patch {result['patch']}")
        print(f"Total games analyzed: {result['total_games']:,}")
        return result

    except (KeyError, TypeError) as e:
        print(f"Error extracting comp data: {e}")
        return None


def save_comps_data(data):
    """Save composition data to JSON file."""
    if not data:
        print("No data to save")
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / "comps.json"

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Saved composition data to {output_file}")
    return True


def update_timestamp():
    """Update the last-fetched timestamp."""
    timestamp_file = DATA_DIR / "last_updated.json"
    data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "tactics.tools",
        "url": TACTICS_TOOLS_URL,
        "automated": True
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(timestamp_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Updated timestamp: {data['last_updated']}")


def main():
    print("=" * 50)
    print("TFT Meta Data Fetcher")
    print("=" * 50)
    print(f"Running at: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Fetch data from tactics.tools
    next_data = fetch_tactics_tools_data()

    if next_data:
        # Extract and save composition data
        comps_data = extract_comps_data(next_data)
        save_comps_data(comps_data)
    else:
        print("Failed to fetch data - skipping save")

    # Update timestamp
    update_timestamp()

    print()
    print("Data fetch complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
