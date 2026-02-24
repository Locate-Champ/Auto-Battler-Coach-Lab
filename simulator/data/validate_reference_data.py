#!/usr/bin/env python3
"""Validate tracked simulator reference data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIMULATOR_DATA_DIR = PROJECT_ROOT / "simulator" / "data"
REQUIRED_SIMULATOR_FILES = (
    "combat_data.json",
    "traits.json",
    "helper_units.json",
    "timing_constants.json",
    "augments_set16.json",
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_required_simulator_files() -> list[str]:
    problems: list[str] = []

    for filename in REQUIRED_SIMULATOR_FILES:
        path = SIMULATOR_DATA_DIR / filename
        if not path.exists():
            problems.append(f"Missing required simulator file: {path}")
            continue

        try:
            payload = _load_json(path)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"Failed to load {path}: {exc}")
            continue

        if filename == "augments_set16.json":
            if not isinstance(payload, list):
                problems.append(f"{path} must be a JSON array, got {type(payload).__name__}")
                continue
            if not payload:
                problems.append(f"{path} is empty")
                continue
            for idx, entry in enumerate(payload):
                if not isinstance(entry, dict):
                    problems.append(
                        f"{path} entries must be objects, got {type(entry).__name__} at index {idx}"
                    )
                    break
                missing_keys = [key for key in ("apiName", "name", "effects") if key not in entry]
                if missing_keys:
                    problems.append(
                        f"{path} entry index {idx} missing required keys: {missing_keys}"
                    )
                    break
            continue

        if not isinstance(payload, dict):
            problems.append(f"{path} must be a JSON object, got {type(payload).__name__}")

    return problems


def validate_traits() -> list[str]:
    path = SIMULATOR_DATA_DIR / "traits.json"
    payload = _load_json(path)
    problems: list[str] = []

    traits = payload.get("traits")
    if not isinstance(traits, dict):
        return [f"{path} must contain an object field 'traits'."]
    if not traits:
        return [f"{path} has no trait entries."]

    for trait_id, trait_payload in traits.items():
        if not isinstance(trait_payload, dict):
            problems.append(f"{path} trait '{trait_id}' is not an object.")
            continue
        effects = trait_payload.get("effects")
        if not isinstance(effects, list):
            problems.append(f"{path} trait '{trait_id}' must define list field 'effects'.")

    return problems


def validate_helpers() -> list[str]:
    helper_payload = _load_json(SIMULATOR_DATA_DIR / "helper_units.json")
    helpers = helper_payload.get("helpers")
    problems: list[str] = []

    if not isinstance(helpers, list):
        return [f"{SIMULATOR_DATA_DIR / 'helper_units.json'} must contain list field 'helpers'."]

    helper_ids: set[str] = set()
    for idx, helper in enumerate(helpers):
        if not isinstance(helper, dict):
            problems.append(f"helper_units.json entry index {idx} is not an object.")
            continue
        api_name = helper.get("apiName")
        if not isinstance(api_name, str) or not api_name:
            problems.append(f"helper_units.json entry index {idx} missing non-empty 'apiName'.")
            continue
        helper_ids.add(api_name)

    required_combat_helpers = {
        "TFT16_Atakhan",
        "TFT16_AzirSoldier",
        "TFT16_FreljordProp",
        "TFT16_MalzaharVoidling",
        "TFT16_PiltoverInvention",
        "TFT16_AnnieTibbers",
    }
    missing_helper_entries = sorted(required_combat_helpers - helper_ids)
    if missing_helper_entries:
        problems.append(
            f"helper_units.json missing required helper entries: {missing_helper_entries}"
        )

    combat_data = _load_json(SIMULATOR_DATA_DIR / "combat_data.json")
    champions = combat_data.get("champions", {})
    if not isinstance(champions, dict):
        problems.append("combat_data.json must contain object field 'champions'.")
    else:
        missing_from_combat = sorted(required_combat_helpers - set(champions.keys()))
        if missing_from_combat:
            problems.append(
                f"combat_data.json missing required helper champions: {missing_from_combat}"
            )

    return problems


def main() -> int:
    problems = validate_required_simulator_files()
    if not problems:
        problems.extend(validate_traits())
        problems.extend(validate_helpers())

    if problems:
        print("Simulator reference validation failed:")
        for issue in problems:
            print(f"  - {issue}")
        return 1

    print("Simulator reference validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
