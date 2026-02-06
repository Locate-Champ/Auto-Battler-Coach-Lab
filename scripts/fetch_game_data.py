#!/usr/bin/env python3
"""
Fetch TFT game data (champions, items, traits, augments) from MetaTFT API.

This script fetches the core game reference data that changes with patches.
Data is saved to data/game_data/ in JSONL format for consistency.

API Endpoints:
- https://api-hc.metatft.com/tft-stat-api/units
- https://api-hc.metatft.com/tft-stat-api/items
- https://api-hc.metatft.com/tft-stat-api/traits
- https://data.metatft.com/lookups/trait_mapping.json

Usage:
    python scripts/fetch_game_data.py           # Fetch all game data
    python scripts/fetch_game_data.py --units   # Only fetch units/champions
    python scripts/fetch_game_data.py --items   # Only fetch items
    python scripts/fetch_game_data.py --traits  # Only fetch traits
"""

import argparse
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"
GAME_DATA_DIR = DATA_DIR / "game_data"

# MetaTFT API endpoints
API_BASE = "https://api-hc.metatft.com/tft-stat-api"
DATA_BASE = "https://data.metatft.com"

# Default query parameters
DEFAULT_PARAMS = {
    "queue": "1100",
    "patch": "current",
    "days": "3",
    "rank": "CHALLENGER,DIAMOND,EMERALD,GRANDMASTER,MASTER",
    "permit_filter_adjustment": "true",
    "region_hint": "na1",
}

# Headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def fetch_json(url: str, params: dict = None) -> Optional[dict]:
    """Fetch JSON from URL with proper headers."""
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    request = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        print(f"  Error fetching {url}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  Error parsing JSON from {url}: {e}")
        return None


def calculate_stats(places: list) -> dict:
    """Calculate stats from placement distribution."""
    if not places or len(places) < 8:
        return {"avg_place": 0, "top4_rate": 0, "win_rate": 0, "games": 0}

    total = sum(places[:8])
    if total == 0:
        return {"avg_place": 0, "top4_rate": 0, "win_rate": 0, "games": 0}

    avg_place = sum((i + 1) * count for i, count in enumerate(places[:8])) / total
    top4_rate = sum(places[:4]) / total
    win_rate = places[0] / total

    return {
        "avg_place": round(avg_place, 3),
        "top4_rate": round(top4_rate, 4),
        "win_rate": round(win_rate, 4),
        "games": total
    }


def fetch_units() -> bool:
    """Fetch unit/champion data from MetaTFT API."""
    print("\n[1/4] Fetching champions/units...")

    data = fetch_json(f"{API_BASE}/units", DEFAULT_PARAMS)
    if not data or "results" not in data:
        print("  Failed to fetch units data")
        return False

    results = data["results"]
    tft_set = data.get("tft_set", "TFTSet16")
    updated = data.get("updated")

    # Process and save as JSONL
    output_path = GAME_DATA_DIR / "champions.jsonl"
    count = 0

    with open(output_path, 'w', encoding='utf-8') as f:
        for unit in results:
            unit_id = unit.get("unit", "")
            places = unit.get("places", [])

            # Skip non-champion units (like armory keys)
            if not unit_id.startswith("TFT"):
                continue

            stats = calculate_stats(places)

            record = {
                "apiName": unit_id,
                "name": unit_id.replace("TFT16_", "").replace("TFT_", ""),
                "set": tft_set,
                "placements": places[:8] if len(places) >= 8 else places,
                **stats
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"  Saved {count} champions to {output_path}")
    return True


def fetch_items() -> bool:
    """Fetch item data from MetaTFT API."""
    print("\n[2/4] Fetching items...")

    data = fetch_json(f"{API_BASE}/items", DEFAULT_PARAMS)
    if not data or "results" not in data:
        print("  Failed to fetch items data")
        return False

    results = data["results"]
    tft_set = data.get("tft_set", "TFTSet16")

    # Process and save as JSONL
    output_path = GAME_DATA_DIR / "items.jsonl"
    count = 0

    # Categorize items
    def categorize_item(name: str) -> str:
        if "Emblem" in name:
            return "emblem"
        if "Radiant" in name:
            return "radiant"
        if "Artifact" in name:
            return "artifact"
        if "Ornn" in name:
            return "ornn"
        if "Shimmerscale" in name:
            return "shimmerscale"
        if "Darkin" in name:
            return "darkin"
        if "Bilgewater" in name:
            return "bilgewater"
        if name.startswith("TFT_Item_") and not any(x in name for x in ["Radiant", "Artifact"]):
            # Check if it's a component
            components = ["BFSword", "RecurveBow", "NeedlesslyLargeRod", "TearOfTheGoddess",
                          "ChainVest", "NegatronCloak", "GiantsBelt", "SparringGloves", "Spatula"]
            for comp in components:
                if comp in name:
                    return "component"
            return "completed"
        return "other"

    with open(output_path, 'w', encoding='utf-8') as f:
        for item in results:
            item_name = item.get("itemName", "")
            places = item.get("places", [])

            if not item_name:
                continue

            stats = calculate_stats(places)
            category = categorize_item(item_name)

            # Extract display name
            display_name = item_name
            for prefix in ["TFT16_Item_", "TFT_Item_", "TFT5_Item_", "TFT4_Item_",
                           "TFT7_Item_", "TFT9_Item_", "TFT16_"]:
                display_name = display_name.replace(prefix, "")

            record = {
                "apiName": item_name,
                "name": display_name,
                "category": category,
                "set": tft_set,
                "placements": places[:8] if len(places) >= 8 else places,
                **stats
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"  Saved {count} items to {output_path}")
    return True


