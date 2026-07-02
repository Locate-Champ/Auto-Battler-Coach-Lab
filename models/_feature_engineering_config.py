"""Feature engineering configuration: constants, dataclasses, and helper functions."""

from __future__ import annotations

import functools
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Tuple

EPSILON = 1e-6
STAR_SCALING_HP = {1: 1.0, 2: 1.8, 3: 3.24}
STAR_SCALING_AD = {1: 1.0, 2: 1.5, 3: 2.25}
ATTACK_SPEED_CAP = 5.0
BOARD_COLS = 7
DEFAULT_STAGE_DIVISOR = 7

# Required columns for transform_batch() and transform_arrow_batch().
# These are the columns that MUST be present after normalization.
# Both dict and Arrow paths access these columns — missing ones produce
# silent zero-filled features that corrupt training.
REQUIRED_COLUMNS: frozenset = frozenset(
    {
        "level",
        "hp",
        "gold",
        "round",
        "augments",
    }
)

# Columns where the code supports alternative names from raw simulation output.
# At least ONE name from each group must be present.
_REQUIRED_COLUMN_GROUPS: tuple = (
    (
        "streak",
        "win_streak",
    ),  # _economy_features tries streak, falls back to win_streak - loss_streak
    ("units", "board", "board_names"),  # _extract_units tries units, board, then board_names
    ("traits", "trait_names"),  # _extract_traits tries traits, then trait_names/trait_counts
)

_ECON_AUGMENT_KEYWORDS = (
    "gold",
    "interest",
    "xp",
    "economy",
    "reroll",
    "shop",
    "income",
)
_COMBAT_AUGMENT_KEYWORDS = (
    "damage",
    "attack",
    "armor",
    "magic",
    "health",
    "shield",
    "stun",
    "cast",
    "mana",
)
_TRAIT_AUGMENT_KEYWORDS = ("trait", "emblem", "allies that share", "your ")
_CC_HEAVY_NAME_KEYS = (
    "sejuani",
    "nautilus",
    "sion",
    "jarvan",
    "fiddlesticks",
    "morgana",
    "ryze",
    "ahri",
    "zoe",
    "lissandra",
)


@dataclass
class FeatureConfig:
    """Controls which feature groups are active."""

    use_composition: bool = True
    use_economy: bool = True
    use_traits: bool = True
    use_items: bool = True
    use_augments: bool = True
    use_matchup: bool = True
    use_positioning: bool = False
    use_personal_weights: bool = True


@dataclass(frozen=True)
class TraitMetadata:
    """Reference metadata for one trait."""

    api_name: str
    name: str
    breakpoints: Tuple[int, ...]


@functools.lru_cache(maxsize=2048)
def _normalize_token(value: Any) -> str:
    """Normalize free-form names into a stable key."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", text)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Best-effort float conversion."""
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _safe_int(value: Any, default: int = 0) -> int:
    """Best-effort int conversion."""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _decode_maybe_json(value: Any) -> Any:
    """Decode JSON strings emitted in parquet chunks."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if text[0] not in ("[", "{"):
        return value
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return value
