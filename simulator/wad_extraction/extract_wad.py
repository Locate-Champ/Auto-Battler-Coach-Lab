"""
WAD Extraction Script for TFT Set 16

Uses CDTB (CommunityDragon Toolbox) to extract WAD files and convert BIN to JSON.
"""

import os
import sys
from pathlib import Path

# Add cdtb to path if needed
try:
    from cdtb.wad import Wad
    from cdtb.binfile import BinFile
except ImportError:
    print("CDTB not found. Install with: pip install cdtb")
    sys.exit(1)

# Paths
SCRIPT_DIR = Path(__file__).parent
RAW_DIR = SCRIPT_DIR / "raw"
EXTRACTED_DIR = SCRIPT_DIR / "extracted"
JSON_DIR = SCRIPT_DIR / "json"

def extract_wad(wad_path: Path, output_dir: Path):
    """Extract all files from a WAD archive."""
    print(f"Extracting: {wad_path.name}")

    # Convert to string for CDTB compatibility (Windows Path bug workaround)
    wad = Wad(str(wad_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use CDTB's extract method
    wad.extract(str(output_dir))

    # Count extracted files
    extracted_count = sum(1 for _ in output_dir.rglob("*") if _.is_file())
    print(f"  Total: {extracted_count} files extracted to {output_dir}")
    return extracted_count


def convert_bin_to_json(bin_path: Path, json_path: Path):
    """Convert a BIN file to JSON format."""
    try:
        binfile = BinFile(str(bin_path))
        json_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and save as JSON
        import json
        data = binfile.to_serializable()

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"  Error converting {bin_path.name}: {e}")
        return False


def find_and_convert_bins(extracted_dir: Path, json_dir: Path):
    """Find all .bin files and convert them to JSON."""
    print(f"\nConverting BIN files to JSON...")

    bin_files = list(extracted_dir.rglob("*.bin"))
    print(f"Found {len(bin_files)} BIN files")

    converted = 0
    failed = 0

    for bin_path in bin_files:
        # Preserve directory structure
        rel_path = bin_path.relative_to(extracted_dir)
        json_path = json_dir / rel_path.with_suffix('.json')

        if convert_bin_to_json(bin_path, json_path):
            converted += 1
        else:
            failed += 1

        if (converted + failed) % 50 == 0:
            print(f"  Processed {converted + failed}/{len(bin_files)} files...")

    print(f"  Converted: {converted}, Failed: {failed}")
    return converted, failed


def main():
    print("=" * 60)
    print("TFT Set 16 WAD Extraction Pipeline")
    print("=" * 60)

    # Check for WAD files
    wad_files = list(RAW_DIR.glob("*.wad.client"))
    if not wad_files:
        print(f"No WAD files found in {RAW_DIR}")
        return

    print(f"\nFound {len(wad_files)} WAD files:")
    for wad in wad_files:
        print(f"  - {wad.name} ({wad.stat().st_size / 1024 / 1024:.1f} MB)")

    # Extract each WAD
    for wad_path in wad_files:
        wad_name = wad_path.stem.replace('.wad', '')
        output_dir = EXTRACTED_DIR / wad_name

        if output_dir.exists():
            print(f"\nSkipping {wad_path.name} (already extracted)")
            continue

        extract_wad(wad_path, output_dir)

    # Convert BIN files to JSON
    find_and_convert_bins(EXTRACTED_DIR, JSON_DIR)

    print("\n" + "=" * 60)
    print("Extraction complete!")
    print(f"Extracted files: {EXTRACTED_DIR}")
    print(f"JSON files: {JSON_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
