#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

CODE_EXTS = {".py", ".pyi", ".json", ".yml", ".yaml", ".toml"}


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def is_code_file(path: str) -> bool:
    p = Path(path)
    return p.suffix.lower() in CODE_EXTS


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event_name = os.environ.get("GITHUB_EVENT_NAME")

    if not event_path or not Path(event_path).exists():
        # If not running in GitHub Actions PR context, do nothing.
        return 0

    if event_name != "pull_request":
        return 0

    payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pr = payload.get("pull_request", {})
    labels = {lbl["name"] for lbl in pr.get("labels", []) if "name" in lbl}
    body = pr.get("body") or ""

    base_sha = pr.get("base", {}).get("sha")
    head_sha = pr.get("head", {}).get("sha")
    if not base_sha or not head_sha:
        print("dual-track guard: missing base/head sha in PR payload")
        return 1

    # Ensure base commit is available (requires fetch-depth: 0 in checkout)
    changed = run(["git", "diff", "--name-only", f"{base_sha}...{head_sha}"]).splitlines()

    src_changes = [p for p in changed if p.startswith("src/models/") and is_code_file(p)]
    models_changes = [p for p in changed if p.startswith("models/") and is_code_file(p)]

    dual_track = bool(src_changes) and bool(models_changes)
    if not dual_track:
        return 0

    # Dual track detected
    required_label = "allow-dual-track"
    if required_label not in labels:
        print("Dual-track change detected (code changes in BOTH src/models and models).")
        print(f"Add PR label '{required_label}' to proceed.")
        print("Changed files (src/models):")
        for p in src_changes:
            print(f"  - {p}")
        print("Changed files (models):")
        for p in models_changes:
            print(f"  - {p}")
        return 1

    # Label present, enforce PR body sections
    if "Dual-Track Reason:" not in body or "Exit Plan:" not in body:
        print(f"PR label '{required_label}' is present, but PR body is missing required sections.")
        print("Include both of the following in the PR description:")
        print("  Dual-Track Reason:")
        print("  Exit Plan:")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
