#!/usr/bin/env python3
"""
TFT Match Data Preprocessor

Normalizes Riot API match data for use with the TFT Coach ML pipeline.
Handles:
- Trait name normalization (strips TFT16_/Set16_ prefixes)
- Column name standardization
- Backend version to patch mapping
- Deduplication with existing data

Usage:
    python scripts/process_riot_matches.py
"""

import re
import pandas as pd
from pathlib import Path
from typing import Optional


# =============================================================================
# CONFIGURATION
# =============================================================================

# Riot backend version -> actual game patch mapping
VERSION_MAP = {
    '15.24': '16.1',
    '16.1': '16.2',
    '16.2': '16.3',
    '16.3': '16.4',  # Future-proofing
}

# Column name standardization
COLUMN_RENAME_MAP = {
    '1-Aug': 'aug1',
    '2-Aug': 'aug2',
    '3-Aug': 'aug3',
}

# File paths (relative to project root)
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_FILE = PROJECT_ROOT / 'tft_matches_since_set16.csv'
EXISTING_FILE = PROJECT_ROOT / 'data' / 'personal' / 'tft_since_16_2_enhanced.csv'
OUTPUT_FILE = PROJECT_ROOT / 'data' / 'personal' / 'tft_all_matches.csv'


# =============================================================================
# NORMALIZATION FUNCTIONS
# =============================================================================

def normalize_traits(traits_str: str) -> str:
    """
    Normalize trait string by removing TFT16_/Set16_ prefixes.

    Input:  "TFT16_Brawler:2 | TFT16_Void:3"
    Output: "Brawler:2 | Void:3"
    """
    if pd.isna(traits_str) or not traits_str:
        return ''

    # Remove both TFT16_ and Set16_ prefixes
    normalized = re.sub(r'(TFT16_|Set16_)', '', str(traits_str))
    return normalized


def normalize_units(units_str: str) -> str:
    """
    Normalize unit string - units should already be clean but double-check.
    Also handles lowercase unit names (e.g., tft16_atakhan -> Atakhan).

    Input:  "tft16_atakhan_1*() | Sion_2*(BrambleVest)"
    Output: "Atakhan_1*() | Sion_2*(BrambleVest)"
    """
    if pd.isna(units_str) or not units_str:
        return ''

    # Remove TFT16_ prefix (case-insensitive)
    normalized = re.sub(r'(?i)tft16_', '', str(units_str))

    # Capitalize first letter of each unit name
    def capitalize_unit(match):
        return match.group(0).capitalize()

    # Match unit names at start of each unit entry
    normalized = re.sub(r'(?<=\| )[a-z]|^[a-z]', capitalize_unit, normalized)

    return normalized


def extract_backend_version(game_version: str) -> str:
    """
    Extract backend version number from game_version string.

    Input:  "Linux Version 16.2.741.3171 (Jan 26 2026/11:02:39) [PUBLIC] <Releases/16.2>"
    Output: "16.2"
    """
    if pd.isna(game_version) or not game_version:
        return ''

    # Match version pattern like "Version 16.2" or "Version 15.24"
    match = re.search(r'Version (\d+\.\d+)', str(game_version))
    if match:
        return match.group(1)
    return ''


def map_to_actual_patch(backend_version: str) -> str:
    """
    Map Riot backend version to actual game patch.

    Backend 15.24 -> Patch 16.1
    Backend 16.1  -> Patch 16.2
    Backend 16.2  -> Patch 16.3
    """
    return VERSION_MAP.get(backend_version, backend_version)


# =============================================================================
# DATA PROCESSING
# =============================================================================

