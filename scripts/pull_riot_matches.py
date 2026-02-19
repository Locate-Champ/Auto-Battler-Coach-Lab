#!/usr/bin/env python3
"""
Riot API Match History Fetcher for TFT
Pulls all TFT matches since December 3, 2025 (Set 16.1 launch)

Usage:
    Add RIOT_API_KEY to your .env file
    python pull_riot_matches.py
"""

import os
import sys
import time
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional
import requests
from dotenv import load_dotenv

# Load .env file from the same directory as this script
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# =============================================================================
# CONFIGURATION
# =============================================================================

GAME_NAME = "Karina Super Fan"
TAG_LINE = "8148"
REGION = "americas"  # NA uses americas routing

# December 3, 2025 00:00:00 UTC in milliseconds
START_DATE_MS = 1733184000000

# API endpoints
ACCOUNT_API = f"https://{REGION}.api.riotgames.com/riot/account/v1/accounts/by-riot-id"
MATCH_API = f"https://{REGION}.api.riotgames.com/tft/match/v1/matches"

# Rate limiting (conservative)
REQUESTS_PER_SECOND = 15
REQUEST_DELAY = 1.0 / REQUESTS_PER_SECOND

# Output file
OUTPUT_FILE = "tft_matches_since_set16.csv"

# =============================================================================
# API FUNCTIONS
# =============================================================================


def get_api_key() -> str:
    """Get API key from .env file, environment, or prompt."""
    api_key = os.environ.get("RIOT_API_KEY")
    if not api_key:
        api_key = input("Enter your Riot API key: ").strip()
    if not api_key:
        print("Error: No API key provided")
        print("Add RIOT_API_KEY=your_key to .env file or set environment variable")
        sys.exit(1)
    return api_key


