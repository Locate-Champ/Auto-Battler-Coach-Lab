from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _env_with_fallback(primary: str, fallback: str) -> str | None:
    return os.getenv(primary) or os.getenv(fallback)


def runtime_outputs_dir() -> Path:
    direct = _env_with_fallback("COACH_OUTPUTS_DIR", "TFT_OUTPUTS_DIR")
    if direct:
        return Path(direct)

    artifact_root = _env_with_fallback("COACH_ARTIFACT_ROOT", "TFT_ARTIFACT_ROOT")
    if artifact_root:
        return Path(artifact_root) / "outputs" / "coach"

    return _repo_root() / "outputs" / "coach"


def checkpoint_dir() -> Path:
    direct = _env_with_fallback("COACH_CHECKPOINT_DIR", "TFT_CHECKPOINT_DIR")
    if direct:
        return Path(direct)

    artifact_root = _env_with_fallback("COACH_ARTIFACT_ROOT", "TFT_ARTIFACT_ROOT")
    if artifact_root:
        return Path(artifact_root) / "checkpoints"

    return _repo_root() / "models" / "checkpoints"
