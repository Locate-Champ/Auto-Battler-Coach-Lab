from __future__ import annotations

from pathlib import Path

from coach import artifacts


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_runtime_outputs_dir_default(monkeypatch) -> None:
    monkeypatch.delenv("TFT_OUTPUTS_DIR", raising=False)
    monkeypatch.delenv("TFT_ARTIFACT_ROOT", raising=False)

    expected = _repo_root() / "outputs" / "coach"
    assert artifacts.runtime_outputs_dir() == expected


def test_runtime_outputs_dir_direct_env_takes_precedence(monkeypatch, tmp_path: Path) -> None:
    direct = tmp_path / "runtime-out"
    root = tmp_path / "artifact-root"
    monkeypatch.setenv("TFT_OUTPUTS_DIR", str(direct))
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.runtime_outputs_dir() == direct


def test_runtime_outputs_dir_uses_artifact_root(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "artifact-root"
    monkeypatch.delenv("TFT_OUTPUTS_DIR", raising=False)
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.runtime_outputs_dir() == root / "outputs" / "coach"


def test_checkpoint_dir_default(monkeypatch) -> None:
    monkeypatch.delenv("TFT_CHECKPOINT_DIR", raising=False)
    monkeypatch.delenv("TFT_ARTIFACT_ROOT", raising=False)

    expected = _repo_root() / "models" / "checkpoints"
    assert artifacts.checkpoint_dir() == expected


def test_checkpoint_dir_direct_env_takes_precedence(monkeypatch, tmp_path: Path) -> None:
    direct = tmp_path / "ckpt-direct"
    root = tmp_path / "artifact-root"
    monkeypatch.setenv("TFT_CHECKPOINT_DIR", str(direct))
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.checkpoint_dir() == direct


def test_checkpoint_dir_uses_artifact_root(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "artifact-root"
    monkeypatch.delenv("TFT_CHECKPOINT_DIR", raising=False)
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.checkpoint_dir() == root / "checkpoints"
