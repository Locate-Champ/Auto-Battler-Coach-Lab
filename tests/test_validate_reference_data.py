"""Tests for simulator reference preflight file gating."""

from __future__ import annotations

import json
from pathlib import Path

from simulator.data import validate_reference_data


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_required_files(simulator_data_dir: Path) -> None:
    _write_json(simulator_data_dir / "combat_data.json", {"champions": {}})
    _write_json(simulator_data_dir / "traits.json", {"traits": {"Trait": {"effects": []}}})
    _write_json(simulator_data_dir / "helper_units.json", {"helpers": []})
    _write_json(simulator_data_dir / "timing_constants.json", {"timing": {}})
    _write_json(
        simulator_data_dir / "augments_set16.json",
        [{"apiName": "Aug", "name": "Aug", "effects": []}],
    )


def test_validate_required_simulator_files_missing_file(tmp_path: Path, monkeypatch) -> None:
    simulator_data_dir = tmp_path / "simulator-data"
    simulator_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(validate_reference_data, "SIMULATOR_DATA_DIR", simulator_data_dir)

    problems = validate_reference_data.validate_required_simulator_files()
    assert any("Missing required simulator file" in issue for issue in problems)
    assert any("combat_data.json" in issue for issue in problems)


def test_validate_required_simulator_files_empty_augments_payload(
    tmp_path: Path, monkeypatch
) -> None:
    simulator_data_dir = tmp_path / "simulator-data"
    simulator_data_dir.mkdir(parents=True, exist_ok=True)
    _write_valid_required_files(simulator_data_dir)
    _write_json(simulator_data_dir / "augments_set16.json", [])
    monkeypatch.setattr(validate_reference_data, "SIMULATOR_DATA_DIR", simulator_data_dir)

    problems = validate_reference_data.validate_required_simulator_files()
    assert any("augments_set16.json is empty" in issue for issue in problems)


def test_validate_required_simulator_files_missing_required_key(
    tmp_path: Path, monkeypatch
) -> None:
    simulator_data_dir = tmp_path / "simulator-data"
    simulator_data_dir.mkdir(parents=True, exist_ok=True)
    _write_valid_required_files(simulator_data_dir)
    _write_json(simulator_data_dir / "augments_set16.json", [{"apiName": "Aug", "name": "Aug"}])
    monkeypatch.setattr(validate_reference_data, "SIMULATOR_DATA_DIR", simulator_data_dir)

    problems = validate_reference_data.validate_required_simulator_files()
    assert any(
        "augments_set16.json entry index 0 missing required keys" in issue for issue in problems
    )
