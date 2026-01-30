#!/usr/bin/env python3
"""
Watch MetaTFT logs for changes and optionally sync to git.
Run this on your Windows machine while playing.

Usage:
    python watch_logs.py              # Just watch and print changes
    python watch_logs.py --sync       # Watch and auto-sync to git
    python watch_logs.py --uuid       # Watch specifically for UUID patterns
"""

import os
import sys
import time
import subprocess
import re
from pathlib import Path
from datetime import datetime

# Configure these paths for your system
METATFT_LOGS = Path(os.environ.get('LOCALAPPDATA', '')) / 'Overwolf' / 'Log' / 'Apps' / 'MetaTFT'
REPO_PATH = Path(__file__).parent  # Assumes script is in repo root

# Key log files to watch
WATCH_FILES = [
    'background.html.log',
    'main.html.log',
    'ingamedesktop.html.log',
]

# Patterns to look for
UUID_PATTERN = re.compile(r'"uuid":\s*"([a-f0-9-]{36})"', re.IGNORECASE)
SIGNED_IN_PATTERN = re.compile(r'"status":\s*"(success|error)".*"Reason":\s*"([^"]*)"', re.IGNORECASE)
MATCH_PATTERN = re.compile(r'match_uuid|game_uuid|presigned', re.IGNORECASE)


def get_file_info(filepath):
    """Get file modification time and size."""
    try:
        stat = filepath.stat()
        return stat.st_mtime, stat.st_size
    except:
        return None, None


def tail_file(filepath, lines=50):
    """Get last N lines of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.readlines()[-lines:]
    except:
        return []


def check_for_uuid(lines):
    """Check for UUID patterns in log lines."""
    for line in lines:
        uuid_match = UUID_PATTERN.search(line)
        if uuid_match:
            return uuid_match.group(1)

        signed_match = SIGNED_IN_PATTERN.search(line)
        if signed_match:
            status, reason = signed_match.groups()
            if status == 'success':
                print(f"  ✓ Signed in successfully!")
            elif 'Not signed in' in reason:
                print(f"  ✗ Not signed in: {reason}")
    return None


def sync_to_git(folder_name):
    """Quick sync logs to git."""
    dest = REPO_PATH / folder_name
    dest.mkdir(exist_ok=True)

    for filename in WATCH_FILES:
        src = METATFT_LOGS / filename
        if src.exists():
            import shutil
            shutil.copy2(src, dest / filename)

    # Git operations
    subprocess.run(['git', 'add', str(dest)], cwd=REPO_PATH)
    subprocess.run(['git', 'commit', '-m', f'Live logs: {folder_name}'], cwd=REPO_PATH)
    subprocess.run(['git', 'push'], cwd=REPO_PATH)
    print(f"  → Synced to git: {folder_name}")


def watch_logs(sync=False, uuid_watch=False):
    """Main watch loop."""
    print(f"Watching MetaTFT logs at: {METATFT_LOGS}")
    print(f"Press Ctrl+C to stop\n")

    # Track file states
    file_states = {}

    while True:
        for filename in WATCH_FILES:
            filepath = METATFT_LOGS / filename
            mtime, size = get_file_info(filepath)

            if mtime is None:
                continue

            prev_mtime, prev_size = file_states.get(filename, (None, None))

            if prev_mtime is not None and mtime > prev_mtime:
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] {filename} updated (+{size - prev_size} bytes)")

                # Check new content
                lines = tail_file(filepath, 100)

                if uuid_watch:
                    uuid = check_for_uuid(lines)
                    if uuid:
                        print(f"  🎮 UUID FOUND: {uuid}")
                        print(f"  URL: https://metatft-matches-2.ams3.digitaloceanspaces.com/{uuid}.json")

                if sync:
                    folder = f"live-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    sync_to_git(folder)

            file_states[filename] = (mtime, size)

        time.sleep(2)  # Check every 2 seconds


if __name__ == '__main__':
    sync = '--sync' in sys.argv
    uuid_watch = '--uuid' in sys.argv or True  # Always watch for UUID

    try:
        watch_logs(sync=sync, uuid_watch=uuid_watch)
    except KeyboardInterrupt:
        print("\nStopped watching.")
