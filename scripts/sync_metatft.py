"""
MetaTFT Auto-Sync
Automatically finds and parses MetaTFT logs from your Overwolf installation.
Run this after each gaming session to update your augment data.

Usage:
    python sync_metatft.py              # Auto-discover and sync
    python sync_metatft.py --watch      # Watch for new logs continuously
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.metatft_parser import MetaTFTLogParser  # noqa: E402


def find_overwolf_logs() -> Path:
    """Auto-discover Overwolf log directory"""

    # Standard Windows locations
    possible_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Overwolf" / "Log",
        Path(os.environ.get("APPDATA", "")) / "Overwolf" / "Log",
        Path.home() / "AppData" / "Local" / "Overwolf" / "Log",
        Path.home() / "AppData" / "Roaming" / "Overwolf" / "Log",
    ]

    # Check each location
    for path in possible_paths:
        metatft_path = path / "Apps" / "MetaTFT"
        if metatft_path.exists():
            print(f"Found MetaTFT logs at: {metatft_path}")
            return metatft_path

    # Try to find any Overwolf installation
    for path in possible_paths:
        if path.exists():
            print(f"Found Overwolf logs at: {path}")
            # Look for MetaTFT subdirectory
            for subdir in path.glob("Apps/*"):
                if "metatft" in subdir.name.lower():
                    print(f"Found MetaTFT logs at: {subdir}")
                    return subdir

    return None


def sync_augments(log_dir: Path = None, output_dir: Path = None):
    """Sync augment data from MetaTFT logs"""

    # Auto-discover if not provided
    if log_dir is None:
        log_dir = find_overwolf_logs()

    if log_dir is None or not log_dir.exists():
        print("ERROR: Could not find MetaTFT logs!")
        print(
            "Make sure MetaTFT/Overwolf is installed and you've played at least one game."
        )
        print("\nExpected location: %LOCALAPPDATA%\\Overwolf\\Log\\Apps\\MetaTFT")
        return False

    # Default output directory
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "local" / "personal"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "metatft_augments.csv"

    print(f"\nParsing logs from: {log_dir}")
    print(f"Output file: {output_file}")
    print("-" * 50)

    # Parse logs
    parser = MetaTFTLogParser()

    try:
        events = parser.parse_all_augment_logs(str(log_dir))

        if not events:
            print("No augment events found in logs.")
            return False

        print(f"Found {len(events)} augment armory events")

        # Get stats
        stats = parser.get_augment_stats()
        print(f"Unique augments seen: {stats['unique_augments_seen']}")

        # Show recent events
        print("\nRecent augment choices:")
        for event in events[-5:]:
            ts = event["timestamp"].split()[1][:8]  # Just time
            opts = ", ".join(event["options"][:3])
            selected = list(event.get("selected", {}).values())
            sel_str = f" -> {selected[0]}" if selected else ""
            print(f"  [{ts}] {opts[:50]}{sel_str}")

        # Export
        parser.export_to_csv(str(output_file))

        # Show top augments
        print("\nYour most-picked augments:")
        sorted_augs = sorted(
            stats["augments"].items(),
            key=lambda x: x[1]["times_selected"],
            reverse=True,
        )
        for aug, data in sorted_augs[:10]:
            if data["times_selected"] > 0:
                print(
                    f"  {aug}: {data['times_selected']}x picked "
                    f"({data['selection_rate'] * 100:.0f}% when offered)"
                )

        print(f"\nSynced {len(events)} events to {output_file}")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


def watch_mode(interval: int = 60):
    """Watch for new logs and sync periodically"""
    print(f"Watching for new MetaTFT logs (checking every {interval}s)")
    print("Press Ctrl+C to stop\n")

    last_sync = None

    try:
        while True:
            log_dir = find_overwolf_logs()

            if log_dir:
                # Check if logs have been modified
                latest_log = max(
                    log_dir.glob("augment_recommendations*.log"),
                    key=lambda p: p.stat().st_mtime,
                    default=None,
                )

                if latest_log:
                    mod_time = datetime.fromtimestamp(latest_log.stat().st_mtime)

                    if last_sync is None or mod_time > last_sync:
                        print(
                            f"\n[{datetime.now().strftime('%H:%M:%S')}] New data detected, syncing..."
                        )
                        sync_augments(log_dir)
                        last_sync = datetime.now()
                    else:
                        print(
                            f"[{datetime.now().strftime('%H:%M:%S')}] No new data",
                            end="\r",
                        )

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped watching.")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sync MetaTFT augment data")
    parser.add_argument(
        "--watch", action="store_true", help="Watch for new logs continuously"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds (for watch mode)",
    )
    parser.add_argument(
        "--log-dir", type=str, help="Manual path to MetaTFT log directory"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("MetaTFT Auto-Sync")
    print("=" * 50)

    log_dir = Path(args.log_dir) if args.log_dir else None

    if args.watch:
        watch_mode(args.interval)
    else:
        success = sync_augments(log_dir)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
