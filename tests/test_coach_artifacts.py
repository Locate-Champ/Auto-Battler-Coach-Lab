from __future__ import annotations

from pathlib import Path

from coach import artifacts


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _clear_env(monkeypatch) -> None:
    for key in (
        "COACH_OUTPUTS_DIR",
        "COACH_CHECKPOINT_DIR",
        "COACH_ARTIFACT_ROOT",
        "TFT_OUTPUTS_DIR",
        "TFT_CHECKPOINT_DIR",
        "TFT_ARTIFACT_ROOT",
    ):
        monkeypatch.delenv(key, raising=False)


def test_runtime_outputs_dir_default(monkeypatch) -> None:
    _clear_env(monkeypatch)

    expected = _repo_root() / "outputs" / "coach"
    assert artifacts.runtime_outputs_dir() == expected


def test_runtime_outputs_dir_prefers_coach_direct(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    coach_direct = tmp_path / "coach-runtime-out"
    tft_direct = tmp_path / "legacy-runtime-out"
    monkeypatch.setenv("COACH_OUTPUTS_DIR", str(coach_direct))
    monkeypatch.setenv("TFT_OUTPUTS_DIR", str(tft_direct))
    monkeypatch.setenv("COACH_ARTIFACT_ROOT", str(tmp_path / "coach-root"))
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(tmp_path / "legacy-root"))

    assert artifacts.runtime_outputs_dir() == coach_direct


def test_runtime_outputs_dir_uses_legacy_direct_fallback(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    tft_direct = tmp_path / "legacy-runtime-out"
    monkeypatch.setenv("TFT_OUTPUTS_DIR", str(tft_direct))

    assert artifacts.runtime_outputs_dir() == tft_direct


def test_runtime_outputs_dir_prefers_coach_artifact_root(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    coach_root = tmp_path / "coach-root"
    root = tmp_path / "artifact-root"
    monkeypatch.setenv("COACH_ARTIFACT_ROOT", str(coach_root))
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.runtime_outputs_dir() == coach_root / "outputs" / "coach"


def test_runtime_outputs_dir_uses_legacy_artifact_root_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    _clear_env(monkeypatch)
    root = tmp_path / "legacy-root"
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.runtime_outputs_dir() == root / "outputs" / "coach"


def test_checkpoint_dir_default(monkeypatch) -> None:
    _clear_env(monkeypatch)

    expected = _repo_root() / "models" / "checkpoints"
    assert artifacts.checkpoint_dir() == expected


def test_checkpoint_dir_prefers_coach_direct(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    coach_direct = tmp_path / "coach-ckpt-direct"
    tft_direct = tmp_path / "legacy-ckpt-direct"
    monkeypatch.setenv("COACH_CHECKPOINT_DIR", str(coach_direct))
    monkeypatch.setenv("TFT_CHECKPOINT_DIR", str(tft_direct))

    assert artifacts.checkpoint_dir() == coach_direct


def test_checkpoint_dir_uses_legacy_direct_fallback(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    direct = tmp_path / "legacy-ckpt-direct"
    monkeypatch.setenv("TFT_CHECKPOINT_DIR", str(direct))

    assert artifacts.checkpoint_dir() == direct


def test_checkpoint_dir_prefers_coach_artifact_root(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    coach_root = tmp_path / "coach-root"
    root = tmp_path / "artifact-root"
    monkeypatch.setenv("COACH_ARTIFACT_ROOT", str(coach_root))
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.checkpoint_dir() == coach_root / "checkpoints"


def test_checkpoint_dir_uses_legacy_artifact_root_fallback(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    root = tmp_path / "legacy-root"
    monkeypatch.setenv("TFT_ARTIFACT_ROOT", str(root))

    assert artifacts.checkpoint_dir() == root / "checkpoints"
