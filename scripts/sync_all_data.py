#!/usr/bin/env python3
"""
Unified data sync script for TFT Coach.

This script keeps both /data/ and /simulator/data/ in sync by running
all necessary fetch operations in sequence.

Usage:
    python scripts/sync_all_data.py           # Sync all data
    python scripts/sync_all_data.py --meta    # Only sync meta data (/data/meta/)
    python scripts/sync_all_data.py --game    # Only sync game data (champions, items, traits)
    python scripts/sync_all_data.py --sim     # Only sync simulator data (/simulator/data/)
    python scripts/sync_all_data.py --dry-run # Show what would be synced without syncing
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
SIMULATOR_DIR = PROJECT_ROOT / "simulator"
SIMULATOR_DATA_DIR = SIMULATOR_DIR / "data"


class SyncResult:
    """Track sync operation results."""

    def __init__(self):
        self.successes = []
        self.failures = []
        self.skipped = []

    def add_success(self, name: str, details: str = ""):
        self.successes.append({"name": name, "details": details})

    def add_failure(self, name: str, error: str):
        self.failures.append({"name": name, "error": error})

    def add_skip(self, name: str, reason: str):
        self.skipped.append({"name": name, "reason": reason})

    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "SYNC SUMMARY",
            "=" * 60,
            f"  Successful: {len(self.successes)}",
            f"  Failed:     {len(self.failures)}",
            f"  Skipped:    {len(self.skipped)}",
            "-" * 60,
        ]

        if self.successes:
            lines.append("Successful:")
            for s in self.successes:
                lines.append(f"  ✓ {s['name']}")
                if s['details']:
                    lines.append(f"    {s['details']}")

        if self.failures:
            lines.append("Failed:")
            for f in self.failures:
                lines.append(f"  ✗ {f['name']}: {f['error']}")

        if self.skipped:
            lines.append("Skipped:")
            for s in self.skipped:
                lines.append(f"  - {s['name']}: {s['reason']}")

        lines.append("=" * 60)
        return "\n".join(lines)


def run_script(script_path: Path, args: list = None, cwd: Path = None) -> tuple[bool, str]:
    """
    Run a Python script and return success status and output.

    Returns:
        (success: bool, output: str)
    """
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else str(script_path.parent),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR: {result.stderr}"

        return result.returncode == 0, output

    except subprocess.TimeoutExpired:
        return False, "Script timed out after 5 minutes"
    except Exception as e:
        return False, str(e)


def sync_meta_data(result: SyncResult, dry_run: bool = False):
    """
    Sync main meta data in /data/ folder.

    Runs: scripts/fetch_meta_data.py
    Updates: data/meta/comps.json, data/meta/last_updated.json
    """
    print("\n" + "=" * 60)
    print("SYNCING META DATA (/data/)")
    print("=" * 60)

    script = SCRIPT_DIR / "fetch_meta_data.py"

    if not script.exists():
        result.add_failure("fetch_meta_data.py", "Script not found")
        return

    if dry_run:
        result.add_skip("fetch_meta_data.py", "Dry run mode")
        print(f"  [DRY RUN] Would run: {script}")
        return

    print(f"Running {script.name}...")
    success, output = run_script(script)

    if success:
        result.add_success("fetch_meta_data.py", "Updated data/meta/")
        print(output)
    else:
        result.add_failure("fetch_meta_data.py", output[:200])
        print(f"  ERROR: {output}")


def sync_simulator_items(result: SyncResult, dry_run: bool = False):
    """
    Sync simulator item data.

    Runs: simulator/fetch_metatft_items.py --save-all
    Updates: simulator/data/metatft_items.json
    """
    print("\n" + "-" * 60)
    print("Syncing simulator items...")
    print("-" * 60)

    script = SIMULATOR_DIR / "fetch_metatft_items.py"

    if not script.exists():
        result.add_failure("fetch_metatft_items.py", "Script not found")
        return

    if dry_run:
        result.add_skip("fetch_metatft_items.py", "Dry run mode")
        print(f"  [DRY RUN] Would run: {script} --save-all")
        return

    print(f"Running {script.name} --save-all...")
    success, output = run_script(script, ["--save-all"], cwd=SIMULATOR_DIR)

    if success:
        result.add_success("fetch_metatft_items.py", "Updated simulator/data/metatft_items.json")
        # Print last few lines of output
        lines = output.strip().split('\n')
        for line in lines[-10:]:
            print(f"  {line}")
    else:
        result.add_failure("fetch_metatft_items.py", output[:200])
        print(f"  ERROR: {output}")


def sync_simulator_positions(result: SyncResult, dry_run: bool = False):
    """
    Sync simulator positioning data.

    Runs: simulator/fetch_metatft_positions.py --save-all
    Updates: simulator/data/metatft_positions.json
    """
    print("\n" + "-" * 60)
    print("Syncing simulator positions...")
    print("-" * 60)

    script = SIMULATOR_DIR / "fetch_metatft_positions.py"

    if not script.exists():
        result.add_failure("fetch_metatft_positions.py", "Script not found")
        return

    if dry_run:
        result.add_skip("fetch_metatft_positions.py", "Dry run mode")
        print(f"  [DRY RUN] Would run: {script} --save-all")
        return

    print(f"Running {script.name} --save-all...")
    success, output = run_script(script, ["--save-all"], cwd=SIMULATOR_DIR)

    if success:
        result.add_success("fetch_metatft_positions.py", "Updated simulator/data/metatft_positions.json")
        # Print last few lines of output
        lines = output.strip().split('\n')
        for line in lines[-10:]:
            print(f"  {line}")
    else:
        result.add_failure("fetch_metatft_positions.py", output[:200])
        print(f"  ERROR: {output}")


def sync_simulator_data(result: SyncResult, dry_run: bool = False):
    """
    Sync all simulator data in /simulator/data/ folder.
    """
    print("\n" + "=" * 60)
    print("SYNCING SIMULATOR DATA (/simulator/data/)")
    print("=" * 60)

    sync_simulator_items(result, dry_run)
    sync_simulator_positions(result, dry_run)


def sync_game_data(result: SyncResult, dry_run: bool = False):
    """
    Sync game reference data (champions, items, traits, augments).

    Runs: scripts/fetch_game_data.py (placement stats)
    Runs: scripts/fetch_champion_stats.py (full stats + abilities)
    Updates: data/game_data/*.jsonl, simulator/data/
    """
    print("\n" + "=" * 60)
    print("SYNCING GAME DATA (champions, items, traits)")
    print("=" * 60)

    # 1. Fetch placement stats (win rates, top 4 rates)
    script = SCRIPT_DIR / "fetch_game_data.py"

    if not script.exists():
        result.add_failure("fetch_game_data.py", "Script not found")
    elif dry_run:
        result.add_skip("fetch_game_data.py", "Dry run mode")
        print(f"  [DRY RUN] Would run: {script}")
    else:
        print(f"Running {script.name}...")
        success, output = run_script(script)

        if success:
            result.add_success("fetch_game_data.py", "Updated data/game_data/ (placement stats)")
            print(output)
        else:
            result.add_failure("fetch_game_data.py", output[:200])
            print(f"  ERROR: {output}")

    # 2. Fetch full champion stats and abilities from CommunityDragon
    print("\n" + "-" * 60)
    print("Syncing champion stats and abilities (CommunityDragon)...")
    print("-" * 60)

    stats_script = SCRIPT_DIR / "fetch_champion_stats.py"

    if not stats_script.exists():
        result.add_failure("fetch_champion_stats.py", "Script not found")
        return

    if dry_run:
        result.add_skip("fetch_champion_stats.py", "Dry run mode")
        print(f"  [DRY RUN] Would run: {stats_script}")
        return

    print(f"Running {stats_script.name}...")
    success, output = run_script(stats_script)

    if success:
        result.add_success("fetch_champion_stats.py", "Updated simulator/data/ (stats + abilities)")
        # Print last few lines of output
        lines = output.strip().split('\n')
        for line in lines[-15:]:
            print(f"  {line}")
    else:
        result.add_failure("fetch_champion_stats.py", output[:200])
        print(f"  ERROR: {output}")


def update_sync_manifest(result: SyncResult):
    """
    Update a manifest file tracking when data was last synced.
    """
    manifest_path = DATA_DIR / "sync_manifest.json"

    manifest = {
        "last_sync": datetime.now(timezone.utc).isoformat(),
        "script": "scripts/sync_all_data.py",
        "results": {
            "successes": [s["name"] for s in result.successes],
            "failures": [f["name"] for f in result.failures],
            "skipped": [s["name"] for s in result.skipped],
        },
        "data_sources": {
            "meta": {
                "folder": "data/meta/",
                "source": "MetaTFT API",
                "files": ["comps.json", "last_updated.json"]
            },
            "game_data_placements": {
                "folder": "data/game_data/",
                "source": "MetaTFT API",
                "files": ["champions.jsonl", "items.jsonl", "traits.jsonl", "augments.jsonl"],
                "note": "Placement statistics (win rates, top 4 rates)"
            },
            "champion_stats": {
                "folder": "simulator/data/",
                "source": "CommunityDragon",
                "files": ["combat_data.json", "timing_constants.json", "traits.json"],
                "note": "Full champion stats (HP, AD, abilities, spell variables)"
            },
            "simulator_items": {
                "folder": "simulator/data/",
                "source": "MetaTFT API",
                "file": "metatft_items.json"
            },
            "simulator_positions": {
                "folder": "simulator/data/",
                "source": "MetaTFT API",
                "file": "metatft_positions.json"
            }
        }
    }

    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nUpdated sync manifest: {manifest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync all TFT data from external APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/sync_all_data.py           # Sync everything
    python scripts/sync_all_data.py --meta    # Only sync meta comps (/data/meta/)
    python scripts/sync_all_data.py --game    # Only sync game data (champions, items, traits)
    python scripts/sync_all_data.py --sim     # Only sync /simulator/data/
    python scripts/sync_all_data.py --dry-run # Preview what would be synced
        """
    )
    parser.add_argument(
        "--meta",
        action="store_true",
        help="Only sync meta data (comps, builds)"
    )
    parser.add_argument(
        "--game",
        action="store_true",
        help="Only sync game data (champions, items, traits, augments)"
    )
    parser.add_argument(
        "--sim", "--simulator",
        action="store_true",
        dest="sim",
        help="Only sync simulator data (/simulator/data/ folder)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without actually syncing"
    )

    args = parser.parse_args()

    # Default to syncing everything if no specific flag
    has_specific = args.meta or args.game or args.sim
    sync_meta = args.meta or not has_specific
    sync_game = args.game or not has_specific
    sync_sim = args.sim or not has_specific

    # Build sync description
    syncing = []
    if sync_meta:
        syncing.append("meta")
    if sync_game:
        syncing.append("game")
    if sync_sim:
        syncing.append("simulator")

    print("=" * 60)
    print("TFT DATA SYNC")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Syncing: {', '.join(syncing)}")

    result = SyncResult()

    # Run sync operations
    if sync_meta:
        sync_meta_data(result, args.dry_run)

    if sync_game:
        sync_game_data(result, args.dry_run)

    if sync_sim:
        sync_simulator_data(result, args.dry_run)

    # Update manifest (skip on dry run)
    if not args.dry_run and (result.successes or result.failures):
        update_sync_manifest(result)

    # Print summary
    print(result.summary())

    # Exit with error code if any failures
    if result.failures:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
