#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
PLANS_DIR = REPO_ROOT / ".agent" / "plans"
PLANS_README = PLANS_DIR / "README.md"

EXPECTED = "./.agent/plans"


def run_git_check_ignore(path: Path) -> bool:
    # Returns True if ignored, False if not ignored
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            cwd=REPO_ROOT,
            check=False,
        )
        return proc.returncode == 0
    except Exception:
        # If git isn't available, skip ignore check (CI will have git).
        return False


def main() -> int:
    if not SETTINGS.exists():
        print("ERROR: .claude/settings.json missing")
        return 1

    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    got = data.get("plansDirectory")
    if got != EXPECTED:
        print("ERROR: plansDirectory drift detected in .claude/settings.json")
        print(f"  expected: {EXPECTED}")
        print(f"  got:      {got!r}")
        return 1

    if not PLANS_DIR.exists() or not PLANS_DIR.is_dir():
        print("ERROR: .agent/plans directory missing")
        return 1

    if not PLANS_README.exists():
        print("ERROR: .agent/plans/README.md missing (directory must be trackable)")
        return 1

    if run_git_check_ignore(PLANS_README):
        print(
            "ERROR: .agent/plans/README.md is ignored by gitignore (allowlist broken)"
        )
        return 1

    print("OK: agent plans directory policy is enforced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
