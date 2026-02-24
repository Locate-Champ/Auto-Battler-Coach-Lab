#!/usr/bin/env python3
from __future__ import annotations

import subprocess

FORBIDDEN_SUBSTRINGS = (
    "trait_icons_",
    "/icons/",
    "\\icons\\",
)

ALLOWLIST_PREFIXES = (
    "archive/",
    ".agent/archive/",
)


def main() -> int:
    proc = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    violations: list[str] = []
    for path in tracked:
        normalized = path.replace("\\", "/")
        if normalized.startswith(ALLOWLIST_PREFIXES):
            continue
        if any(token in normalized for token in FORBIDDEN_SUBSTRINGS):
            violations.append(normalized)

    if violations:
        print("Tracked asset-pack paths are not allowed:")
        for item in violations:
            print(f"  - {item}")
        return 1

    print("No tracked asset-pack paths found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