def load_and_standardize(filepath: Path) -> Optional[pd.DataFrame]:
    """Load CSV and standardize column names."""
    if not filepath.exists():
        print(f"  File not found: {filepath}")
        return None

    print(f"  Loading {filepath.name}...")
    df = pd.read_csv(filepath)
    print(f"    Loaded {len(df)} rows")

    # Rename columns if needed
    df = df.rename(columns=COLUMN_RENAME_MAP)

    return df


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all normalizations to dataframe."""
    df = df.copy()

    # Normalize traits
    if 'traits_active' in df.columns:
        print("  Normalizing traits...")
        df['traits_active'] = df['traits_active'].apply(normalize_traits)

    # Normalize units
    if 'final_board_units' in df.columns:
        print("  Normalizing units...")
        df['final_board_units'] = df['final_board_units'].apply(normalize_units)

    # Extract and map patch version
    if 'game_version' in df.columns:
        print("  Mapping patch versions...")
        df['backend_version'] = df['game_version'].apply(extract_backend_version)
        df['patch'] = df['backend_version'].apply(map_to_actual_patch)

    return df


def deduplicate(new_df: pd.DataFrame, existing_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Remove matches that already exist in the existing dataset."""
    if existing_df is None or len(existing_df) == 0:
        return new_df

    existing_ids = set(existing_df['match_id'].unique())
    before_count = len(new_df)

    new_df = new_df[~new_df['match_id'].isin(existing_ids)]

    removed = before_count - len(new_df)
    if removed > 0:
        print(f"  Removed {removed} duplicate matches")

    return new_df


def print_summary(df: pd.DataFrame):
    """Print summary statistics."""
    print("\n" + "=" * 60)
    print("PROCESSED DATA SUMMARY")
    print("=" * 60)

    print(f"\nTotal matches: {len(df)}")

    # Placement stats
    avg_placement = df['placement'].mean()
    top4_rate = (df['placement'] <= 4).mean() * 100
    wins = (df['placement'] == 1).sum()
    print(f"Average placement: {avg_placement:.2f}")
    print(f"Top 4 rate: {top4_rate:.1f}%")
    print(f"Wins: {wins}")

    # Patch distribution
    if 'patch' in df.columns:
        print("\nGames by patch:")
        patch_counts = df['patch'].value_counts().sort_index()
        for patch, count in patch_counts.items():
            patch_top4 = (df[df['patch'] == patch]['placement'] <= 4).mean() * 100
            print(f"  {patch}: {count} games ({patch_top4:.1f}% top 4)")

    # Queue distribution
    if 'queue_id' in df.columns:
        print("\nGames by queue:")
        queue_counts = df['queue_id'].value_counts()
        queue_names = {1100: 'Ranked', 1090: 'Normal', 1220: 'Hyper Roll'}
        for queue_id, count in queue_counts.items():
            name = queue_names.get(queue_id, f'Queue {queue_id}')
            print(f"  {name}: {count} games")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("TFT Match Data Preprocessor")
    print("=" * 60)

    # Load new data
    print("\n[1/4] Loading data...")
    new_df = load_and_standardize(INPUT_FILE)
    if new_df is None:
        print("Error: Could not load input file")
        return

    # Load existing data for deduplication (optional)
    existing_df = load_and_standardize(EXISTING_FILE)

    # Process new data
    print("\n[2/4] Processing data...")
    processed_df = process_dataframe(new_df)

    # Deduplicate
    print("\n[3/4] Deduplicating...")
    if existing_df is not None:
        # Also process existing data to ensure consistency
        existing_processed = process_dataframe(existing_df)

        # Combine and deduplicate
        combined_df = pd.concat([processed_df, existing_processed], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['match_id'], keep='first')
        final_df = combined_df
        print(f"  Combined dataset: {len(final_df)} unique matches")
    else:
        final_df = processed_df
        final_df = final_df.drop_duplicates(subset=['match_id'], keep='first')

    # Sort by game datetime (most recent first)
    if 'game_datetime' in final_df.columns:
        final_df = final_df.sort_values('game_datetime', ascending=False)

    # Save output
    print("\n[4/4] Saving output...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"  Saved to {OUTPUT_FILE}")

    # Print summary
    print_summary(final_df)

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()
