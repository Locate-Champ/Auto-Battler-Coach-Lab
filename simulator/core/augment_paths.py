"""Shared augment path resolution for simulator components."""

from __future__ import annotations

import os
from pathlib import Path

SIMULATOR_AUGMENTS_ENV_VAR = "SIMULATOR_AUGMENTS_PATH"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _simulator_default_path() -> Path:
    return _repo_root() / "simulator" / "data" / "augments_set16.json"


def _legacy_default_path() -> Path:
    return _repo_root() / "data" / "api" / "processed" / "augments_set16.json"


def resolve_augment_data_path() -> Path:
    """Resolve augment data path with env override and legacy fallback."""
    override = os.environ.get(SIMULATOR_AUGMENTS_ENV_VAR, "").strip()
    candidates: list[Path] = []

    if override:
        candidates.append(Path(override).expanduser())

    candidates.append(_simulator_default_path())
    candidates.append(_legacy_default_path())

    seen: set[Path] = set()
    deduped: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(candidate)

    for candidate in deduped:
        if candidate.exists():
            return candidate

    return _simulator_default_path()
