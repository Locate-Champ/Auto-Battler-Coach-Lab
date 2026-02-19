#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FORBIDDEN_PATH_PREFIXES = (
    "archive/",
    ".agent/archive/",
    "docs/",
)

FORBIDDEN_TOKENS = (
    "forrestmiller34",
    "tft-coach-234",
    "tft-sim-results-forrest",
    "tft-sim-role",
    "tft-coach-gpu",
    "/data/tft",
    "tft-results/gates",
)


def tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    out = proc.stdout.decode("utf-8", errors="strict")
    return [item for item in out.split("\0") if item]


def is_binary(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            head = fh.read(4096)
    except OSError:
        return True
    return b"\x00" in head


def main() -> int:
    files = tracked_files()

    path_violations: list[str] = []
    token_violations: list[str] = []
    token_bytes = tuple(token.encode("utf-8") for token in FORBIDDEN_TOKENS)

    for rel in files:
        normalized = rel.replace("\\", "/")
        if normalized.startswith(FORBIDDEN_PATH_PREFIXES):
            path_violations.append(normalized)
            continue

        path = Path(rel)
        if not path.exists() or is_binary(path):
            continue

        try:
            blob = path.read_bytes().lower()
        except OSError:
            continue

        for token, token_b in zip(FORBIDDEN_TOKENS, token_bytes):
            if token_b in blob:
                token_violations.append(f"{normalized}: contains '{token}'")

    if path_violations or token_violations:
        print("Legacy/public identifier policy violation.")

        if path_violations:
            print("\nTracked local-only paths found:")
            for item in sorted(path_violations):
                print(f"  - {item}")

        if token_violations:
            print("\nForbidden identifier tokens found:")
            for item in sorted(token_violations):
                print(f"  - {item}")

        return 1

    print("No forbidden legacy identifiers found in tracked files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