def fetch_traits() -> bool:
    """Fetch trait data from MetaTFT API."""
    print("\n[3/4] Fetching traits...")

    data = fetch_json(f"{API_BASE}/traits", DEFAULT_PARAMS)
    if not data or "results" not in data:
        print("  Failed to fetch traits data")
        return False

    results = data["results"]
    tft_set = data.get("tft_set", "TFTSet16")

    # Also fetch trait mapping for display names
    trait_mapping = fetch_json(f"{DATA_BASE}/lookups/trait_mapping.json")
    reverse_mapping = {}
    if trait_mapping:
        reverse_mapping = {v: k for k, v in trait_mapping.items()}

    # Process and save as JSONL
    output_path = GAME_DATA_DIR / "traits.jsonl"
    count = 0

    # Group traits by base name (without tier number)
    trait_groups = {}
    for trait in results:
        trait_id = trait.get("trait", "")
        if not trait_id:
            continue

        # Parse trait name and tier (e.g., "TFT16_Void_3" -> "TFT16_Void", 3)
        parts = trait_id.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            base_name = parts[0]
            tier = int(parts[1])
        else:
            base_name = trait_id
            tier = 1

        if base_name not in trait_groups:
            trait_groups[base_name] = {"tiers": {}}

        places = trait.get("places", [])
        stats = calculate_stats(places)
        trait_groups[base_name]["tiers"][tier] = {
            "placements": places[:8] if len(places) >= 8 else places,
            **stats
        }

    with open(output_path, 'w', encoding='utf-8') as f:
        for base_name, group in trait_groups.items():
            # Get display name from mapping
            display_name = base_name.replace("TFT16_", "").replace("TFT_", "")

            # Check reverse mapping
            api_name_clean = base_name.replace("TFT16_", "")
            if base_name in reverse_mapping:
                display_name = reverse_mapping[base_name]
            elif api_name_clean in reverse_mapping:
                display_name = reverse_mapping[api_name_clean]

            # Determine if it's a unique trait (only tier 1)
            is_unique = len(group["tiers"]) == 1 and 1 in group["tiers"]

            record = {
                "apiName": base_name,
                "name": display_name,
                "set": tft_set,
                "is_unique": is_unique,
                "tiers": group["tiers"]
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    # Also save the trait mapping
    if trait_mapping:
        mapping_path = GAME_DATA_DIR / "trait_id_map.json"
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(trait_mapping, f, indent=2)
        print(f"  Updated trait_id_map.json")

    print(f"  Saved {count} traits to {output_path}")
    return True


def fetch_augments() -> bool:
    """Fetch augment data from MetaTFT lookup and tier list APIs.

    The primary /augments endpoint returns HTTP 500, so we use:
    - Lookup data: https://data.metatft.com/lookups/TFTSet16_latest_en_us.json
    - Tier list: https://api-hc.metatft.com/tft-stat-api/augments_tiers
    """
    print("\n[4/4] Fetching augments...")
    import re

    # 1. Fetch lookup data for augment details
    print("  Fetching augment lookup data...")
    lookup_data = fetch_json(f"{DATA_BASE}/lookups/TFTSet16_latest_en_us.json")

    if not lookup_data or "augments" not in lookup_data:
        print("  Failed to fetch augment lookup data")
        return False

    augments_lookup = {aug['apiName']: aug for aug in lookup_data['augments']}
    print(f"  Found {len(augments_lookup)} augments in lookup")

    # 2. Fetch tier list for rankings
    print("  Fetching augment tier list...")
    tiers_data = fetch_json(f"{API_BASE}/augments_tiers", DEFAULT_PARAMS)

    tier_mapping = {}
    tft_set = "TFTSet16"

    if tiers_data and "content" in tiers_data:
        tft_set = tiers_data.get("tft_set", "TFTSet16")
        try:
            tier_list = tiers_data['content']['content']['tierList']
            tier_labels = ['S', 'A', 'B', 'C', 'D']
            for i, tier in enumerate(tier_list):
                label = tier_labels[i] if i < len(tier_labels) else f'T{i}'
                for aug in tier['content']:
                    tier_mapping[aug['id']] = label
            print(f"  Found {len(tier_mapping)} augments with tier rankings")
        except (KeyError, TypeError):
            print("  Could not parse tier list, using 'U' for all")
    else:
        print("  Tier list unavailable, using 'U' for all augments")

    # Helper functions
    def determine_rarity(api_name: str) -> int:
        """Determine augment rarity (1=Silver, 2=Gold, 3=Prismatic)."""
        if api_name.endswith('PlusPlus') or '_III' in api_name or api_name.endswith('3'):
            return 3
        elif api_name.endswith('Plus') or '_II' in api_name or api_name.endswith('2'):
            return 2
        return 1

    def clean_description(desc: str) -> str:
        """Clean HTML/XML tags from description."""
        if not desc:
            return ''
        desc = re.sub(r'<[^>]+>', '', desc)
        desc = re.sub(r'@\w+@', 'X', desc)
        return desc.strip()

    def extract_display_name(api_name: str, lookup_entry: dict) -> str:
        """Get display name from lookup or derive from API name."""
        if lookup_entry:
            if lookup_entry.get('name'):
                return lookup_entry['name']
            if lookup_entry.get('en_name'):
                return lookup_entry['en_name']
        name = api_name
        for prefix in ['TFT16_Augment_', 'TFT9_Augment_', 'TFT6_Augment_', 'TFT_Augment_']:
            name = name.replace(prefix, '')
        return name

    # 3. Combine and write augments.jsonl
    output_path = GAME_DATA_DIR / "augments.jsonl"
    count = 0

    with open(output_path, 'w', encoding='utf-8') as f:
        # Process all augments from lookup
        for api_name, aug_data in augments_lookup.items():
            tier = tier_mapping.get(api_name, 'U')
            rarity = determine_rarity(api_name)

            record = {
                'apiName': api_name,
                'name': extract_display_name(api_name, aug_data),
                'description': clean_description(aug_data.get('desc', '')),
                'tier': tier,
                'rarity': rarity,
                'set': tft_set,
                'effects': aug_data.get('effects', {}),
                'associatedTraits': aug_data.get('associatedTraits', []),
                'tags': aug_data.get('tags', [])
            }

            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            count += 1

        # Add any augments from tier list not in lookup
        for api_name in tier_mapping:
            if api_name not in augments_lookup:
                tier = tier_mapping[api_name]
                rarity = determine_rarity(api_name)

                record = {
                    'apiName': api_name,
                    'name': extract_display_name(api_name, None),
                    'description': '',
                    'tier': tier,
                    'rarity': rarity,
                    'set': tft_set,
                    'effects': {},
                    'associatedTraits': [],
                    'tags': []
                }

                f.write(json.dumps(record, ensure_ascii=False) + '\n')
                count += 1

    print(f"  Saved {count} augments to {output_path}")
    return True


def update_metadata():
    """Update metadata file with fetch timestamp."""
    metadata_path = DATA_DIR / "metadata.json"

    metadata = {
        "source": "MetaTFT API",
        "source_urls": [
            f"{API_BASE}/units",
            f"{API_BASE}/items",
            f"{API_BASE}/traits",
            f"{DATA_BASE}/lookups/trait_mapping.json"
        ],
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "set_number": 16,
        "set_name": "Set16",
        "notes": [
            "Data fetched from MetaTFT public API",
            "Placements array: [1st, 2nd, 3rd, 4th, 5th, 6th, 7th, 8th]",
            "Stats calculated from high-elo ranked games"
        ]
    }

    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"\nUpdated {metadata_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch TFT game data from MetaTFT API"
    )
    parser.add_argument("--units", action="store_true", help="Only fetch units/champions")
    parser.add_argument("--items", action="store_true", help="Only fetch items")
    parser.add_argument("--traits", action="store_true", help="Only fetch traits")
    parser.add_argument("--augments", action="store_true", help="Only fetch augments")

    args = parser.parse_args()

    # If no specific flags, fetch everything
    fetch_all = not any([args.units, args.items, args.traits, args.augments])

    print("=" * 60)
    print("TFT Game Data Fetcher (MetaTFT API)")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    # Ensure output directory exists
    GAME_DATA_DIR.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures = 0

    if fetch_all or args.units:
        if fetch_units():
            successes += 1
        else:
            failures += 1

    if fetch_all or args.items:
        if fetch_items():
            successes += 1
        else:
            failures += 1

    if fetch_all or args.traits:
        if fetch_traits():
            successes += 1
        else:
            failures += 1

    if fetch_all or args.augments:
        if fetch_augments():
            successes += 1
        else:
            failures += 1

    # Update metadata
    if successes > 0:
        update_metadata()

    print("\n" + "=" * 60)
    print(f"Fetch complete: {successes} succeeded, {failures} failed")
    print("=" * 60)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    exit(main())
