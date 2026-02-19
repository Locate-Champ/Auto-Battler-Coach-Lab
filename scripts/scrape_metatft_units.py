#!/usr/bin/env python3
"""
Scrape MetaTFT unit pages for ability descriptions and stats.

Uses Playwright to navigate the React SPA and extract:
- Ability descriptions (class="UnitAbilityDescription")
- Champion stats from the Stats tab (class="UnitStatsMenu")

Usage:
    pip install playwright
    playwright install chromium
    python scripts/scrape_metatft_units.py              # Scrape all champions
    python scripts/scrape_metatft_units.py --champion Aatrox  # Single champion
    python scripts/scrape_metatft_units.py --dry-run     # List URLs only
"""

import argparse
import json
import random
import time
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
except ImportError:
    print("Playwright not installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
COMBAT_DATA_PATH = PROJECT_ROOT / "simulator" / "data" / "combat_data.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "metatft_unit_data.json"

# MetaTFT base URL
METATFT_UNITS_URL = "https://www.metatft.com/units"

# Map from our API names to MetaTFT URL slugs
# Most are just the display name, but some need special handling
SPECIAL_URL_SLUGS = {
    "TFT16_KogMaw": "Kog'Maw",
    "TFT16_KaiSa": "Kai'Sa",
    "TFT16_MissFortune": "Miss Fortune",
    "TFT16_DrMundo": "Dr. Mundo",
    "TFT16_RekSai": "Rek'Sai",
    "TFT16_TwistedFate": "Twisted Fate",
    "TFT16_XinZhao": "Xin Zhao",
    "TFT16_JarvanIV": "Jarvan IV",
    "TFT16_LeBlanc": "LeBlanc",
    "TFT16_AurelionSol": "Aurelion Sol",
    "TFT16_BaronNashor": "Baron Nashor",
    "TFT16_RiftHerald": "Rift Herald",
    "TFT16_TahmKench": "Tahm Kench",
    "TFT16_AnnieTibbers": "Tibbers",
    "TFT16_LucianSenna": "Lucian & Senna",
    "TFT16_KobukoYuumi": "Kobuko & Yuumi",
    "TFT16_THex": "T-Hex",
}

# Skip these - they're not real champion pages on MetaTFT
SKIP_UNITS = {
    "TFT16_AzirSoldier",  # Sand Soldier summon
    "TFT16_FreljordProp",  # Frozen Tower structure
    "TFT16_MalzaharVoidling",  # Voidling summon
    "TFT16_PiltoverInvention",  # Piltover special
    "TFT16_Atakhan",  # Darkin encounter
}


def get_champion_list():
    """Load champion list from combat_data.json."""
    with open(COMBAT_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    champions = {}
    for api_name, champ in data.get("champions", {}).items():
        if not api_name.startswith("TFT16_"):
            continue
        if api_name in SKIP_UNITS:
            continue

        name = champ.get("name", api_name.replace("TFT16_", ""))
        cost = champ.get("cost", 0)
        if cost == 11:
            # Tibbers is the only cost-11 unit with a real page
            if api_name != "TFT16_AnnieTibbers":
                continue

        champions[api_name] = {
            "name": name,
            "cost": cost,
            "url_slug": SPECIAL_URL_SLUGS.get(api_name, name),
        }

    return champions


def get_metatft_url(slug):
    """Build MetaTFT unit URL from slug."""
    # MetaTFT uses URL-encoded names
    return f"{METATFT_UNITS_URL}/{slug}"


def scrape_champion(page, api_name, info, retries=2):
    """Scrape a single champion's ability and stats from MetaTFT."""
    url = get_metatft_url(info["url_slug"])
    result = {
        "api_name": api_name,
        "display_name": info["name"],
        "cost": info["cost"],
        "url": url,
        "ability_description": None,
        "stats": None,
        "scraped": False,
        "error": None,
    }

    for attempt in range(retries + 1):
        try:
            # Navigate to champion page
            page.goto(url, wait_until="networkidle", timeout=15000)

            # Wait for the page content to load
            page.wait_for_timeout(1500)

            # --- Extract ability description ---
            ability_desc = None
            try:
                # Try the exact class first
                ability_el = page.query_selector(".UnitAbilityDescription")
                if ability_el:
                    ability_desc = ability_el.inner_text().strip()
            except Exception:
                pass

            if not ability_desc:
                try:
                    # Fallback: look for ability section by content structure
                    ability_el = page.query_selector(
                        '[class*="UnitAbility"] [class*="Description"]'
                    )
                    if ability_el:
                        ability_desc = ability_el.inner_text().strip()
                except Exception:
                    pass

            result["ability_description"] = ability_desc

            # --- Click Stats tab and extract stats ---
            stats_data = {}
            try:
                # Find and click the Stats tab
                # The user identified this class for the tab buttons
                tabs = page.query_selector_all(
                    ".MuiButtonBase-root.MuiTab-root.MuiTab-textColorPrimary"
                )

                stats_tab = None
                for tab in tabs:
                    tab_text = tab.inner_text().strip().lower()
                    if "stat" in tab_text:
                        stats_tab = tab
                        break

                if stats_tab:
                    stats_tab.click()
                    page.wait_for_timeout(800)

                    # Extract stats from UnitStatsMenu
                    stats_menu = page.query_selector(".UnitStatsMenu")
                    if stats_menu:
                        stats_data["raw_text"] = stats_menu.inner_text().strip()

                        # Try to parse individual stat rows
                        stat_rows = stats_menu.query_selector_all(
                            '[class*="StatRow"], [class*="stat-row"], tr, [class*="Stat"]'
                        )
                        parsed_stats = {}
                        for row in stat_rows:
                            row_text = row.inner_text().strip()
                            if row_text:
                                # Try to extract label: value pairs
                                parts = re.split(r"[\t\n]+", row_text)
                                if len(parts) >= 2:
                                    parsed_stats[parts[0].strip()] = parts[1].strip()
                                elif ":" in row_text:
                                    k, v = row_text.split(":", 1)
                                    parsed_stats[k.strip()] = v.strip()

                        # Remove Ability Power (always 100 for all champs, not useful)
                        parsed_stats.pop("Ability Power", None)

                        if parsed_stats:
                            stats_data["parsed"] = parsed_stats
                    else:
                        # Fallback: try to find any stats container
                        stats_container = page.query_selector(
                            '[class*="StatsMenu"], [class*="stats-menu"], [class*="UnitStats"]'
                        )
                        if stats_container:
                            stats_data["raw_text"] = (
                                stats_container.inner_text().strip()
                            )

                    # Switch back to ability tab
                    if tabs:
                        tabs[0].click()
                        page.wait_for_timeout(300)

            except Exception as e:
                stats_data["error"] = str(e)

            result["stats"] = stats_data
            result["scraped"] = True
            return result

        except PWTimeoutError:
            if attempt < retries:
                print(f"    Timeout, retrying ({attempt + 1}/{retries})...")
                page.wait_for_timeout(2000)
                continue
            result["error"] = "Timeout after retries"
        except Exception as e:
            if attempt < retries:
                print(f"    Error: {e}, retrying ({attempt + 1}/{retries})...")
                page.wait_for_timeout(2000)
                continue
            result["error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Scrape MetaTFT unit pages for ability descriptions and stats"
    )
    parser.add_argument(
        "--champion",
        type=str,
        help="Scrape a single champion by display name (e.g., Aatrox)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List URLs without scraping"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output JSON file (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    parser.add_argument(
        "--visible", action="store_true", help="Run browser in visible mode"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)",
    )

    args = parser.parse_args()
    headless = not args.visible

    print("=" * 60)
    print("MetaTFT Unit Data Scraper")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    # Load champion list
    champions = get_champion_list()
    print(f"Champions to scrape: {len(champions)}")

    # Filter for single champion if requested
    if args.champion:
        target = args.champion.lower().replace(" ", "").replace("'", "")
        filtered = {}
        for api_name, info in champions.items():
            name_norm = info["name"].lower().replace(" ", "").replace("'", "")
            if target in name_norm or target in api_name.lower():
                filtered[api_name] = info
        if not filtered:
            print(f"Champion '{args.champion}' not found!")
            print("Available:", ", ".join(c["name"] for c in champions.values()))
            return 1
        champions = filtered
        print(f"Filtered to: {', '.join(c['name'] for c in champions.values())}")

    if args.dry_run:
        print("\n[DRY RUN] Would scrape these URLs:")
        for api_name, info in sorted(champions.items()):
            url = get_metatft_url(info["url_slug"])
            print(f"  {info['name']:25} -> {url}")
        return 0

    # Scrape
    results = {}
    total = len(champions)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        for i, (api_name, info) in enumerate(
            sorted(champions.items(), key=lambda x: (-x[1]["cost"], x[1]["name"]))
        ):
            print(
                f"\n[{i + 1}/{total}] {info['name']} ({info['cost']}-cost)...", end=" "
            )

            result = scrape_champion(page, api_name, info)
            results[api_name] = result

            if result["scraped"]:
                desc_len = (
                    len(result["ability_description"])
                    if result["ability_description"]
                    else 0
                )
                has_stats = bool(result["stats"] and result["stats"].get("raw_text"))
                print(
                    f"OK (desc: {desc_len} chars, stats: {'Y' if has_stats else 'N'})"
                )
            else:
                print(f"FAILED: {result['error']}")

            # Rate limit with random delay to be polite
            if i < total - 1:
                delay = random.uniform(1.0, 3.0)
                time.sleep(delay)

        browser.close()

    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_data = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": "metatft.com",
        "total_champions": total,
        "successful": sum(1 for r in results.values() if r["scraped"]),
        "failed": sum(1 for r in results.values() if not r["scraped"]),
        "champions": results,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    success = sum(1 for r in results.values() if r["scraped"])
    with_desc = sum(1 for r in results.values() if r.get("ability_description"))
    with_stats = sum(
        1 for r in results.values() if r.get("stats") and r["stats"].get("raw_text")
    )
    failed = sum(1 for r in results.values() if not r["scraped"])

    print(f"  Total:            {total}")
    print(f"  Scraped:          {success}")
    print(f"  With ability desc:{with_desc}")
    print(f"  With stats:       {with_stats}")
    print(f"  Failed:           {failed}")
    print(f"\n  Saved to: {args.output}")

    if failed > 0:
        print("\n  Failed champions:")
        for api_name, r in results.items():
            if not r["scraped"]:
                print(f"    - {r['display_name']}: {r['error']}")

    return 0


if __name__ == "__main__":
    exit(main())
