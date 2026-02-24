"""Shared simulator snapshot schema constants."""

from __future__ import annotations

import json
from typing import Any, Final, Mapping

JSONISH_COLUMNS: Final[tuple[str, ...]] = (
    "board_names",
    "board_stars",
    "trait_names",
    "trait_counts",
    "augments",
    "units",
    "traits",
    "opponent_units",
    "opponent_traits",
    "opponent_augments",
)


def decode_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or text[0] not in ("[", "{"):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value


def normalize_jsonish_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    for key in JSONISH_COLUMNS:
        if key in normalized:
            normalized[key] = decode_jsonish(normalized[key])
    return normalized
