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
import html
import json
import re
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

_LOOKUP_CACHE: Optional[dict] = None


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


def fetch_set16_lookup() -> Optional[dict]:
    """Fetch and cache the Set 16 lookup payload from MetaTFT."""
    global _LOOKUP_CACHE
    if _LOOKUP_CACHE is not None:
        return _LOOKUP_CACHE

    _LOOKUP_CACHE = fetch_json(f"{DATA_BASE}/lookups/TFTSet16_latest_en_us.json")
    return _LOOKUP_CACHE


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


def format_value(value) -> str:
    """Format numeric values with compact display."""
    if isinstance(value, str):
        return value
    if value is None:
        return "0"
    if isinstance(value, (int, float)):
        numeric = float(value)
        if abs(numeric - round(numeric)) < 1e-9:
            return str(int(round(numeric)))
        return f"{numeric:.2f}".rstrip("0").rstrip(".")
    return str(value)


def derive_display_name(api_name: str, prefixes: list[str]) -> str:
    """Derive a fallback display name from an API identifier."""
    display_name = api_name
    for prefix in prefixes:
        display_name = display_name.replace(prefix, "")
    return display_name


def slugify_display_name(value: str) -> str:
    """Build a stable slug form for a display string."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def render_lookup_description(entry: dict) -> str:
    """Render lookup tooltip text to plain readable text."""
    if not entry:
        return ""

    desc = entry.get("desc") or entry.get("description") or ""
    if not desc:
        return ""

    effects = entry.get("effects") or {}
    if isinstance(effects, list):
        merged_effects = {}
        for effect in effects:
            variables = effect.get("variables") if isinstance(effect, dict) else None
            if isinstance(variables, dict):
                for key, value in variables.items():
                    if key not in merged_effects and value is not None:
                        merged_effects[key] = value
        effects = merged_effects
    effect_keys = {str(k).lower(): k for k in effects.keys()}
    unit_props = entry.get("unitProperties") or {}

    # Resolve dynamic @...@ tokens.
    for token in set(re.findall(r"@([^@]+)@", desc)):
        raw = token.strip()
        replacement = None
        add_percent = False

        if raw.startswith("TFTUnitProperty"):
            prop_key = re.sub(r"TFTUnitProperty\.*\w*:", "", raw)
            if prop_key.endswith("%"):
                add_percent = True
                prop_key = prop_key[:-1]
            value = unit_props.get(prop_key)
            if value is not None:
                if isinstance(value, (int, float)) and value < 1:
                    value = value * 100
                    add_percent = True
                replacement = format_value(value)
        else:
            base_key = raw
            multiplier = 1
            if base_key.endswith("%"):
                add_percent = True
                base_key = base_key[:-1]
            if "*100" in base_key:
                base_key = base_key.replace("*100", "")
                multiplier = 100
                add_percent = True

            effect_key = effect_keys.get(base_key.lower())
            if effect_key is not None:
                value = effects.get(effect_key)
                if isinstance(value, (int, float)):
                    value = float(value) * multiplier
                replacement = format_value(value)

        if replacement is None:
            replacement = "Varies"

        if add_percent and replacement and not replacement.endswith("%"):
            replacement = f"{replacement}%"

        desc = desc.replace(f"@{token}@", replacement)

    token_replacements = {
        "i:scaleAD": "AD",
        "i:TFTBaseAD": "AD",
        "i:scaleAP": "AP",
        "i:scaleMR": "Magic Resist",
        "i:scaleArmor": "Armor",
        "i:scaleAS": "Attack Speed",
        "i:scaleMana": "Mana",
        "i:scaleHealth": "Health",
        "i:scaleRange": "Range",
        "i:scaleCritMult": "Crit Damage",
        "i:scaleCrit": "Crit Chance",
        "i:scaleDA": "Damage Amp",
        "i:scaleDR": "Durability",
        "i:scaleSV": "Omnivamp",
        "i:goldCoins": "Gold",
        "i:star": "★",
    }
    for token, replacement in token_replacements.items():
        desc = re.sub(f"%{re.escape(token)}%", replacement, desc)
        desc = re.sub(re.escape(token), replacement, desc)

    desc = html.unescape(desc)
    desc = re.sub(r"<br\s*/?>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</?rules>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</?tftitemrules>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = desc.replace("%%", "%")
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc


def fetch_units() -> bool:
    """Fetch unit/champion data from MetaTFT API."""
    print("\n[1/4] Fetching champions/units...")

    data = fetch_json(f"{API_BASE}/units", DEFAULT_PARAMS)
    if not data or "results" not in data:
        print("  Failed to fetch units data")
        return False

    results = data["results"]
    tft_set = data.get("tft_set", "TFTSet16")
    lookup_data = fetch_set16_lookup()
    unit_lookup = {}
    if lookup_data:
        unit_lookup = {unit.get("apiName"): unit for unit in lookup_data.get("units", []) if unit.get("apiName")}

    # Process and save as JSONL + processed active set.
    output_path = GAME_DATA_DIR / "champions.jsonl"
    processed_path = DATA_DIR / "api" / "processed" / "units_set16.json"
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    missing_lookup = 0
    active_unit_ids = {
        unit.get("unit", "")
        for unit in results
        if unit.get("unit", "").startswith("TFT")
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        for unit in results:
            unit_id = unit.get("unit", "")
            places = unit.get("places", [])

            # Skip non-champion units (like armory keys)
            if not unit_id.startswith("TFT"):
                continue

            lookup_entry = unit_lookup.get(unit_id)
            stats = calculate_stats(places)

            record = {
                "apiName": unit_id,
                "name": (
                    lookup_entry.get("name", "").strip()
                    if lookup_entry and lookup_entry.get("name")
                    else derive_display_name(unit_id, ["TFT16_", "TFT_"])
                ),
                "set": tft_set,
                "placements": places[:8] if len(places) >= 8 else places,
                **stats
            }
            if lookup_entry:
                if lookup_entry.get("cost") is not None:
                    record["cost"] = lookup_entry.get("cost")
                if lookup_entry.get("traits"):
                    record["traits"] = lookup_entry.get("traits")
                if lookup_entry.get("role"):
                    record["role"] = lookup_entry.get("role")
            else:
                missing_lookup += 1

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    # Keep the processed unit index complete (active + helper/non-playable).
    processed_units = []
    lookup_ids = set()
    for lookup_entry in unit_lookup.values():
        unit_id = lookup_entry.get("apiName", "")
        if not unit_id or not unit_id.startswith("TFT"):
            continue
        lookup_ids.add(unit_id)
        processed_unit = dict(lookup_entry)
        processed_unit["name"] = processed_unit.get("name", "").strip()
        processed_unit["is_active"] = unit_id in active_unit_ids
        processed_unit["is_helper"] = unit_id not in active_unit_ids
        processed_units.append(processed_unit)

    # Preserve any active unit returned by stats endpoint but missing in lookup.
    for unit_id in sorted(active_unit_ids - lookup_ids):
        processed_units.append(
            {
                "apiName": unit_id,
                "name": derive_display_name(unit_id, ["TFT16_", "TFT_"]),
                "cost": None,
                "traits": [],
                "is_active": True,
                "is_helper": False,
            }
        )

    processed_units.sort(key=lambda unit: unit.get("apiName", ""))

    with open(processed_path, 'w', encoding='utf-8') as f:
        json.dump(processed_units, f, indent=2, ensure_ascii=False)

    helper_count = sum(1 for unit in processed_units if unit.get("is_helper"))
    print(f"  Saved {count} active champions to {output_path}")
    print(f"  Saved {len(processed_units)} total units ({helper_count} helper) to {processed_path}")
    if missing_lookup:
        print(f"  WARNING: {missing_lookup} active units missing in lookup data")
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
    lookup_data = fetch_set16_lookup()
    item_lookup = {}
    if lookup_data:
        item_lookup = {item.get("apiName"): item for item in lookup_data.get("items", []) if item.get("apiName")}

    # Process and save as JSONL + processed active set.
    output_path = GAME_DATA_DIR / "items.jsonl"
    processed_path = DATA_DIR / "api" / "processed" / "items_set16.json"
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    missing_lookup = 0
    processed_items = []

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
            lookup_entry = item_lookup.get(item_name)

            display_name = (
                lookup_entry.get("name", "").strip()
                if lookup_entry and lookup_entry.get("name")
                else derive_display_name(
                    item_name,
                    ["TFT16_Item_", "TFT_Item_", "TFT5_Item_", "TFT4_Item_", "TFT7_Item_", "TFT9_Item_", "TFT16_"],
                )
            )
            description = render_lookup_description(lookup_entry) if lookup_entry else ""

            record = {
                "apiName": item_name,
                "name": display_name,
                "description": description,
                "category": category,
                "set": tft_set,
                "placements": places[:8] if len(places) >= 8 else places,
                **stats
            }
            if lookup_entry and lookup_entry.get("icon"):
                record["icon"] = lookup_entry.get("icon")

            if lookup_entry:
                processed_item = dict(lookup_entry)
                processed_item["name"] = display_name
                processed_item["desc"] = description
                processed_item["description"] = description
                processed_items.append(processed_item)
            else:
                missing_lookup += 1
                processed_items.append(
                    {
                        "apiName": item_name,
                        "name": display_name,
                        "desc": description,
                        "description": description,
                        "effects": {},
                    }
                )

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    with open(processed_path, 'w', encoding='utf-8') as f:
        json.dump(processed_items, f, indent=2, ensure_ascii=False)

    print(f"  Saved {count} items to {output_path}")
    print(f"  Saved {len(processed_items)} active items to {processed_path}")
    if missing_lookup:
        print(f"  WARNING: {missing_lookup} active items missing in lookup data")
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
    lookup_data = fetch_set16_lookup()
    if not lookup_data:
        print("  Failed to fetch lookup data for traits")
        return False

    lookup_traits = [
        trait for trait in lookup_data.get("traits", [])
        if trait.get("apiName", "").startswith("TFT")
    ]
    if not lookup_traits:
        print("  Failed to load traits from lookup payload")
        return False

    # Build placement stats grouped by base trait API name.
    output_path = GAME_DATA_DIR / "traits.jsonl"
    effects_path = GAME_DATA_DIR / "trait_effects.jsonl"
    mapping_path = GAME_DATA_DIR / "trait_id_map.json"
    processed_path = DATA_DIR / "api" / "processed" / "traits_set16.json"
    processed_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0

    trait_groups = {}
    for trait in results:
        trait_id = trait.get("trait", "")
        if not trait_id:
            continue

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

    # Always keep traits.jsonl aligned with lookup trait roster (active + helper teamups).
    with open(output_path, 'w', encoding='utf-8') as f:
        for trait in sorted(lookup_traits, key=lambda entry: entry.get("apiName", "")):
            api_name = trait.get("apiName", "")
            if not api_name:
                continue

            grouped = trait_groups.get(api_name, {})
            tier_stats = grouped.get("tiers", {})
            if not tier_stats:
                # Traits without stats endpoint coverage (for example unused teamups)
                # still get deterministic zeroed tier entries for downstream consumers.
                for idx, _effect in enumerate(trait.get("effects", []), start=1):
                    tier_stats[idx] = {
                        "placements": [0, 0, 0, 0, 0, 0, 0, 0],
                        "avg_place": 0,
                        "top4_rate": 0,
                        "win_rate": 0,
                        "games": 0,
                    }

            display_name = (trait.get("name") or "").strip() or derive_display_name(api_name, ["TFT16_", "TFT_"])
            desc = render_lookup_description(trait)
            effects = trait.get("effects", [])
            is_unique = bool(effects) and all(effect.get("style") == 4 for effect in effects)

            record = {
                "apiName": api_name,
                "name": display_name,
                "set": tft_set,
                "desc": desc,
                "icon": trait.get("icon"),
                "is_unique": is_unique,
                "tiers": tier_stats,
            }

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    # Trait effects for combat/game-data loaders.
    effect_count = 0
    with open(effects_path, 'w', encoding='utf-8') as f:
        for trait in sorted(lookup_traits, key=lambda entry: entry.get("apiName", "")):
            api_name = trait.get("apiName", "")
            for effect in trait.get("effects", []):
                record = {
                    "trait_apiName": api_name,
                    "minUnits": effect.get("minUnits"),
                    "maxUnits": effect.get("maxUnits"),
                    "style": effect.get("style"),
                    "variables_json": json.dumps(effect.get("variables", {}), ensure_ascii=False),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                effect_count += 1

    # Multi-key trait mapping (API, short ID, display name, slug).
    trait_mapping = {}
    for trait in lookup_traits:
        api_name = trait.get("apiName", "")
        if not api_name:
            continue
        short_name = api_name.replace("TFT16_", "", 1)
        display_name = (trait.get("name") or "").strip() or short_name
        slug = slugify_display_name(display_name)
        payload = {
            "apiName": api_name,
            "shortName": short_name,
            "displayName": display_name,
            "slug": slug,
            "icon": trait.get("icon"),
        }
        for key in {api_name, short_name, display_name, slug}:
            trait_mapping[key] = payload

    with open(mapping_path, 'w', encoding='utf-8') as f:
        json.dump(trait_mapping, f, indent=2, ensure_ascii=False)

    # Keep processed traits in sync with full lookup data used by app/simulator.
    processed_traits = []
    for trait in sorted(lookup_traits, key=lambda entry: entry.get("apiName", "")):
        processed_trait = dict(trait)
        desc = render_lookup_description(trait)
        processed_trait["desc"] = desc
        processed_trait["description"] = desc
        processed_traits.append(processed_trait)

    with open(processed_path, 'w', encoding='utf-8') as f:
        json.dump(processed_traits, f, indent=2, ensure_ascii=False)

    print(f"  Saved {count} traits to {output_path}")
    print(f"  Saved {effect_count} trait effect rows to {effects_path}")
    print(f"  Updated trait mapping with {len(trait_mapping)} keys at {mapping_path}")
    print(f"  Saved {len(processed_traits)} processed traits to {processed_path}")
    return True


def fetch_augments() -> bool:
    """Fetch augment data from MetaTFT lookup and tier list APIs.

    The primary /augments endpoint returns HTTP 500, so we use:
    - Lookup data: https://data.metatft.com/lookups/TFTSet16_latest_en_us.json
    - Tier list: https://api-hc.metatft.com/tft-stat-api/augments_tiers
    """
    print("\n[4/4] Fetching augments...")
    # 1. Fetch lookup data for augment details
    print("  Fetching augment lookup data...")
    lookup_data = fetch_set16_lookup()

    if not lookup_data or "augments" not in lookup_data:
        print("  Failed to fetch augment lookup data")
        return False

    augments_lookup = {aug['apiName']: aug for aug in lookup_data['augments']}
    print(f"  Found {len(augments_lookup)} augments in lookup")

    # 2. Fetch tier list for rankings
    print("  Fetching augment tier list...")
    tiers_data = fetch_json(f"{API_BASE}/augments_tiers", DEFAULT_PARAMS)

    tier_mapping = {}
    active_augments = []
    tft_set = "TFTSet16"

    if tiers_data and "content" in tiers_data:
        tft_set = tiers_data.get("tft_set", "TFTSet16")
        try:
            tier_list = tiers_data['content']['content']['tierList']
            tier_labels = ['S', 'A', 'B', 'C', 'D']
            for i, tier in enumerate(tier_list):
                label = tier_labels[i] if i < len(tier_labels) else f'T{i}'
                for aug in tier['content']:
                    aug_id = aug.get('id')
                    if not aug_id:
                        continue
                    tier_mapping[aug_id] = label
                    active_augments.append(aug_id)
            print(f"  Found {len(tier_mapping)} active augments with tier rankings")
        except (KeyError, TypeError):
            print("  Could not parse tier list")
            return False
    else:
        print("  Tier list unavailable")
        return False

    active_ids = sorted(set(active_augments))
    print(f"  Keeping {len(active_ids)} augments shown on metatft.com/augments")

    # Helper functions
    stage_tags = {"2-1", "3-2", "4-2"}

    rarity_suffixes = {
        "Silver": ["1", "-I", "-I-A", "-I-B", "_I", "Heart"],
        "Gold": ["2", "-II", "-II-A", "-II-B", "_II", "Crest"],
        "Prismatic": ["3", "-III", "III", "_III", "-III-A", "-III-B", "Crown"],
    }

    keyword_replacements = {
        "TFT14_AnimaSquad_Bonus_Default": "An Anima Squad Item",
        "Empty Mod - TFT14_Netgod_Champ_Default": "",
        "An Inkshadow Tattoo": "An Exotech Item",
    }

    token_replacements = {
        "i:scaleAD": "AD",
        "i:TFTBaseAD": "AD",
        "i:scaleAP": "AP",
        "i:scaleMR": "Magic Resist",
        "i:scaleArmor": "Armor",
        "i:scaleAS": "Attack Speed",
        "i:scaleMana": "Mana",
        "i:scaleHealth": "Health",
        "i:scaleRange": "Range",
        "i:scaleCritMult": "Crit Damage",
        "i:scaleCrit": "Crit Chance",
        "i:scaleDA": "Damage Amp",
        "i:scaleDR": "Durability",
        "i:scaleSV": "Omnivamp",
        "i:goldCoins": "Gold",
        "i:star": "★",
    }

    def infer_rarity(api_name: str, aug_data: dict) -> int:
        """Infer augment rarity (1=Silver, 2=Gold, 3=Prismatic)."""
        if api_name == "TFT9_Augment_FreljordTrait":
            return 2

        icon = aug_data.get("icon", "")
        metatft_name = icon.split("/")[-1].split(".")[0] if icon else ""

        for rarity_name, endings in rarity_suffixes.items():
            if any(metatft_name.endswith(suffix) for suffix in endings):
                return {"Silver": 1, "Gold": 2, "Prismatic": 3}[rarity_name]

        # Fallback for odd legacy names
        if api_name.endswith("PlusPlus") or "_III" in api_name or api_name.endswith("3"):
            return 3
        if api_name.endswith("Plus") or "_II" in api_name or api_name.endswith("2"):
            return 2
        return 1

    def render_description(aug_data: dict) -> str:
        """Render an augment description similar to MetaTFT tooltip text."""
        desc = aug_data.get("desc") or aug_data.get("description") or ""

        # Replace dynamic unit/trait property placeholders first.
        for token in set(re.findall(r"\(?@TFTUnitProperty\.*\w*:\w*(?:\*100)?@%?\)?", desc)):
            replacement = "Varies"
            if "TRA" in token:
                replacement = ""

            unit_props = aug_data.get("unitProperties") or {}
            prop_key = re.sub(r"@", "", token)
            prop_key = re.sub(r"TFTUnitProperty\.*\w*:", "", prop_key)
            if prop_key.endswith(")"):
                prop_key = prop_key.split(")")[0]

            add_percent = False
            if prop_key.endswith("%"):
                add_percent = True
                prop_key = prop_key[:-1]

            if prop_key in unit_props:
                replacement = unit_props[prop_key]
                if isinstance(replacement, (int, float)) and replacement < 1:
                    replacement = int(round(replacement * 100))
                replacement = str(replacement)
                if add_percent and replacement and not replacement.endswith("%"):
                    replacement = f"{replacement}%"

            if token.endswith(")") and not token.startswith("("):
                replacement = f"{replacement})"
            if token.startswith("(") and not token.endswith(")"):
                replacement = f"({replacement}"

            desc = desc.replace(token, replacement)

        # Replace normal variable placeholders using variable_matches.
        for variable in aug_data.get("variable_matches") or []:
            full_match = variable.get("full_match")
            if not full_match:
                continue

            value = variable.get("value")
            if value is None or value == "null":
                value = 0

            if variable.get("type") == "multiplier":
                multiplier = variable.get("multiplier", 1)
                try:
                    multiplier = float(multiplier)
                    value = float(value) * multiplier
                except (TypeError, ValueError):
                    pass

            desc = desc.replace(full_match, format_value(value))

        # Replace style tokens from MetaTFT tooltip markup.
        for token, replacement in token_replacements.items():
            desc = re.sub(f"%{re.escape(token)}%", replacement, desc)
            desc = re.sub(re.escape(token), replacement, desc)

        # Fallback replacements for legacy keywords.
        for token, replacement in keyword_replacements.items():
            if token in desc:
                desc = desc.replace(token, replacement)

        # Strip any leftover @...@ placeholders and html-ish tags.
        desc = re.sub(r"@[^@]+@", "", desc)
        desc = html.unescape(desc)
        desc = re.sub(r"<br\s*/?>", " ", desc, flags=re.IGNORECASE)
        desc = re.sub(r"</?rules>", " ", desc, flags=re.IGNORECASE)
        desc = re.sub(r"</?expandRowActive>|</?expandRow>", " ", desc, flags=re.IGNORECASE)
        desc = re.sub(r"</?row[^>]*>", " ", desc, flags=re.IGNORECASE)
        desc = re.sub(r"</?tooltipCalculationContainer>|</?tooltipCalculation>", " ", desc, flags=re.IGNORECASE)
        desc = re.sub(r"<[^>]+>", " ", desc)
        desc = desc.replace("???", "Varies")
        desc = re.sub(r"\s+", " ", desc).strip()
        return desc

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

    # 3. Combine and write augments.jsonl (active augments only)
    output_path = GAME_DATA_DIR / "augments.jsonl"
    count = 0
    missing_from_lookup = 0
    processed_augments = []

    with open(output_path, 'w', encoding='utf-8') as f:
        for api_name in active_ids:
            aug_data = augments_lookup.get(api_name)
            if not aug_data:
                missing_from_lookup += 1
                continue

            tier = tier_mapping.get(api_name, 'U')
            rarity = infer_rarity(api_name, aug_data)
            tags = [tag for tag in aug_data.get('tags', []) if tag in stage_tags]
            description = render_description(aug_data)

            record = {
                'apiName': api_name,
                'name': extract_display_name(api_name, aug_data),
                'description': description,
                'tier': tier,
                'rarity': rarity,
                'set': tft_set,
                'effects': aug_data.get('effects', {}),
                'associatedTraits': aug_data.get('associatedTraits', []),
                'tags': tags
            }

            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            count += 1
            processed_augments.append({
                **aug_data,
                "desc": description,
                "description": description,
                "tags": tags,
                "disabled": False,
            })

    # 4. Keep simulator augment source in sync (same active set).
    processed_path = DATA_DIR / "api" / "processed" / "augments_set16.json"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    with open(processed_path, 'w', encoding='utf-8') as f:
        json.dump(processed_augments, f, indent=2, ensure_ascii=False)

    print(f"  Saved {count} augments to {output_path}")
    print(f"  Saved {len(processed_augments)} augments to {processed_path}")
    if missing_from_lookup:
        print(f"  WARNING: {missing_from_lookup} tier-list augments missing in lookup data")
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
            f"{DATA_BASE}/lookups/TFTSet16_latest_en_us.json",
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


def update_processed_index():
    """Refresh data/api/processed/index.json with current file counts."""
    index_path = DATA_DIR / "api" / "processed" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    def count_entries(path: Path) -> int:
        if not path.exists():
            return 0
        with open(path, 'r', encoding='utf-8') as f:
            payload = json.load(f)
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            return len(payload)
        return 0

    counts = {
        "units": count_entries(index_path.parent / "units_set16.json"),
        "items": count_entries(index_path.parent / "items_set16.json"),
        "augments": count_entries(index_path.parent / "augments_set16.json"),
        "traits": count_entries(index_path.parent / "traits_set16.json"),
        "armory_items": count_entries(index_path.parent / "armory_items_set16.json"),
    }

    index = {
        "set": "TFTSet16",
        "patch": "current",
        "generated": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
    }

    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"Updated processed index: {index_path}")


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
        update_processed_index()

    print("\n" + "=" * 60)
    print(f"Fetch complete: {successes} succeeded, {failures} failed")
    print("=" * 60)

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    exit(main())