def make_request(url: str, api_key: str, retries: int = 3) -> Optional[dict]:
    """Make API request with retry logic."""
    headers = {"X-Riot-Token": api_key}

    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                # Rate limited - wait and retry
                retry_after = int(response.headers.get("Retry-After", 10))
                print(f"  Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
            elif response.status_code == 404:
                return None
            else:
                print(f"  Error {response.status_code}: {response.text[:100]}")
                time.sleep(2**attempt)

        except requests.exceptions.RequestException as e:
            print(f"  Request error: {e}")
            time.sleep(2**attempt)

    return None


def get_puuid(game_name: str, tag_line: str, api_key: str) -> Optional[str]:
    """Get PUUID from Riot ID."""
    url = f"{ACCOUNT_API}/{game_name}/{tag_line}"
    print(f"Looking up PUUID for {game_name}#{tag_line}...")

    data = make_request(url, api_key)
    if data:
        puuid = data.get("puuid")
        print(f"  Found PUUID: {puuid[:20]}...")
        return puuid
    return None


def get_match_ids(puuid: str, api_key: str, start_time: int, count: int = 100) -> list:
    """Get match IDs for a player since start_time."""
    all_match_ids = []
    start_index = 0

    while True:
        url = f"{MATCH_API}/by-puuid/{puuid}/ids"
        url += f"?startTime={start_time // 1000}"  # API uses seconds, not ms
        url += f"&start={start_index}&count={count}"

        print(f"  Fetching matches {start_index} to {start_index + count}...")
        time.sleep(REQUEST_DELAY)

        match_ids = make_request(url, api_key)

        if not match_ids or len(match_ids) == 0:
            break

        all_match_ids.extend(match_ids)
        print(f"    Found {len(match_ids)} matches (total: {len(all_match_ids)})")

        if len(match_ids) < count:
            break

        start_index += count

    return all_match_ids


def get_match_details(match_id: str, api_key: str) -> Optional[dict]:
    """Get detailed match data."""
    url = f"{MATCH_API}/{match_id}"
    time.sleep(REQUEST_DELAY)
    return make_request(url, api_key)


# =============================================================================
# DATA EXTRACTION
# =============================================================================


def extract_player_data(match: dict, puuid: str) -> Optional[dict]:
    """Extract player-specific data from match."""
    info = match.get("info", {})
    metadata = match.get("metadata", {})

    # Find our participant
    participant = None
    for p in info.get("participants", []):
        if p.get("puuid") == puuid:
            participant = p
            break

    if not participant:
        return None

    # Extract traits
    traits = participant.get("traits", [])
    traits_active = " | ".join(
        [
            f"{t['name'].replace('Set16_', '')}:{t['tier_current']}"
            for t in traits
            if t.get("tier_current", 0) > 0
        ]
    )

    # Extract units with items and star level
    units = participant.get("units", [])
    unit_strings = []
    for unit in units:
        name = unit.get("character_id", "").replace("TFT16_", "")
        stars = unit.get("tier", 1)
        items = unit.get("itemNames", [])
        items_clean = [
            i.replace("TFT_Item_", "").replace("TFT4_Item_", "") for i in items
        ]
        items_str = ",".join(items_clean) if items_clean else ""
        unit_strings.append(f"{name}_{stars}*({items_str})")

    final_board_units = " | ".join(unit_strings)

    # Extract augments
    augments = participant.get("augments", [])
    aug1 = augments[0] if len(augments) > 0 else ""
    aug2 = augments[1] if len(augments) > 1 else ""
    aug3 = augments[2] if len(augments) > 2 else ""

    return {
        "match_id": metadata.get("match_id", ""),
        "game_datetime": info.get("game_datetime", 0),
        "game_length_sec": info.get("game_length", 0),
        "queue_id": info.get("queue_id", 0),
        "game_version": info.get("game_version", ""),
        "placement": participant.get("placement", 0),
        "level": participant.get("level", 0),
        "gold_left": participant.get("gold_left", 0),
        "last_round": participant.get("last_round", 0),
        "time_eliminated": participant.get("time_eliminated", 0),
        "total_damage_to_players": participant.get("total_damage_to_players", 0),
        "players_eliminated": participant.get("players_eliminated", 0),
        "aug1": aug1,
        "aug2": aug2,
        "aug3": aug3,
        "traits_active": traits_active,
        "final_board_units": final_board_units,
    }


# =============================================================================
# MAIN
# =============================================================================


def main():
    print("=" * 60)
    print("TFT Match History Fetcher")
    print(f"Player: {GAME_NAME}#{TAG_LINE}")
    print(f"Region: {REGION}")
    print(f"Start Date: {datetime.fromtimestamp(START_DATE_MS / 1000)}")
    print("=" * 60)

    # Get API key
    api_key = get_api_key()

    # Get PUUID
    puuid = get_puuid(GAME_NAME, TAG_LINE, api_key)
    if not puuid:
        print("Error: Could not find player")
        sys.exit(1)

    # Get match IDs
    print("\nFetching match IDs since Dec 3, 2025...")
    match_ids = get_match_ids(puuid, api_key, START_DATE_MS)
    print(f"\nFound {len(match_ids)} total matches")

    if not match_ids:
        print("No matches found!")
        sys.exit(0)

    # Fetch match details
    print("\nFetching match details...")
    matches_data = []

    for i, match_id in enumerate(match_ids):
        print(f"  [{i + 1}/{len(match_ids)}] {match_id}...", end=" ")

        match = get_match_details(match_id, api_key)
        if match:
            player_data = extract_player_data(match, puuid)
            if player_data:
                matches_data.append(player_data)
                print(f"Placement: {player_data['placement']}")
            else:
                print("Could not extract data")
        else:
            print("Failed to fetch")

    # Write CSV
    if matches_data:
        print(f"\nWriting {len(matches_data)} matches to {OUTPUT_FILE}...")

        fieldnames = [
            "match_id",
            "game_datetime",
            "game_length_sec",
            "queue_id",
            "game_version",
            "placement",
            "level",
            "gold_left",
            "last_round",
            "time_eliminated",
            "total_damage_to_players",
            "players_eliminated",
            "aug1",
            "aug2",
            "aug3",
            "traits_active",
            "final_board_units",
        ]

        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(matches_data)

        print(f"Done! Saved to {OUTPUT_FILE}")

        # Print summary
        placements = [m["placement"] for m in matches_data]
        avg_placement = sum(placements) / len(placements)
        top4_rate = len([p for p in placements if p <= 4]) / len(placements) * 100
        wins = len([p for p in placements if p == 1])

        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total Games: {len(matches_data)}")
        print(f"Average Placement: {avg_placement:.2f}")
        print(f"Top 4 Rate: {top4_rate:.1f}%")
        print(f"Wins: {wins}")
    else:
        print("No match data extracted!")


if __name__ == "__main__":
    main()
