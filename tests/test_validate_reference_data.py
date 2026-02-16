"""Tests for simulator reference preflight file gating."""

from __future__ import annotations

import json
from pathlib import Path

from simulator.data import validate_reference_data


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_required_files(processed_dir: Path) -> None:
    _write_json(processed_dir / "traits_set16.json", [{"apiName": "Trait", "effects": []}])
    _write_json(processed_dir / "units_set16.json", [{"apiName": "Unit", "cost": 1, "stats": {}}])
    _write_json(processed_dir / "items_set16.json", [{"apiName": "Item", "name": "Item", "effects": []}])
    _write_json(processed_dir / "augments_set16.json", [{"apiName": "Aug", "name": "Aug", "effects": []}])


def test_validate_required_processed_files_missing_file(tmp_path: Path, monkeypatch) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(validate_reference_data, "PROCESSED_DIR", processed_dir)

    problems = validate_reference_data.validate_required_processed_files()
    assert any("Missing required processed file" in issue for issue in problems)
    assert any("traits_set16.json" in issue for issue in problems)


def test_validate_required_processed_files_empty_payload(tmp_path: Path, monkeypatch) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    _write_valid_required_files(processed_dir)
    _write_json(processed_dir / "items_set16.json", [])
    monkeypatch.setattr(validate_reference_data, "PROCESSED_DIR", processed_dir)

    problems = validate_reference_data.validate_required_processed_files()
    assert any("items_set16.json is empty" in issue for issue in problems)


def test_validate_required_processed_files_missing_required_key(tmp_path: Path, monkeypatch) -> None:
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    _write_valid_required_files(processed_dir)
    _write_json(processed_dir / "augments_set16.json", [{"apiName": "Aug", "name": "Aug"}])
    monkeypatch.setattr(validate_reference_data, "PROCESSED_DIR", processed_dir)

    problems = validate_reference_data.validate_required_processed_files()
    assert any("augments_set16.json entry index 0 missing required keys" in issue for issue in problems)
