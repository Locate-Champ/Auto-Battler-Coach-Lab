"""Feature engineering for TFT board states."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._feature_engineering_batch import _BatchTransformMixin
from ._feature_engineering_config import (
    _REQUIRED_COLUMN_GROUPS,
    ATTACK_SPEED_CAP,
    BOARD_COLS,
    DEFAULT_STAGE_DIVISOR,
    EPSILON,
    REQUIRED_COLUMNS,
    STAR_SCALING_AD,
    STAR_SCALING_HP,
    FeatureConfig,
    TraitMetadata,
    _decode_maybe_json,
    _normalize_token,
    _safe_float,
    _safe_int,
)
from ._feature_engineering_loaders import _LoaderMixin
from ._feature_engineering_transform import _TransformMixin
from .feature_config import DEFAULT_CONFIG, NumericFeatureConfig

_log = logging.getLogger(__name__)


class TFTFeatureEngineer(_LoaderMixin, _TransformMixin, _BatchTransformMixin):
    """Transforms raw board state into engineered feature vectors."""

    def __init__(
        self,
        config: Optional[FeatureConfig] = None,
        repo_root: Optional[Path] = None,
        numeric_config: Optional[NumericFeatureConfig] = None,
    ) -> None:
        self.config = config or FeatureConfig()
        self._numeric_config = numeric_config or DEFAULT_CONFIG
        self.repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()

        self.champion_costs: Dict[str, int] = {}
        self.champion_stats: Dict[str, Dict[str, float]] = {}
        self.champion_traits: Dict[str, List[str]] = {}
        self.champion_lookup: Dict[str, str] = {}

        self.item_stats: Dict[str, Dict[str, float]] = {}
        self.item_types: Dict[str, str] = {}
        self.item_lookup: Dict[str, str] = {}
        self.component_items: set[str] = set()

        self.traits: List[TraitMetadata] = []
        self.trait_lookup: Dict[str, str] = {}
        self._trait_api_names: frozenset[str] = frozenset()

        self.augment_tiers: Dict[str, int] = {}
        self.augment_flags: Dict[str, tuple] = {}
        self.augment_lookup: Dict[str, str] = {}
        self.augment_encoding: Dict[str, int] = {}

        self.personal_carry_stats: Dict[str, tuple] = {}
        self.personal_item_scores: Dict[str, float] = {}

        self._load_reference_data()
        self._build_fast_lookup_sets()
        self._feature_names_cache = self._build_feature_names()

    # --- Pickle optimization: exclude large derived caches from serialization ---
    # The packed dicts (_champion_packed, _item_packed, flag sets) and
    # _feature_names_cache are all derived from the base reference dicts.
    # Excluding them reduces pickle size by ~70% and they are rebuilt on unpickle.
    _DERIVED_ATTRS = (
        "_champion_packed",
        "_item_packed",
        "_qss_items",
        "_guardbreaker_items",
        "_blue_buff_items",
        "_shojin_items",
        "_morello_items",
        "_ionic_items",
        "_cc_heavy_api_names",
        "_item_personal_by_canonical",
        "_feature_names_cache",
    )

    def __getstate__(self) -> Dict[str, Any]:
        state = self.__dict__.copy()
        for attr in self._DERIVED_ATTRS:
            state.pop(attr, None)
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        self._build_fast_lookup_sets()
        self._feature_names_cache = self._build_feature_names()


FeatureEngineer = TFTFeatureEngineer

# Re-export public symbols for backward compatibility.
# These names are available via ``from models.feature_engineering import X``.
__all__ = [
    "ATTACK_SPEED_CAP",
    "BOARD_COLS",
    "DEFAULT_CONFIG",
    "DEFAULT_STAGE_DIVISOR",
    "EPSILON",
    "FeatureConfig",
    "FeatureEngineer",
    "NumericFeatureConfig",
    "REQUIRED_COLUMNS",
    "STAR_SCALING_AD",
    "STAR_SCALING_HP",
    "TFTFeatureEngineer",
    "TraitMetadata",
    "_REQUIRED_COLUMN_GROUPS",
    "_decode_maybe_json",
    "_normalize_token",
    "_safe_float",
    "_safe_int",
]
