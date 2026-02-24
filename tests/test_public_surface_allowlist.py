from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_allowlist_checker():
    script_path = REPO_ROOT / "scripts" / "ci" / "check_public_surface_allowlist.py"
    spec = importlib.util.spec_from_file_location("check_public_surface_allowlist", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_allowlist_blocks_local_only_paths() -> None:
    checker = _load_allowlist_checker()
    assert checker.is_allowed("docs/INDEX.md") is False
    assert checker.is_allowed("scraper/index.js") is False
    assert checker.is_allowed(".mcp.json") is False


def test_allowlist_accepts_expected_public_paths() -> None:
    checker = _load_allowlist_checker()
    assert checker.is_allowed("scripts/ci/check_public_surface_allowlist.py") is True
    assert checker.is_allowed("simulator/core/combat_engine.py") is True
    assert checker.is_allowed("simulator/data/augments_set16.json") is True
    assert checker.is_allowed("src/models/recommender.py") is True


def test_find_violations_returns_only_disallowed_entries() -> None:
    checker = _load_allowlist_checker()
    violations = checker.find_violations(
        [
            "simulator/core/combat_engine.py",
            "docs/INDEX.md",
            "knowledge-base/manifests/manifest.schema.json",
            "scripts/sync_metatft.py",
        ]
    )
    assert violations == ["docs/INDEX.md", "scripts/sync_metatft.py"]
