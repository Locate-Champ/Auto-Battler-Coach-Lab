#!/usr/bin/env python3
"""
Fetch TFT champion stats and abilities from CommunityDragon.

This script downloads the full TFT data from CommunityDragon and extracts:
- Champion base stats (HP, AD, armor, MR, attack speed, range, mana)
- Ability names and spell variables
- Trait associations

Data is saved to simulator/data/ for the combat simulator.

API Endpoint:
- https://raw.communitydragon.org/16.3/cdragon/tft/en_us.json

Usage:
    python scripts/fetch_champion_stats.py           # Fetch all champion data
    python scripts/fetch_champion_stats.py --set 16  # Specific set (default: 16)
    python scripts/fetch_champion_stats.py --dry-run # Preview without saving
"""

import argparse
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SIMULATOR_DATA_DIR = PROJECT_ROOT / "simulator" / "data"

# CommunityDragon TFT endpoint (use specific patch version for stability)
CDRAGON_TFT_URL = "https://raw.communitydragon.org/16.3/cdragon/tft/en_us.json"

# Headers
HEADERS = {
    "User-Agent": "TFT-Coach-Bot/1.0 (https://github.com/forrestmiller34/tft-coach-234)",
    "Accept": "application/json",
}

# Default TFT Set
DEFAULT_SET = 16


