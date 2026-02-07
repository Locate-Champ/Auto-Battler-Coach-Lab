#!/usr/bin/env python3
"""Validate simulator reference data against canonical processed data."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "api" / "processed"
SIMULATOR_DATA_DIR = PROJECT_ROOT / "simulator" / "data"


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_unit_key(api_name: str) -> str:
    key = api_name
    for prefix in ("TFT16_", "TFT9_", "TFT6_", "TFT5_", "TFT_"):
        key = key.replace(prefix, "")
    return key.replace("_", "").lower()


def _load_origin_class_keys() -> set[str]:
    module_path = PROJECT_ROOT / "simulator" / "Simulator" / "origin_class_stats.py"
    spec = importlib.util.spec_from_file_location("origin_class_stats", str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module.origin_class.keys())


def _trait_signature(trait: dict[str, Any]) -> tuple[str, tuple[tuple[Any, Any, Any, tuple[tuple[str, Any], ...]], ...]]:
    effects = []
    for effect in trait.get("effects", []):
        variables = tuple(sorted((effect.get("variables") or {}).items()))
        effects.append(
            (
                effect.get("minUnits"),
                effect.get("maxUnits"),
                effect.get("style"),
                variables,
            )
        )
    return trait.get("apiName"), tuple(effects)


def validate_traits() -> list[str]:
    problems: list[str] = []
    canonical_traits = _load_json(PROCESSED_DIR / "traits_set16.json")
    simulator_traits = _load_json(SIMULATOR_DATA_DIR / "traits.json").get("traits", {})

    canonical_map = {
        trait.get("apiName"): {
            "apiName": trait.get("apiName"),
            "effects": [
                {
                    "minUnits": effect.get("minUnits"),
                    "maxUnits": effect.get("maxUnits"),
                    "style": effect.get("style"),
                    "variables": effect.get("variables", {}),
                }
                for effect in trait.get("effects", [])
            ],
        }
        for trait in canonical_traits
        if trait.get("apiName")
    }

    canonical_ids = set(canonical_map.keys())
    simulator_ids = set(simulator_traits.keys())

    missing = sorted(canonical_ids - simulator_ids)
    extra = sorted(simulator_ids - canonical_ids)
    if missing:
        problems.append(f"Simulator traits missing {len(missing)} IDs: {missing}")
    if extra:
        problems.append(f"Simulator traits has {len(extra)} extra IDs: {extra}")

    for trait_id in sorted(canonical_ids & simulator_ids):
        canonical_sig = _trait_signature(canonical_map[trait_id])
        simulator_sig = _trait_signature(simulator_traits[trait_id])
        if canonical_sig != simulator_sig:
            problems.append(f"Trait effects mismatch: {trait_id}")

    return problems


def validate_helpers() -> list[str]:
    problems: list[str] = []
    units_payload = _load_json(PROCESSED_DIR / "units_set16.json")
    helper_payload = _load_json(SIMULATOR_DATA_DIR / "helper_units.json").get("helpers", [])
    origin_class_keys = _load_origin_class_keys()

    expected_helpers = sorted(
        unit.get("apiName")
        for unit in units_payload
        if unit.get("is_helper", False) and unit.get("apiName")
    )
    actual_helpers = sorted(
        helper.get("apiName")
        for helper in helper_payload
        if helper.get("apiName")
    )

    if expected_helpers != actual_helpers:
        expected_set = set(expected_helpers)
        actual_set = set(actual_helpers)
        missing = sorted(expected_set - actual_set)
        extra = sorted(actual_set - expected_set)
        if missing:
            problems.append(f"helper_units.json missing {len(missing)} IDs: {missing}")
        if extra:
            problems.append(f"helper_units.json has {len(extra)} extra IDs: {extra}")

    for api_name in expected_helpers:
        internal_key = _normalize_unit_key(api_name)
        if internal_key not in origin_class_keys:
            problems.append(
                f"origin_class missing helper mapping for {api_name} -> '{internal_key}'"
            )

    required_combat_helpers = {
        "TFT16_Atakhan",
        "TFT16_AzirSoldier",
        "TFT16_FreljordProp",
        "TFT16_MalzaharVoidling",
        "TFT16_PiltoverInvention",
        "TFT16_AnnieTibbers",
    }
    combat_data = _load_json(SIMULATOR_DATA_DIR / "combat_data.json").get("champions", {})
    missing_from_combat = sorted(required_combat_helpers - set(combat_data.keys()))
    if missing_from_combat:
        problems.append(
            f"combat_data.json missing required helper champions: {missing_from_combat}"
        )

    return problems


def main() -> int:
    problems = []
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
