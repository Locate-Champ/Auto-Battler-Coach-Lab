#!/usr/bin/env python3
"""
Script to organize and parse TFT API data files from Meta TFT.
This script processes the JSON files from the API Data folder and organizes them
into a structured format for the TFT Coach application.
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

# Base paths
BASE_DIR = Path(__file__).parent.parent
API_DATA_SOURCE = BASE_DIR / "TFT 16.3 API Data" / "API Data"
DATA_DIR = BASE_DIR / "data"

# Target directories
API_RAW_DIR = DATA_DIR / "api" / "raw"
API_PROCESSED_DIR = DATA_DIR / "api" / "processed"
META_DIR = DATA_DIR / "meta"
GAME_DATA_DIR = DATA_DIR / "game_data"


def ensure_directories():
    """Create necessary directory structure."""
    dirs = [API_RAW_DIR, API_PROCESSED_DIR, META_DIR, GAME_DATA_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Directory structure created")


def copy_raw_files():
    """Copy raw API files to the api/raw directory for reference."""
    if not API_DATA_SOURCE.exists():
        print(f"[WARN] Source directory not found: {API_DATA_SOURCE}")
        return

    for json_file in API_DATA_SOURCE.glob("*.json"):
        if json_file.name == "blank":
            continue
        dest = API_RAW_DIR / json_file.name
        shutil.copy2(json_file, dest)
        print(f"[OK] Copied {json_file.name} to api/raw/")


def parse_game_data():
    """Parse TFTSet16_latest_en_us.json into separate organized files."""
    source_file = API_DATA_SOURCE / "TFTSet16_latest_en_us.json"
    if not source_file.exists():
        print(f"[WARN] Game data file not found: {source_file}")
        return

    with open(source_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract and save each data type
    extractions = {
        'units': 'units_set16.json',
        'items': 'items_set16.json',
        'augments': 'augments_set16.json',
        'traits': 'traits_set16.json',
        'armory_items': 'armory_items_set16.json',
        'augmentOdds': 'augment_odds_set16.json',
        'encounters': 'encounters_set16.json',
        'roles': 'roles_set16.json',
    }

    for key, filename in extractions.items():
        if key in data and data[key]:
            output_path = API_PROCESSED_DIR / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data[key], f, indent=2, ensure_ascii=False)
            count = len(data[key]) if isinstance(data[key], (list, dict)) else 1
            print(f"[OK] Extracted {key}: {count} entries -> {filename}")

    # Create a lookup/index file for quick reference
    index = {
        'set': 'TFTSet16',
        'patch': '16.3',
        'generated': datetime.now().isoformat(),
        'counts': {
            'units': len(data.get('units', [])),
            'items': len(data.get('items', [])),
            'augments': len(data.get('augments', [])),
            'traits': len(data.get('traits', [])),
            'armory_items': len(data.get('armory_items', [])),
        }
    }
    with open(API_PROCESSED_DIR / 'index.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)
    print(f"[OK] Created index.json with data summary")


def parse_comps_data():
    """Parse composition data files."""
    # comps_data.json - Main composition cluster data
    source_file = API_DATA_SOURCE / "comps_data.json"
    if source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'results' in data and 'data' in data['results']:
            cluster_details = data['results']['data'].get('cluster_details', {})

            # Save cluster details as compositions
            output = {
                'cluster_id': data['results']['data'].get('cluster_id'),
                'tft_set': data['results']['data'].get('tft_set'),
                'compositions': cluster_details,
                'updated': data.get('updated'),
            }

            with open(META_DIR / 'compositions.json', 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            print(f"[OK] Parsed comps_data.json: {len(cluster_details)} compositions -> compositions.json")


def parse_comps_stats():
    """Parse composition statistics."""
    source_file = API_DATA_SOURCE / "comps_stats.json"
    if source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Reorganize stats for easier consumption
        stats = []
        if 'results' in data:
            for entry in data['results']:
                if entry.get('cluster'):  # Skip empty cluster entries
                    stats.append({
                        'cluster_id': entry['cluster'],
                        'placements': entry.get('places', []),
                        'total_games': entry.get('count', 0),
                    })

        output = {
            'tft_set': data.get('tft_set'),
            'queue_id': data.get('queue_id'),
            'updated': data.get('updated'),
            'filter': data.get('filter_adjustment', {}).get('rank_filter'),
            'stats': stats,
        }

        with open(META_DIR / 'comp_stats.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[OK] Parsed comps_stats.json: {len(stats)} comp stats -> comp_stats.json")


def parse_comp_builds():
    """Parse composition build variations."""
    source_file = API_DATA_SOURCE / "comp_builds.json"
    if source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        builds_output = {}
        if 'results' in data:
            for cluster_id, build_data in data['results'].items():
                builds_output[cluster_id] = {
                    'builds': build_data.get('builds', []),
                    'overall': build_data.get('overall', {}),
                }

        output = {
            'tft_set': data.get('tft_set'),
            'cluster_id': data.get('cluster_id'),
            'updated': data.get('updated'),
            'builds': builds_output,
        }

        with open(META_DIR / 'comp_builds.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[OK] Parsed comp_builds.json: {len(builds_output)} comp builds -> comp_builds.json")


def parse_comp_options():
    """Parse composition options (augments, items per comp)."""
    source_file = API_DATA_SOURCE / "comp_options.json"
    if source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        options_output = {}
        if 'results' in data and 'options' in data['results']:
            options_output = data['results']['options']

        output = {
            'tft_set': data.get('tft_set'),
            'cluster_id': data.get('cluster_id'),
            'updated': data.get('updated'),
            'options': options_output,
        }

        with open(META_DIR / 'comp_options.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[OK] Parsed comp_options.json: {len(options_output)} comp options -> comp_options.json")


def parse_unit_items():
    """Parse unit item statistics."""
    source_file = API_DATA_SOURCE / "unit_items_processed.json"
    if source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        output = {
            'tft_set': data.get('tft_set'),
            'queue_id': data.get('queue_id'),
            'updated': data.get('updated'),
            'units': data.get('units', {}),
            'item_names': data.get('itemNames', {}),
            'overall': data.get('overall', {}),
        }

        with open(META_DIR / 'unit_items.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[OK] Parsed unit_items_processed.json: {len(output['units'])} units -> unit_items.json")


def parse_percentiles():
    """Parse ranking percentile data."""
    source_file = API_DATA_SOURCE / "percentiles.json"
    if source_file.exists():
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        output = {
            'updated': data.get('updated'),
            'percentiles': data.get('percentiles', {}),
            'overall_percentiles': data.get('overall_percentiles', {}),
        }

        with open(META_DIR / 'percentiles.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"[OK] Parsed percentiles.json: {len(output['percentiles'])} percentile entries -> percentiles.json")


def create_summary():
    """Create a summary file documenting the data organization."""
    summary = {
        'description': 'TFT Coach API Data - Organized from Meta TFT',
        'source': 'TFT 16.3 API Data/API Data',
        'processed_date': datetime.now().isoformat(),
        'structure': {
            'data/api/raw/': 'Original API JSON files for reference',
            'data/api/processed/': 'Parsed game data (units, items, augments, traits)',
            'data/meta/': 'Meta statistics (compositions, builds, item stats)',
        },
        'files': {
            'api/processed/': [
                'units_set16.json - All champion/unit data',
                'items_set16.json - All item data',
                'augments_set16.json - All augment data',
                'traits_set16.json - All trait data',
                'armory_items_set16.json - Armory item data',
                'augment_odds_set16.json - Augment appearance odds',
                'encounters_set16.json - PvE encounter data',
                'roles_set16.json - Unit role classifications',
                'index.json - Data summary and counts',
            ],
            'meta/': [
                'compositions.json - Composition cluster data with details',
                'comp_stats.json - Composition placement statistics',
                'comp_builds.json - Build variations per composition',
                'comp_options.json - Augment/item options per comp',
                'unit_items.json - Best items per unit statistics',
                'percentiles.json - Ranking percentile data',
            ],
        }
    }

    with open(DATA_DIR / 'API_DATA_README.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[OK] Created API_DATA_README.json with data documentation")


def main():
    print("=" * 60)
    print("TFT API Data Organization Script")
    print("=" * 60)
    print()

    print("[1/9] Creating directory structure...")
    ensure_directories()

    print("\n[2/9] Copying raw API files...")
    copy_raw_files()

    print("\n[3/9] Parsing game data (units, items, augments, traits)...")
    parse_game_data()

    print("\n[4/9] Parsing composition data...")
    parse_comps_data()

    print("\n[5/9] Parsing composition statistics...")
    parse_comps_stats()

    print("\n[6/9] Parsing composition builds...")
    parse_comp_builds()

    print("\n[7/9] Parsing composition options...")
    parse_comp_options()

    print("\n[8/9] Parsing unit item statistics...")
    parse_unit_items()

    print("\n[9/9] Parsing percentile data...")
    parse_percentiles()

    print("\n[FINAL] Creating summary documentation...")
    create_summary()

    print("\n" + "=" * 60)
    print("Data organization complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
