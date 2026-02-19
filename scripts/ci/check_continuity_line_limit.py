#!/usr/bin/env python3
from __future__ import annotations
import sys
from pathlib import Path

MAX_LINES = 250
CONTINUITY_PATH = Path(".agent/CONTINUITY.md")

def main() -> int:
    if not CONTINUITY_PATH.exists():
        print(f"ERROR: missing {CONTINUITY_PATH}. This file is required.", file=sys.stderr)
        return 1

    text = CONTINUITY_PATH.read_text(encoding="utf-8")
    line_count = len(text.splitlines())

    if line_count > MAX_LINES:
        print(
            f"ERROR: {CONTINUITY_PATH} is {line_count} lines (limit: {MAX_LINES}).",
            file=sys.stderr,
        )
        print(
            "Action required: archive snapshot to .agent/archive/CONTINUITY_<YYYY-MM-DD>.md "
            "and compact .agent/CONTINUITY.md per continuity policy.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {CONTINUITY_PATH} is {line_count} lines (<= {MAX_LINES}).")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
