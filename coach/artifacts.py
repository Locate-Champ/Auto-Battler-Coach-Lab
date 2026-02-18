from __future__ import annotations

import os
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def runtime_outputs_dir() -> Path:
    direct = os.getenv("TFT_OUTPUTS_DIR")
    if direct:
        return Path(direct)

    artifact_root = os.getenv("TFT_ARTIFACT_ROOT")
    if artifact_root:
        return Path(artifact_root) / "outputs" / "coach"

    return _repo_root() / "outputs" / "coach"


def checkpoint_dir() -> Path:
    direct = os.getenv("TFT_CHECKPOINT_DIR")
    if direct:
        return Path(direct)

    artifact_root = os.getenv("TFT_ARTIFACT_ROOT")
    if artifact_root:
        return Path(artifact_root) / "checkpoints"

    return _repo_root() / "models" / "checkpoints"
