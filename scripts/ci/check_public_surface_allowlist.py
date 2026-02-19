#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable

ROOT_ALLOWED_FILES = {
    ".dockerignore.simulator",
    ".env.example",
    ".gitignore",
    ".ntfy-topic.example",
    "AGENTS.md",
    "CLAUDE.md",
    "Dockerfile.simulator",
    "HANDOFF.md",
    "README.md",
    "config.py",
    "package.json",
    "pytest.ini",
    "requirements-ml.txt",
    "requirements-simulator.txt",
    "requirements.txt",
    "sitecustomize.py",
    "snapshot_schema.py",
    "start.sh",
}

ROOT_ALLOWED_PREFIXES = (
    ".github/",
    "app/",
    "coach/",
    "models/",
    "tests/",
)

DATA_ALLOWED_FILES = {"data/README.md"}

OUTPUTS_ALLOWED_PREFIX = "outputs/coach/"

SRC_ALLOWED_FILES = {"src/__init__.py"}
SRC_ALLOWED_PREFIXES = (
    "src/combat_engine/",
    "src/models/",
)

SCRIPTS_ALLOWED_FILES = {
    "scripts/ci/check_dual_track_guard.py",
    "scripts/ci/check_no_tracked_asset_packs.py",
    "scripts/ci/check_public_surface_allowlist.py",
    "scripts/notify-ntfy.ps1",
    "scripts/sync_agents_to_claude.py",
    "scripts/verify.ps1",
}

SIMULATOR_ALLOWED_FILES = {
    "simulator/__init__.py",
    "simulator/benchmark.py",
    "simulator/cloud_runner.py",
    "simulator/config.py",
    "simulator/conftest.py",
    "simulator/test_item_combat.py",
    "simulator/validate_output.py",
    "simulator/data/augments_set16.json",
    "simulator/data/combat_data.json",
    "simulator/data/helper_units.json",
    "simulator/data/set16_items.py",
    "simulator/data/timing_constants.json",
    "simulator/data/traits.json",
    "simulator/data/validate_reference_data.py",
}
SIMULATOR_ALLOWED_PREFIXES = (
    "simulator/core/",
    "simulator/game/",
)

KNOWLEDGE_BASE_ALLOWED_FILES = {
    "knowledge-base/README.md",
    "knowledge-base/manifests/.gitkeep",
    "knowledge-base/manifests/CONTRACT.md",
    "knowledge-base/manifests/README.md",
    "knowledge-base/manifests/manifest.schema.json",
    "knowledge-base/sources/web-scrape/README.md",
    "knowledge-base/sources/web-scrape/canonical/.gitkeep",
    "knowledge-base/sources/web-scrape/incoming/.gitkeep",
    "knowledge-base/sources/web-scrape/metadata/.gitkeep",
    "knowledge-base/sources/web-scrape/processed/.gitkeep",
}


def tracked_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def is_allowed(path: str) -> bool:
    if path in ROOT_ALLOWED_FILES:
        return True

    if any(path.startswith(prefix) for prefix in ROOT_ALLOWED_PREFIXES):
        return True

    if path.startswith("data/"):
        return path in DATA_ALLOWED_FILES

    if path.startswith("outputs/"):
        return path.startswith(OUTPUTS_ALLOWED_PREFIX)

    if path.startswith("src/"):
        return path in SRC_ALLOWED_FILES or any(
            path.startswith(prefix) for prefix in SRC_ALLOWED_PREFIXES
        )

    if path.startswith("scripts/"):
        return path in SCRIPTS_ALLOWED_FILES

    if path.startswith("simulator/"):
        return path in SIMULATOR_ALLOWED_FILES or any(
            path.startswith(prefix) for prefix in SIMULATOR_ALLOWED_PREFIXES
        )

    if path.startswith("knowledge-base/"):
        return path in KNOWLEDGE_BASE_ALLOWED_FILES

    return False


def find_violations(paths: Iterable[str]) -> list[str]:
    return sorted(path for path in paths if not is_allowed(path))


def main() -> int:
    violations = find_violations(tracked_files())
    if violations:
        print("Public surface allowlist violations:")
        for path in violations:
            print(f"  - {path}")
        return 1

    print("Public surface allowlist check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
