from __future__ import annotations

from pathlib import Path

from simulator.core.augment_paths import resolve_augment_data_path


def test_resolve_augment_data_path_defaults_to_simulator_baseline(monkeypatch) -> None:
    monkeypatch.delenv("SIMULATOR_AUGMENTS_PATH", raising=False)
    resolved = resolve_augment_data_path()
    expected = Path("simulator/data/augments_set16.json")
    assert str(resolved).replace("\\", "/").endswith(str(expected).replace("\\", "/"))


def test_resolve_augment_data_path_prefers_env_override(tmp_path: Path, monkeypatch) -> None:
    override_file = tmp_path / "custom_augments.json"
    override_file.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("SIMULATOR_AUGMENTS_PATH", str(override_file))
    resolved = resolve_augment_data_path()
    assert resolved == override_file
