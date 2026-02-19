#!/usr/bin/env python3
"""
Extract TFT champion data from local Riot Games installation.

Uses cdtb (CommunityDragon Toolbox) to:
1. Read map22.bin from Map22.wad.client (TFT game configuration)
2. Read character record BINs from individual champion WADs
3. Read tft.stringtable from localized WAD for English text
4. Run TftTransformer to produce structured JSON (same format as CommunityDragon)

Saves output to data/local_game_data.json

Usage:
    pip install cdtb
    python scripts/extract_local_tft_data.py
    python scripts/extract_local_tft_data.py --game-dir "D:\\Riot Games\\League of Legends"
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

try:
    from cdtb.wad import Wad
    from cdtb.binfile import BinFile
    from cdtb.tftdata import TftTransformer
except ImportError:
    print("cdtb not installed. Run: pip install cdtb")
    sys.exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "local_game_data.json"

# Default game directory
DEFAULT_GAME_DIR = Path(r"C:\Riot Games\League of Legends")

# WAD locations relative to game dir
FINAL_DIR = Path("Game") / "DATA" / "FINAL"
MAP22_WAD = FINAL_DIR / "Maps" / "Shipping" / "Map22.wad.client"
LOCALIZED_WAD = FINAL_DIR / "Localized" / "Global.en_US.wad.client"
CHAMPIONS_DIR = FINAL_DIR / "Champions"
TFTSET16_WAD = FINAL_DIR / "TFTSet16.wad.client"


def extract_file_from_wad(wad_path, target_path, output_path):
    """Extract a single file from a WAD archive (read-only on source)."""
    wad = Wad(str(wad_path))
    for entry in wad.files:
        path = entry.path if hasattr(entry, "path") else None
        if path == target_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(str(wad_path), "rb") as f:
                data = entry.read_data(f)
            with open(output_path, "wb") as f:
                f.write(data)
            return len(data)
    return None


def extract_character_bins(game_dir, extract_dir, champ_names):
    """Extract character record BIN files from individual champion WADs."""
    champions_dir = game_dir / CHAMPIONS_DIR
    extracted = 0
    skipped = 0

    for champ_name in champ_names:
        # TFT16_Aatrox -> aatrox (base LoL champion name)
        base_name = champ_name.replace("TFT16_", "").lower()

        # Some TFT names map to different WAD names
        wad_name_map = {
            "annietibbers": "annie",
            "azirsoldier": "azir",
            "azirultsoldier": "azir",
            "gangplankbarrel": "gangplank",
            "malzaharvoidling": "malzahar",
            "shyvanadragon": "shyvana",
            "piltoverinvention": None,  # No WAD
            "freljordprop": None,
            "explorerprop": None,
            "bilgewaterprismatic": None,
            "demacianstandard": None,
            "shippingrouteminion": None,
            "ixtalprop": None,
        }

        # Skip PVE and special entries
        if base_name.startswith("pve_") or base_name.startswith("xerathzap_"):
            skipped += 1
            continue

        wad_base = wad_name_map.get(base_name, base_name)
        if wad_base is None:
            skipped += 1
            continue

        # Find the WAD file (case-insensitive)
        wad_file = None
        for f in champions_dir.iterdir():
            if f.name.lower() == f"{wad_base}.wad.client":
                wad_file = f
                break

        if not wad_file or not wad_file.exists():
            print(
                f"  Warning: WAD not found for {champ_name} (looked for {wad_base}.wad.client)"
            )
            skipped += 1
            continue

        # The character record is at data/characters/<name>/<name>.bin
        # Use the lowercased TFT name for the target path
        tft_lower = champ_name.lower()
        target = f"data/characters/{tft_lower}/{tft_lower}.bin"

        # First try TFT-specific name, then fall back to base name
        out_path = os.path.join(
            extract_dir, "data", "characters", tft_lower, f"{tft_lower}.bin"
        )

        # Try extracting with TFT name from the TFTSet16 WAD first
        tft_wad = game_dir / TFTSET16_WAD
        size = extract_file_from_wad(tft_wad, target, out_path)

        if size is None:
            # Try from the base champion's WAD with base name
            base_target = f"data/characters/{wad_base}/{wad_base}.bin"
            base_out = os.path.join(
                extract_dir, "data", "characters", tft_lower, f"{tft_lower}.bin"
            )
            size = extract_file_from_wad(wad_file, base_target, base_out)

        if size:
            extracted += 1
        else:
            skipped += 1

    return extracted, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Extract TFT data from local Riot Games installation"
    )
    parser.add_argument(
        "--game-dir",
        type=Path,
        default=DEFAULT_GAME_DIR,
        help=f"Path to League of Legends install (default: {DEFAULT_GAME_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output JSON path (default: {OUTPUT_PATH})",
    )
    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="Temp directory for extraction (default: auto)",
    )
    parser.add_argument(
        "--keep-temp", action="store_true", help="Don't delete temp files after"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("TFT Local Game Data Extractor")
    print("=" * 60)

    # Validate game directory
    game_dir = args.game_dir
    map22_wad = game_dir / MAP22_WAD
    if not map22_wad.exists():
        print(f"ERROR: Map22.wad.client not found at {map22_wad}")
        print(f"Is League of Legends installed at {game_dir}?")
        return 1

    print(f"Game directory: {game_dir}")

    # Set up temp directory
    if args.temp_dir:
        extract_dir = str(args.temp_dir)
        os.makedirs(extract_dir, exist_ok=True)
    else:
        extract_dir = tempfile.mkdtemp(prefix="tft_extract_")

    print(f"Temp directory: {extract_dir}")

    try:
        # Step 1: Extract map22.bin
        print("\n--- Step 1: Extracting map22.bin ---")
        map22_target = "data/maps/shipping/map22/map22.bin"
        map22_out = os.path.join(extract_dir, map22_target.replace("/", os.sep))
        size = extract_file_from_wad(map22_wad, map22_target, map22_out)
        if size:
            print(f"  Extracted map22.bin ({size:,} bytes)")
        else:
            print("  ERROR: map22.bin not found in Map22.wad.client")
            return 1

        # Step 2: Extract TFT stringtable for English text
        print("\n--- Step 2: Extracting tft.stringtable ---")
        loc_wad = game_dir / LOCALIZED_WAD
        if loc_wad.exists():
            st_target = "data/menu/en_us/tft.stringtable"
            st_out = os.path.join(extract_dir, "en_us", st_target.replace("/", os.sep))
            size = extract_file_from_wad(loc_wad, st_target, st_out)
            if size:
                print(f"  Extracted tft.stringtable ({size:,} bytes)")
            else:
                print("  Warning: tft.stringtable not found, names will be hash keys")
        else:
            print(f"  Warning: {loc_wad} not found, names will be hash keys")

        # Step 3: Get TFT16 champion names from map22
        print("\n--- Step 3: Finding TFT16 champions ---")
        map22_bin = BinFile(map22_out)
        shop_entries = [x for x in map22_bin.entries if x.type == "TftShopData"]
        tft16_names = []
        for entry in shop_entries:
            name = entry.getv("mName")
            if name and name.startswith("TFT16_"):
                tft16_names.append(name)
        print(f"  Found {len(tft16_names)} TFT16 entries in map22.bin")

        # Step 4: Extract character record BINs from champion WADs
        print("\n--- Step 4: Extracting character records ---")
        extracted, skipped = extract_character_bins(game_dir, extract_dir, tft16_names)
        print(f"  Extracted: {extracted}, Skipped: {skipped}")

        # Step 5: Run TftTransformer
        print("\n--- Step 5: Running TftTransformer ---")
        output_dir = os.path.join(extract_dir, "output")
        transformer = TftTransformer(extract_dir, game_version=1603)
        transformer.export(output_dir, langs=["en_us"])

        result_path = os.path.join(output_dir, "en_us.json")
        if not os.path.exists(result_path):
            print("  ERROR: TftTransformer produced no output")
            return 1

        with open(result_path, "r", encoding="utf-8") as f:
            full_data = json.load(f)

        # Extract Set 16 data
        set16_data = None
        for sd in full_data.get("setData", []):
            if sd.get("mutator") == "TFTSet16":
                set16_data = sd
                break

        # Also check sets key
        set16_sets = full_data.get("sets", {}).get("16", {})

        champ_count = len(set16_data.get("champions", [])) if set16_data else 0
        champ_count_sets = len(set16_sets.get("champions", [])) if set16_sets else 0
        trait_count = len(set16_data.get("traits", [])) if set16_data else 0

        print(f"  Champions (setData): {champ_count}")
        print(f"  Champions (sets): {champ_count_sets}")
        print(f"  Traits: {trait_count}")

        # Save output
        args.output.parent.mkdir(parents=True, exist_ok=True)

        # Save the full CommunityDragon-format data
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        print(f"\n  Saved to: {args.output} ({os.path.getsize(args.output):,} bytes)")

        # Summary
        print("\n" + "=" * 60)
        print("EXTRACTION COMPLETE")
        print("=" * 60)

        # Show sample champion if available
        champions = (set16_data or set16_sets or {}).get("champions", [])
        if champions:
            # Find Aatrox as sample
            for c in champions:
                if "Aatrox" in c.get("apiName", ""):
                    print(f"\nSample - {c.get('name', c.get('apiName'))}:")
                    print(f"  Cost: {c.get('cost')}")
                    stats = c.get("stats", {})
                    print(
                        f"  HP: {stats.get('hp')}, AD: {stats.get('damage')}, AS: {stats.get('attackSpeed')}"
                    )
                    print(
                        f"  Armor: {stats.get('armor')}, MR: {stats.get('magicResist')}, Range: {stats.get('range')}"
                    )
                    ability = c.get("ability", {})
                    print(f"  Ability: {ability.get('name')}")
                    break

        return 0

    finally:
        if not args.keep_temp and not args.temp_dir:
            import shutil

            try:
                shutil.rmtree(extract_dir)
                print("\nCleaned up temp directory")
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
