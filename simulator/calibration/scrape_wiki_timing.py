"""
Scrape League of Legends Wiki for champion timing data.

The wiki has authoritative data on:
- Attack windup percentage
- Missile speed (projectile speed for ranged autos)
- Attack speed ratio
- Ability cast times

Note: TFT may modify some values, but base mechanics usually match.
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import urllib.request
import urllib.error

# Champions to scrape (TFT Set 16 priority list)
# Map TFT name -> Wiki page name (some differ)
CHAMPION_MAPPING = {
    # Tier 1 - Critical (6-range ADCs)
    "TFT16_Caitlyn": "Caitlyn",
    "TFT16_KogMaw": "Kog'Maw",
    "TFT16_Teemo": "Teemo",
    "TFT16_Vayne": "Vayne",
    "TFT16_KaiSa": "Kai'Sa",
    "TFT16_Ziggs": "Ziggs",

    # Tier 2 - High priority
    "TFT16_Tristana": "Tristana",
    "TFT16_Draven": "Draven",
    "TFT16_MissFortune": "Miss_Fortune",
    "TFT16_Aphelios": "Aphelios",
    "TFT16_Ashe": "Ashe",
    "TFT16_Jhin": "Jhin",
    "TFT16_Kalista": "Kalista",
    "TFT16_Jinx": "Jinx",
    "TFT16_Ahri": "Ahri",
    "TFT16_Kennen": "Kennen",

    # Tier 3 - Medium priority
    "TFT16_Lulu": "Lulu",
    "TFT16_TwistedFate": "Twisted_Fate",
    "TFT16_Zoe": "Zoe",
    "TFT16_Sona": "Sona",
    "TFT16_Lux": "Lux",
    "TFT16_Anivia": "Anivia",
    "TFT16_Lissandra": "Lissandra",
    "TFT16_Malzahar": "Malzahar",
    "TFT16_Annie": "Annie",
    "TFT16_Kindred": "Kindred",
    "TFT16_Azir": "Azir",
    "TFT16_Veigar": "Veigar",
    "TFT16_Orianna": "Orianna",

    # Melee carries
    "TFT16_Aatrox": "Aatrox",
    "TFT16_Yasuo": "Yasuo",
    "TFT16_Yone": "Yone",
    "TFT16_Sylas": "Sylas",
    "TFT16_Ekko": "Ekko",
    "TFT16_Fiddlesticks": "Fiddlesticks",
    "TFT16_Warwick": "Warwick",
    "TFT16_Sett": "Sett",
}


@dataclass
class WikiTimingData:
    """Timing data scraped from wiki."""
    champion_name: str
    wiki_page: str

    # Attack stats
    base_attack_speed: Optional[float] = None
    attack_speed_ratio: Optional[float] = None
    windup_percent: Optional[float] = None
    windup_modifier: Optional[float] = None  # Some champs have modified windup
    missile_speed: Optional[int] = None  # Projectile speed for ranged autos
    attack_range: Optional[int] = None

    # Computed
    windup_seconds_at_base: Optional[float] = None  # Windup time at base AS

    # Ability timing (for reference)
    ability_cast_times: Optional[Dict[str, float]] = None

    # Metadata
    source_url: str = ""
    scraped: bool = False
    notes: str = ""


def fetch_wiki_page(champion: str) -> Optional[str]:
    """Fetch raw HTML from League wiki."""
    url = f"https://wiki.leagueoflegends.com/en-us/{champion}"

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"  HTTP Error {e.code} for {champion}")
        return None
    except Exception as e:
        print(f"  Error fetching {champion}: {e}")
        return None


def parse_timing_data(html: str, champion: str) -> WikiTimingData:
    """Parse timing data from wiki HTML."""
    data = WikiTimingData(
        champion_name=champion,
        wiki_page=champion,
        source_url=f"https://wiki.leagueoflegends.com/en-us/{champion}"
    )

    # Extract attack speed ratio
    # Pattern: "Attack speed ratio" followed by value
    as_ratio_match = re.search(r'Attack speed ratio[^0-9]*([0-9.]+)', html, re.IGNORECASE)
    if as_ratio_match:
        data.attack_speed_ratio = float(as_ratio_match.group(1))

    # Extract base attack speed
    # Pattern: "Base AS" or "Base attack speed" followed by value
    base_as_match = re.search(r'Base (?:AS|attack speed)[^0-9]*([0-9.]+)', html, re.IGNORECASE)
    if base_as_match:
        data.base_attack_speed = float(base_as_match.group(1))

    # Extract windup percentage
    # Pattern: "Windup" followed by percentage
    windup_match = re.search(r'[Ww]indup[^0-9%]*([0-9.]+)\s*%', html)
    if windup_match:
        data.windup_percent = float(windup_match.group(1))

    # Extract windup modifier (some champs have this)
    windup_mod_match = re.search(r'windup modifier[^0-9]*([0-9.]+)', html, re.IGNORECASE)
    if windup_mod_match:
        data.windup_modifier = float(windup_mod_match.group(1))

    # Extract missile speed (for ranged champions)
    missile_match = re.search(r'[Mm]issile speed[^0-9]*([0-9]+)', html)
    if missile_match:
        data.missile_speed = int(missile_match.group(1))

    # Also check for "Projectile speed" in basic attacks section
    if not data.missile_speed:
        proj_match = re.search(r'[Pp]rojectile speed[^0-9]*([0-9]+)', html)
        if proj_match:
            data.missile_speed = int(proj_match.group(1))

    # Extract attack range
    range_match = re.search(r'[Rr]ange[^0-9]*([0-9]+)', html)
    if range_match:
        data.attack_range = int(range_match.group(1))

    # Compute windup time at base AS
    if data.base_attack_speed and data.windup_percent:
        # Attack time = 1 / attack_speed
        # Windup time = attack_time * windup_percent / 100
        attack_time = 1 / data.base_attack_speed
        data.windup_seconds_at_base = attack_time * (data.windup_percent / 100)

    data.scraped = True
    return data


def scrape_all_champions() -> Dict[str, WikiTimingData]:
    """Scrape timing data for all priority champions."""
    results = {}

    print("Scraping League Wiki for timing data...")
    print(f"Champions to scrape: {len(CHAMPION_MAPPING)}")

    for tft_name, wiki_name in CHAMPION_MAPPING.items():
        print(f"\n  {wiki_name}...", end=" ")

        html = fetch_wiki_page(wiki_name)
        if not html:
            results[tft_name] = WikiTimingData(
                champion_name=wiki_name,
                wiki_page=wiki_name,
                notes="Failed to fetch"
            )
            continue

        data = parse_timing_data(html, wiki_name)
        results[tft_name] = data

        # Summary
        if data.windup_percent:
            print(f"windup={data.windup_percent}%", end=" ")
        if data.missile_speed:
            print(f"missile={data.missile_speed}", end=" ")
        if data.base_attack_speed:
            print(f"baseAS={data.base_attack_speed}", end=" ")

        # Rate limit
        time.sleep(0.5)

    return results


def merge_with_timing_constants(wiki_data: Dict[str, WikiTimingData], timing_file: Path):
    """Merge wiki data into existing timing_constants.json."""

    with open(timing_file, 'r', encoding='utf-8') as f:
        timing = json.load(f)

    updated = 0
    for tft_name, wiki in wiki_data.items():
        if tft_name not in timing:
            continue

        champ = timing[tft_name]

        # Add wiki data
        if 'wiki_data' not in champ:
            champ['wiki_data'] = {}

        champ['wiki_data'] = {
            'base_attack_speed': wiki.base_attack_speed,
            'attack_speed_ratio': wiki.attack_speed_ratio,
            'windup_percent': wiki.windup_percent,
            'windup_modifier': wiki.windup_modifier,
            'missile_speed': wiki.missile_speed,
            'attack_range': wiki.attack_range,
            'windup_seconds_at_base': wiki.windup_seconds_at_base,
            'source': wiki.source_url,
        }

        # If we don't have extracted timing, use wiki estimate
        if champ['timing']['attack_windup_seconds'] is None and wiki.windup_seconds_at_base:
            champ['timing']['attack_windup_seconds'] = wiki.windup_seconds_at_base
            champ['timing']['source'] = 'wiki_estimate'
            champ['timing']['confidence'] = 'medium'
            champ['timing']['notes'] = f"Estimated from LoL wiki windup {wiki.windup_percent}%"

        updated += 1

    # Save updated timing
    with open(timing_file, 'w', encoding='utf-8') as f:
        json.dump(timing, f, indent=2, ensure_ascii=False)

    print(f"\nUpdated {updated} champions in {timing_file}")


def main():
    script_dir = Path(__file__).parent
    output_file = script_dir / "wiki_timing_data.json"
    timing_file = script_dir.parent / "data" / "timing_constants.json"

    # Scrape
    wiki_data = scrape_all_champions()

    # Save raw wiki data
    output = {
        tft_name: asdict(data)
        for tft_name, data in wiki_data.items()
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n\nSaved wiki data to: {output_file}")

    # Summary
    print("\n=== SUMMARY ===")
    scraped = sum(1 for d in wiki_data.values() if d.scraped)
    with_windup = sum(1 for d in wiki_data.values() if d.windup_percent)
    with_missile = sum(1 for d in wiki_data.values() if d.missile_speed)

    print(f"Successfully scraped: {scraped}/{len(wiki_data)}")
    print(f"With windup data: {with_windup}")
    print(f"With missile speed: {with_missile}")

    # Merge with timing constants
    if timing_file.exists():
        print(f"\nMerging with {timing_file}...")
        merge_with_timing_constants(wiki_data, timing_file)

    # Print useful data
    print("\n=== TIMING DATA ===")
    for tft_name, data in wiki_data.items():
        if data.windup_percent or data.missile_speed:
            print(f"{data.champion_name:15} windup={data.windup_percent or '?':>6}%  missile={data.missile_speed or '?':>5}  baseAS={data.base_attack_speed or '?'}")


if __name__ == "__main__":
    main()
