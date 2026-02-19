#!/usr/bin/env python3
"""
Fetch fresh TFT meta data from MetaTFT API.
This script is run by GitHub Actions on a daily schedule.

Data source: https://api-hc.metatft.com/tft-comps-api/comps_data
Returns composition clusters with performance stats, item builds, and traits.
"""

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests

# Base paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "meta"
GAME_DATA_DIR = SCRIPT_DIR.parent / "data" / "game_data"

# MetaTFT API endpoints
METATFT_COMPS_URL = "https://api-hc.metatft.com/tft-comps-api/comps_data"
METATFT_STATS_URL = "https://api-hc.metatft.com/tft-comps-api/comps_stats"
METATFT_COMPS_PARAMS = {
    "queue": "1100",  # Ranked queue
    "region_hint": "na1",
    "rank": "EMERALD",  # Emerald+ stats
    "days": "3",  # Last 3 days of data
}
METATFT_STATS_PARAMS = {
    "queue": "1100",  # Ranked queue
    "patch": "current",
    "days": "3",
    "rank": "CHALLENGER,DIAMOND,EMERALD,GRANDMASTER,MASTER",
    "permit_filter_adjustment": "true",
    "region_hint": "na1",
}

# Request headers
HEADERS = {
    "User-Agent": "TFT-Coach/1.0",
    "Accept": "application/json",
}

# Number of top comps to fetch
TOP_COMPS_LIMIT = 25

# Tier thresholds based on average placement
TIER_THRESHOLDS = {
    "S": 4.0,  # < 4.0 avg placement
    "A": 4.3,  # 4.0 - 4.3
    "B": 4.6,  # 4.3 - 4.6
    # C: > 4.6
}

# Trait ID mapping (API name -> display name)
TRAIT_ID_MAP = {}
# Champion to trait mapping (champion apiName -> list of trait apiNames)
CHAMPION_TRAITS_MAP = {}


def load_trait_id_map():
    """Load trait ID mapping from JSON file."""
    global TRAIT_ID_MAP
    map_file = GAME_DATA_DIR / "trait_id_map.json"
    if map_file.exists():
        with open(map_file, "r") as f:
            TRAIT_ID_MAP = json.load(f)
        print(f"Loaded {len(TRAIT_ID_MAP)} trait mappings")
    else:
        print(f"Warning: {map_file} not found, using raw trait names")