def fetch_cdragon_data() -> Optional[Dict]:
    """Download the full TFT data from CommunityDragon."""
    print(f"Fetching TFT data from CommunityDragon...")
    print(f"  URL: {CDRAGON_TFT_URL}")

    request = urllib.request.Request(CDRAGON_TFT_URL, headers=HEADERS)

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read()
            print(f"  Downloaded: {len(content) / 1024 / 1024:.1f} MB")
            return json.loads(content.decode('utf-8'))
    except urllib.error.URLError as e:
        print(f"  Error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None


def extract_champions(data: Dict, set_number: int = DEFAULT_SET) -> Dict[str, Dict]:
    """Extract champion data for the specified TFT set."""
    set_prefix = f"TFT{set_number}_"
    champions = {}

    # The CommunityDragon data has champions in the 'setData' array
    # Each set has its own entry with 'champions' array
    set_data_list = data.get("setData", [])

    target_set = None
    for set_entry in set_data_list:
        # Match by set number or mutator (e.g., "TFTSet16")
        mutator = set_entry.get("mutator", "")
        number = set_entry.get("number", 0)

        if number == set_number or f"TFTSet{set_number}" in mutator:
            target_set = set_entry
            print(f"  Found Set {set_number}: {set_entry.get('name', 'Unknown')}")
            break

    if not target_set:
        print(f"  Warning: Set {set_number} not found, searching all champions...")
        # Fall back to searching all champions in the data
        all_champions = data.get("champions", [])
        if not all_champions:
            # Try to find champions in items array (some versions structure differently)
            print("  Checking alternative data structures...")
            return champions
    else:
        all_champions = target_set.get("champions", [])

    print(f"  Processing {len(all_champions)} champions...")

    for champ in all_champions:
        api_name = champ.get("apiName", "")

        # Filter for our target set
        if not api_name.startswith(set_prefix):
            continue

        # Extract stats
        stats = champ.get("stats", {})

        # Extract ability
        ability_data = champ.get("ability", {})
        ability_variables = {}

        for var in ability_data.get("variables", []):
            var_name = var.get("name", "")
            var_values = var.get("value", [])
            if var_name and var_values:
                ability_variables[var_name] = var_values

        # Helper to get value with default when None
        def get_stat(key, default):
            val = stats.get(key)
            return val if val is not None else default

        champion_entry = {
            "apiName": api_name,
            "name": champ.get("name", api_name.replace(set_prefix, "")),
            "cost": champ.get("cost", 1),
            "traits": [t if isinstance(t, str) else t.get("name", t.get("id", "")) for t in champ.get("traits", [])],
            "stats": {
                "hp": get_stat("hp", 500),
                "ad": get_stat("damage", 50),
                "attackSpeed": get_stat("attackSpeed", 0.7),
                "armor": get_stat("armor", 20),
                "magicResist": get_stat("magicResist", 20),
                "range": get_stat("range", 1),
                "mana": get_stat("mana", 100),
                "startMana": get_stat("initialMana", 0),
                "critChance": get_stat("critChance", 0.25),
                "critMultiplier": get_stat("critMultiplier", 1.4),
            },
            "ability": {
                "name": ability_data.get("name", "Unknown"),
                "variables": ability_variables,
            },
        }

        champions[api_name] = champion_entry

    return champions


def extract_traits(data: Dict, set_number: int = DEFAULT_SET) -> Dict[str, Dict]:
    """Extract trait data for the specified TFT set."""
    set_prefix = f"TFT{set_number}_"
    traits = {}

    set_data_list = data.get("setData", [])

    target_set = None
    for set_entry in set_data_list:
        number = set_entry.get("number", 0)
        mutator = set_entry.get("mutator", "")

        if number == set_number or f"TFTSet{set_number}" in mutator:
            target_set = set_entry
            break

    if not target_set:
        return traits

    all_traits = target_set.get("traits", [])

    for trait in all_traits:
        api_name = trait.get("apiName", "")
        if not api_name.startswith(set_prefix):
            continue

        effects = []
        for effect in trait.get("effects", []):
            effects.append({
                "minUnits": effect.get("minUnits", 0),
                "maxUnits": effect.get("maxUnits", 0),
                "style": effect.get("style", 0),
                "variables": effect.get("variables", {}),
            })

        traits[api_name] = {
            "apiName": api_name,
            "name": trait.get("name", api_name.replace(set_prefix, "")),
            "effects": effects,
        }

    return traits


def merge_with_combat_data(champions: Dict[str, Dict], output_path: Path) -> int:
    """Merge new champion data with existing combat_data.json."""

    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    else:
        existing = {
            "version": "16.0",
            "constants": {
                "hex_size_units": 180,
                "default_missile_speed": 1800,
                "base_crit_chance": 0.25,
                "base_crit_multiplier": 1.4,
            },
            "champions": {},
        }

    updated_count = 0

    for api_name, new_data in champions.items():
        existing_champ = existing.get("champions", {}).get(api_name, {})

        # Create merged entry, preserving timing data and custom fields
        merged = {
            "apiName": api_name,
            "name": new_data["name"],
            "cost": new_data["cost"],
            "traits": new_data["traits"],
            "role": existing_champ.get("role", "Auto"),  # Preserve role
            "stats": new_data["stats"],
            "timing": existing_champ.get("timing", {  # Preserve timing
                "attackWindup": 0.3,
                "windupPercent": 20.0,
                "isRanged": new_data["stats"]["range"] > 1,
            }),
            "ability": new_data["ability"],
        }

        # Preserve derived stats if they exist
        if "derived" in existing_champ:
            merged["derived"] = existing_champ["derived"]

        # Preserve special flags
        if "special" in existing_champ:
            merged["special"] = existing_champ["special"]

        existing["champions"][api_name] = merged
        updated_count += 1

    # Update version timestamp
    existing["last_updated"] = datetime.now(timezone.utc).isoformat()
    existing["source"] = "CommunityDragon"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return updated_count


def merge_with_timing_constants(champions: Dict[str, Dict], output_path: Path) -> int:
    """Merge new champion data with existing timing_constants.json."""

    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    else:
        existing = {}

    updated_count = 0

    for api_name, new_data in champions.items():
        existing_champ = existing.get(api_name, {})

        # Create merged entry, preserving timing and wiki data
        merged = {
            "api_name": api_name,
            "display_name": new_data["name"],
            "cost": new_data["cost"],
            "traits": new_data["traits"],
            "stats": {
                "hp": new_data["stats"]["hp"],
                "damage": new_data["stats"]["ad"],
                "armor": new_data["stats"]["armor"],
                "magic_resist": new_data["stats"]["magicResist"],
                "attack_speed": new_data["stats"]["attackSpeed"],
                "crit_chance": new_data["stats"]["critChance"],
                "crit_multiplier": new_data["stats"]["critMultiplier"],
                "range": new_data["stats"]["range"],
                "mana": new_data["stats"]["mana"],
                "initial_mana": new_data["stats"]["startMana"],
            },
            "timing": existing_champ.get("timing", {  # Preserve timing
                "attack_windup_frames": None,
                "attack_windup_seconds": 0.3,
                "source": "default",
                "confidence": "low",
            }),
            "ability": {
                "name": new_data["ability"]["name"],
                "variables": new_data["ability"]["variables"],
            },
        }

        # Preserve wiki data if exists
        if "wiki_data" in existing_champ:
            merged["wiki_data"] = existing_champ["wiki_data"]

        # Preserve raw animation data if exists
        if "_raw_animation" in existing_champ:
            merged["_raw_animation"] = existing_champ["_raw_animation"]

        existing[api_name] = merged
        updated_count += 1

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    return updated_count


def main():
    parser = argparse.ArgumentParser(
        description="Fetch TFT champion stats from CommunityDragon"
    )
    parser.add_argument(
        "--set", type=int, default=DEFAULT_SET,
        help=f"TFT set number to fetch (default: {DEFAULT_SET})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview data without saving to files"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=SIMULATOR_DATA_DIR,
        help="Output directory for data files"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("TFT Champion Stats Fetcher (CommunityDragon)")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Set: {args.set}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    # Fetch data
    data = fetch_cdragon_data()
    if not data:
        print("\nFailed to fetch data from CommunityDragon")
        return 1

    # Extract champions
    print(f"\n[1/3] Extracting Set {args.set} champions...")
    champions = extract_champions(data, args.set)
    print(f"  Found: {len(champions)} champions")

    if not champions:
        print("\nNo champions found for this set!")
        print("Available sets in data:")
        for set_entry in data.get("setData", []):
            print(f"  - Set {set_entry.get('number')}: {set_entry.get('name')}")
        return 1

    # Extract traits
    print(f"\n[2/3] Extracting Set {args.set} traits...")
    traits = extract_traits(data, args.set)
    print(f"  Found: {len(traits)} traits")

    if args.dry_run:
        print("\n[DRY RUN] Would update these files:")
        print(f"  - {args.output_dir / 'combat_data.json'}")
        print(f"  - {args.output_dir / 'timing_constants.json'}")

        print("\nSample champion data:")
        sample = list(champions.values())[:3]
        for champ in sample:
            print(f"\n  {champ['name']} ({champ['cost']} cost)")
            print(f"    HP: {champ['stats']['hp']}, AD: {champ['stats']['ad']}")
            print(f"    Ability: {champ['ability']['name']}")
        return 0

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Save to files
    print(f"\n[3/3] Saving to files...")

    combat_data_path = args.output_dir / "combat_data.json"
    count1 = merge_with_combat_data(champions, combat_data_path)
    print(f"  Updated {count1} champions in {combat_data_path.name}")

    timing_path = args.output_dir / "timing_constants.json"
    count2 = merge_with_timing_constants(champions, timing_path)
    print(f"  Updated {count2} champions in {timing_path.name}")

    # Save traits
    traits_path = args.output_dir / "traits.json"
    with open(traits_path, 'w', encoding='utf-8') as f:
        json.dump({
            "set": args.set,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "traits": traits,
        }, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(traits)} traits to {traits_path.name}")

    print("\n" + "=" * 60)
    print(f"SUCCESS: Updated {len(champions)} champions from CommunityDragon")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