def load_champion_traits_map():
    """Load champion -> traits mapping from JSONL file."""
    global CHAMPION_TRAITS_MAP
    traits_file = GAME_DATA_DIR / "champion_traits.jsonl"
    if not traits_file.exists():
        print(f"Warning: {traits_file} not found, falling back to traits_string")
        return

    champion_traits: dict[str, list[str]] = {}
    with open(traits_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            champion_api = record.get("champion_apiName")
            trait_api = record.get("trait_apiName")
            if not champion_api or not trait_api:
                continue
            champion_traits.setdefault(champion_api, []).append(trait_api)

    CHAMPION_TRAITS_MAP = champion_traits
    print(f"Loaded traits for {len(CHAMPION_TRAITS_MAP)} champions")


def normalize_trait_name(api_name: str) -> str:
    """Convert API trait name to display name."""
    payload = TRAIT_ID_MAP.get(api_name)
    if isinstance(payload, dict):
        return payload.get("displayName", api_name)
    if isinstance(payload, str):
        # Backward compatibility with slug -> apiName maps.
        alias = TRAIT_ID_MAP.get(payload)
        if isinstance(alias, dict):
            return alias.get("displayName", api_name)
        return payload
    return api_name


def build_traits_from_units(units: list[str]) -> list[dict[str, int]]:
    """Build trait counts from unit list using champion trait map."""
    if not CHAMPION_TRAITS_MAP:
        return []

    trait_counts: Counter[str] = Counter()
    for unit in units:
        traits = CHAMPION_TRAITS_MAP.get(unit, [])
        for trait_api in traits:
            display_name = normalize_trait_name(trait_api)
            trait_counts[display_name] += 1

    return [
        {"name": trait_name, "count": count}
        for trait_name, count in trait_counts.items()
    ]


def calculate_tier(avg_placement: float) -> str:
    """Calculate tier based on average placement."""
    if avg_placement < TIER_THRESHOLDS["S"]:
        return "S"
    elif avg_placement < TIER_THRESHOLDS["A"]:
        return "A"
    elif avg_placement < TIER_THRESHOLDS["B"]:
        return "B"
    return "C"


def calculate_cluster_stats(cluster_data: dict) -> dict:
    """Calculate placement stats for a single cluster using placement buckets when available."""
    overall = cluster_data.get("overall", {})
    places = overall.get("places") or cluster_data.get("places") or []

    if places:
        places = places[:8]
        total_games = sum(places)
        if total_games:
            weighted_sum = sum((idx + 1) * count for idx, count in enumerate(places))
            avg_placement = weighted_sum / total_games
            top4_rate = (sum(places[:4]) / total_games) * 100
            win_rate = (places[0] / total_games) * 100
            return {
                "total_games": total_games,
                "avg_placement": avg_placement,
                "top4_rate": top4_rate,
                "win_rate": win_rate,
            }

    avg_placement = overall.get("avg", 5.0)
    total_games = overall.get("count", 0)
    top4_rate = max(0, min(100, (8 - avg_placement) / 4 * 100))
    win_rate = max(0, min(50, (5 - avg_placement) * 10))
    return {
        "total_games": total_games,
        "avg_placement": avg_placement,
        "top4_rate": top4_rate,
        "win_rate": win_rate,
    }


def fetch_metatft_data():
    """
    Fetch composition data from MetaTFT API.

    Returns:
        dict: Raw API response or None if fetch fails
    """
    print("Fetching comps data from MetaTFT API...")
    print(f"URL: {METATFT_COMPS_URL}")

    try:
        response = requests.get(
            METATFT_COMPS_URL, params=METATFT_COMPS_PARAMS, headers=HEADERS, timeout=30
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching MetaTFT API: {e}")
        return None

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None

    print("Successfully fetched MetaTFT data")
    return data


def fetch_metatft_stats():
    """Fetch composition stats from MetaTFT API with rank filter."""
    print("Fetching stats data from MetaTFT API...")
    print(f"URL: {METATFT_STATS_URL}")

    try:
        response = requests.get(
            METATFT_STATS_URL, params=METATFT_STATS_PARAMS, headers=HEADERS, timeout=30
        )
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching MetaTFT stats API: {e}")
        return None

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None

    print("Successfully fetched MetaTFT stats")
    return data


def build_stats_by_cluster(stats_data):
    """Build stats lookup keyed by cluster ID."""
    if not stats_data:
        return {}, 0, None

    results = stats_data.get("results", [])
    total_games = 0
    stats_by_cluster = {}

    for entry in results:
        cluster_id = str(entry.get("cluster", "")).strip()
        if not cluster_id or cluster_id in {"-1"}:
            continue

        places = entry.get("places", []) or []
        count = entry.get("count", 0)
        total_place_count = sum(places) if places else 0

        if total_place_count > 0:
            place_sum = sum(
                (idx + 1) * place_count for idx, place_count in enumerate(places)
            )
            avg_placement = place_sum / total_place_count
            top4_rate = (sum(places[:4]) / total_place_count) * 100
            win_rate = (places[0] / total_place_count) * 100
        else:
            avg_placement = 5.0
            top4_rate = 0.0
            win_rate = 0.0

        stats_by_cluster[cluster_id] = {
            "avg_placement": avg_placement,
            "games_played": count,
            "top4_rate": top4_rate,
            "win_rate": win_rate,
        }
        total_games += count

    return stats_by_cluster, total_games, stats_data.get("tft_set")


def extract_comps_data(
    raw_data, stats_by_cluster=None, stats_total_games=0, stats_tft_set=None
):
    """
    Extract and normalize composition data from MetaTFT API response.

    Args:
        raw_data: Raw API response

    Returns:
        dict: Normalized composition data with tiers
    """
    if not raw_data:
        return None

    try:
        # Navigate to cluster details
        results = raw_data.get("results", {})
        data = results.get("data", {})
        cluster_details = data.get("cluster_details", {})
        tft_set = stats_tft_set or data.get("tft_set", "TFTSet16")

        # Extract patch from set name (e.g., TFTSet16 -> 16.x)
        patch = tft_set.replace("TFTSet", "") if tft_set else "unknown"

        comps = []
        total_games = stats_total_games

        for cluster_id, cluster_data in cluster_details.items():
            stats = calculate_cluster_stats(cluster_data)
            games_played = stats["total_games"]
            avg_placement = stats["avg_placement"]
            tier = calculate_tier(avg_placement)

            # Parse units from units_string
            units_string = cluster_data.get("units_string", "")
            units = [u.strip() for u in units_string.split(",") if u.strip()]

            # Build traits from units using champion trait map
            traits = build_traits_from_units(units)

            # Fallback: parse traits_string if champion trait map is missing
            if not traits:
                traits_string = cluster_data.get("traits_string", "")
                for trait in traits_string.split(","):
                    trait = trait.strip()
                    if trait:
                        # Extract trait name and count (e.g., "TFT16_Piltover_2" -> {"name": "Piltover", "count": 2})
                        parts = trait.replace("TFT16_", "").rsplit("_", 1)
                        if len(parts) == 2 and parts[1].isdigit():
                            api_name = parts[0]
                            count = int(parts[1])
                            # Normalize trait name to display name
                            display_name = normalize_trait_name(api_name)
                            traits.append({"name": display_name, "count": count})

            # Extract builds (top 3)
            builds = []
            for build in cluster_data.get("builds", [])[:3]:
                builds.append(
                    {
                        "unit": build.get("unit", "").replace("TFT16_", ""),
                        "items": [
                            item.replace("TFT_Item_", "")
                            for item in build.get("buildName", [])
                        ],
                        "games": build.get("count", 0),
                        "avg_placement": round(build.get("avg", 0), 2),
                        "place_change": round(build.get("place_change", 0), 3),
                    }
                )

            top4_rate = round(stats["top4_rate"], 2)
            win_rate = round(stats["win_rate"], 2)

            comp = {
                "cluster_id": int(cluster_id) if cluster_id.isdigit() else cluster_id,
                "tier": tier,
                "name": cluster_data.get("name_string", "Unknown Comp"),
                "units": units,
                "traits": traits,
                "avg_placement": round(avg_placement, 2),
                "games_played": games_played,
                "top4_rate": round(top4_rate, 2),
                "win_rate": round(win_rate, 2),
                "difficulty": round(cluster_data.get("difficulty", 0), 3),
                "levelling": cluster_data.get("levelling", "Standard"),
                "builds": builds,
            }

            comps.append(comp)

        # Sort by tier (S > A > B > C) then by avg placement
        tier_order = {"S": 0, "A": 1, "B": 2, "C": 3}
        comps.sort(key=lambda x: (tier_order.get(x["tier"], 4), x["avg_placement"]))

        # Limit to top N comps
        comps = comps[:TOP_COMPS_LIMIT]

        result = {
            "patch": patch,
            "source": "metatft",
            "total_games": total_games,
            "total_comps": len(comps),
            "tier_counts": {
                "S": sum(1 for c in comps if c["tier"] == "S"),
                "A": sum(1 for c in comps if c["tier"] == "A"),
                "B": sum(1 for c in comps if c["tier"] == "B"),
                "C": sum(1 for c in comps if c["tier"] == "C"),
            },
            "comps": comps,
        }

        print(f"Extracted top {len(comps)} compositions")
        print(f"  S-tier: {result['tier_counts']['S']}")
        print(f"  A-tier: {result['tier_counts']['A']}")
        print(f"  B-tier: {result['tier_counts']['B']}")
        print(f"  C-tier: {result['tier_counts']['C']}")
        print(f"Total games analyzed: {total_games:,}")

        return result

    except (KeyError, TypeError) as e:
        print(f"Error extracting comp data: {e}")
        import traceback

        traceback.print_exc()
        return None


def save_comps_data(data):
    """Save composition data to JSON file."""
    if not data:
        print("No data to save")
        return False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_file = DATA_DIR / "comps.json"

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved composition data to {output_file}")
    return True


def update_timestamp():
    """Update the last-fetched timestamp."""
    timestamp_file = DATA_DIR / "last_updated.json"
    data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "source": "metatft",
        "url": METATFT_STATS_URL,
        "automated": True,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(timestamp_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Updated timestamp: {data['last_updated']}")


def main():
    print("=" * 50)
    print("TFT Meta Data Fetcher (MetaTFT API)")
    print("=" * 50)
    print(f"Running at: {datetime.now(timezone.utc).isoformat()}")
    print()

    # Load trait ID mapping for name normalization
    load_trait_id_map()
    load_champion_traits_map()

    # Fetch data from MetaTFT API
    stats_data = fetch_metatft_stats()
    stats_by_cluster, stats_total_games, stats_tft_set = build_stats_by_cluster(
        stats_data
    )
    raw_data = fetch_metatft_data()

    if raw_data:
        # Extract and save composition data
        comps_data = extract_comps_data(
            raw_data,
            stats_by_cluster=stats_by_cluster,
            stats_total_games=stats_total_games,
            stats_tft_set=stats_tft_set,
        )
        if comps_data:
            save_comps_data(comps_data)
        else:
            print("Failed to extract comp data")
    else:
        print("Failed to fetch data - skipping save")

    # Update timestamp
    update_timestamp()

    print()
    print("Data fetch complete!")
    print("=" * 50)


if __name__ == "__main__":
    main()
