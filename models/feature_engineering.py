"""Feature engineering for TFT board states."""

from __future__ import annotations

import functools
import json
import logging
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .feature_config import DEFAULT_CONFIG, NumericFeatureConfig

try:
    from .fe_fast import (
        CYTHON_AVAILABLE as _CYTHON_FE,
    )
    from .fe_fast import (
        parse_units_column_fast as _cy_parse_units_column,
    )
    from .fe_fast import (
        team_summary_fast as _cy_team_summary,
    )
except (ImportError, OSError):
    _cy_team_summary = None
    _cy_parse_units_column = None
    _CYTHON_FE = False

_log = logging.getLogger(__name__)

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


class TFTFeatureEngineer:
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
        self.augment_flags: Dict[str, Tuple[bool, bool, bool]] = {}
        self.augment_lookup: Dict[str, str] = {}
        self.augment_encoding: Dict[str, int] = {}

        self.personal_carry_stats: Dict[str, Tuple[float, float]] = {}
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

    def _load_reference_data(self) -> None:
        self._load_champions()
        self._load_traits()
        self._load_items()
        self._load_augments()
        self._load_personal_reference()

    def _build_fast_lookup_sets(self) -> None:
        """Pre-compute sets for fast item/champion flag detection."""
        # Item flag sets: map canonical item names to boolean flags
        self._qss_items: set[str] = set()
        self._guardbreaker_items: set[str] = set()
        self._blue_buff_items: set[str] = set()
        self._shojin_items: set[str] = set()
        self._morello_items: set[str] = set()
        self._ionic_items: set[str] = set()
        for item_name in self.item_stats:
            key = _normalize_token(item_name)
            if "quicksilver" in key or key == "qss":
                self._qss_items.add(item_name)
            if "guardbreaker" in key:
                self._guardbreaker_items.add(item_name)
            if "bluebuff" in key:
                self._blue_buff_items.add(item_name)
            if "spearofshojin" in key or "shojin" in key:
                self._shojin_items.add(item_name)
            if "morello" in key:
                self._morello_items.add(item_name)
            if "ionicspark" in key:
                self._ionic_items.add(item_name)

        # CC-heavy champion set: precompute from champion API names
        self._cc_heavy_api_names: frozenset[str] = frozenset(
            api
            for api in self.champion_costs
            if any(cc in _normalize_token(api) for cc in _CC_HEAVY_NAME_KEYS)
        )

        # Packed champion data: api_name → (cost, hp, ad, as, armor, mr, is_cc_heavy)
        self._champion_packed: Dict[str, Tuple[float, float, float, float, float, float, bool]] = {}
        for api_name in self.champion_costs:
            cstats = self.champion_stats.get(api_name, {})
            self._champion_packed[api_name] = (
                float(self.champion_costs[api_name]),
                cstats.get("hp", 0.0),
                cstats.get("ad", 0.0),
                cstats.get("attack_speed", 0.7),
                cstats.get("armor", 0.0),
                cstats.get("mr", 0.0),
                api_name in self._cc_heavy_api_names,
            )

        # Packed item data: canonical → (ad, ap, hp, as, armor, mr, type_code, is_component, flag_bits)
        # type_code: 0=offensive, 1=defensive, 2=utility
        # flag_bits: qss=1, guardbreaker=2, blue_buff=4, shojin=8, morello=16, ionic=32
        self._item_packed: Dict[
            str, Tuple[float, float, float, float, float, float, int, bool, int]
        ] = {}
        for item_name in self.item_stats:
            istats = self.item_stats[item_name]
            itype = self.item_types.get(item_name, "utility")
            type_code = 0 if itype == "offensive" else (1 if itype == "defensive" else 2)
            is_comp = item_name in self.component_items
            flags = 0
            if item_name in self._qss_items:
                flags |= 1
            if item_name in self._guardbreaker_items:
                flags |= 2
            if item_name in self._blue_buff_items:
                flags |= 4
            if item_name in self._shojin_items:
                flags |= 8
            if item_name in self._morello_items:
                flags |= 16
            if item_name in self._ionic_items:
                flags |= 32
            self._item_packed[item_name] = (
                istats.get("ad", 0.0),
                istats.get("ap", 0.0),
                istats.get("hp", 0.0),
                istats.get("attack_speed", 0.0),
                istats.get("armor", 0.0),
                istats.get("magic_resist", 0.0),
                type_code,
                is_comp,
                flags,
            )

        # Pre-computed personal item scores: canonical_item_name → score
        # Avoids per-row _normalize_token calls in _personal_features_batch
        self._item_personal_by_canonical: Dict[str, float] = {}
        for item_name in self.item_stats:
            normalized = _normalize_token(item_name)
            if normalized in self.personal_item_scores:
                self._item_personal_by_canonical[item_name] = self.personal_item_scores[normalized]
        for _token_key, canonical in self.item_lookup.items():
            if canonical not in self._item_personal_by_canonical:
                if _token_key in self.personal_item_scores:
                    self._item_personal_by_canonical[canonical] = self.personal_item_scores[
                        _token_key
                    ]

    def _load_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _load_champions(self) -> None:
        path = self.repo_root / "simulator" / "data" / "combat_data.json"
        payload = self._load_json(path, {})
        champions = payload.get("champions", {})
        for api_name, info in champions.items():
            if not isinstance(info, Mapping):
                continue
            champion_api = str(info.get("apiName", api_name))
            display_name = str(info.get("name", champion_api))
            cost = _safe_int(info.get("cost"), default=0)
            stats = info.get("stats", {}) or {}
            hp = _safe_float(stats.get("hp"))
            ad = _safe_float(stats.get("ad", stats.get("damage")))
            attack_speed = _safe_float(stats.get("attackSpeed", stats.get("as")), default=0.7)
            armor = _safe_float(stats.get("armor"))
            mr = _safe_float(stats.get("magicResist", stats.get("mr")))
            traits = [self._normalize_trait_name(t) for t in info.get("traits", []) if t]

            self.champion_costs[champion_api] = cost
            self.champion_stats[champion_api] = {
                "hp": hp,
                "ad": ad,
                "attack_speed": attack_speed,
                "armor": armor,
                "mr": mr,
            }
            self.champion_traits[champion_api] = traits

            aliases = {
                champion_api,
                display_name,
                champion_api.replace("TFT16_", ""),
                champion_api.replace("TFT_", ""),
                champion_api.replace("TFT16_", "").replace("_", " "),
            }
            for alias in aliases:
                key = _normalize_token(alias)
                if key:
                    self.champion_lookup[key] = champion_api

    def _load_traits(self) -> None:
        path = self.repo_root / "simulator" / "data" / "traits.json"
        payload = self._load_json(path, {})
        raw_traits = payload.get("traits", {})
        trait_rows: List[TraitMetadata] = []
        for api_name, trait in raw_traits.items():
            if not isinstance(trait, Mapping):
                continue
            name = str(trait.get("name", api_name))
            effects = trait.get("effects", []) or []
            breakpoints = sorted(
                {
                    _safe_int(effect.get("minUnits"))
                    for effect in effects
                    if _safe_int(effect.get("minUnits")) > 0
                }
            )
            metadata = TraitMetadata(
                api_name=str(api_name),
                name=name,
                breakpoints=tuple(breakpoints),
            )
            trait_rows.append(metadata)

            aliases = {
                api_name,
                name,
                api_name.replace("TFT16_", ""),
                api_name.replace("TFT_", ""),
                self._normalize_trait_name(name),
            }
            for alias in aliases:
                key = _normalize_token(alias)
                if key:
                    self.trait_lookup[key] = metadata.api_name

        self.traits = sorted(trait_rows, key=lambda item: item.api_name)
        self._trait_api_names: frozenset[str] = frozenset(t.api_name for t in self.traits)

    def _normalize_item_effects(self, effects: Mapping[str, Any]) -> Dict[str, float]:
        _as_threshold = self._numeric_config.attack_speed_pct_threshold

        def pick(keys: Sequence[str]) -> float:
            for key in keys:
                if key in effects:
                    value = _safe_float(effects.get(key))
                    # Riot data mixes absolute and percentage attack speed values.
                    if key in {"AS", "AttackSpeed"} and value > _as_threshold:
                        return value / 100.0
                    return value
            return 0.0

        return {
            "ad": pick(("ad", "AD", "Damage", "ADDamage", "AD_NotStatBar")),
            "ap": pick(("ap", "AP", "SpellPower", "AbilityPower", "AP_NotStatBar")),
            "hp": pick(("hp", "Health")),
            "attack_speed": pick(("attack_speed", "AS", "AttackSpeed")),
            "armor": pick(("armor", "Armor")),
            "magic_resist": pick(("magic_resist", "MagicResist", "MR")),
        }

    def _classify_item_type(
        self,
        item_name: str,
        tags: Sequence[Any],
        stats: Mapping[str, float],
        description: str,
    ) -> str:
        tag_key = " ".join(str(tag).lower() for tag in tags)
        desc_key = description.lower()
        if "emblem" in tag_key or "trait" in tag_key:
            return "utility"
        nc = self._numeric_config
        offensive_signal = (
            stats["ad"] + stats["ap"] + stats["attack_speed"] * nc.attack_speed_weight
        )
        defensive_signal = (
            stats["hp"] / nc.hp_divisor
            + stats["armor"] / nc.armor_divisor
            + stats["magic_resist"] / nc.mr_divisor
        )
        if (
            "damage" in desc_key
            or "execute" in desc_key
            or offensive_signal >= defensive_signal + nc.classification_threshold
        ):
            return "offensive"
        if (
            "shield" in desc_key
            or "heal" in desc_key
            or defensive_signal >= offensive_signal + nc.classification_threshold
        ):
            return "defensive"
        # Utility catches emblems, economy, and hybrid items.
        if any(token in desc_key for token in ("mana", "sunder", "shred", "gold", "stun")):
            return "utility"
        if "artifact" in item_name.lower():
            return "utility"
        return "offensive" if offensive_signal >= defensive_signal else "defensive"

    def _load_items(self) -> None:
        api_items = self._load_json(
            self.repo_root / "data" / "api" / "processed" / "items_set16.json", []
        )
        for item in api_items:
            if not isinstance(item, Mapping):
                continue
            api_name = str(item.get("apiName", ""))
            if not api_name:
                continue
            display_name = str(item.get("name", api_name))
            effects = item.get("effects", {}) or {}
            tags = item.get("tags", []) or []
            description = str(item.get("description", item.get("desc", "")))
            stats = self._normalize_item_effects(effects)

            self.item_stats[api_name] = stats
            self.item_types[api_name] = self._classify_item_type(
                display_name, tags, stats, description
            )

            aliases = {api_name, display_name, item.get("en_name", display_name)}
            for alias in aliases:
                key = _normalize_token(alias)
                if key:
                    self.item_lookup[key] = api_name

            composition = item.get("composition", []) or []
            if composition:
                continue
            if "emblem" in display_name.lower():
                continue
            # Component items are mostly no-composition, non-emblem entries.
            self.component_items.add(api_name)

        # Merge simulator-native item aliases/stats for rows that use internal names.
        try:
            from simulator.data import set16_items  # type: ignore

            for internal_name, stats in set16_items.ALL_ITEMS.items():
                normalized_stats = self._normalize_item_effects(stats)
                self.item_stats.setdefault(internal_name, normalized_stats)
                self.item_types.setdefault(
                    internal_name,
                    self._classify_item_type(internal_name, (), normalized_stats, ""),
                )
                lookup_key = _normalize_token(internal_name)
                if lookup_key:
                    self.item_lookup.setdefault(lookup_key, internal_name)

            for alias, canonical in set16_items.ITEM_ALIASES.items():
                alias_key = _normalize_token(alias)
                if alias_key:
                    self.item_lookup[alias_key] = canonical

            for component in set16_items.BASE_COMPONENTS.keys():
                self.component_items.add(component)
                self.component_items.add(f"TFT_Item_{component}")
        except (ImportError, ModuleNotFoundError):
            _log.debug("simulator.data.set16_items not available; skipping native item merge")

    def _infer_augment_tier(self, augment: Mapping[str, Any]) -> int:
        texture = str(augment.get("texture", "")) + " " + str(augment.get("icon", ""))
        match = re.search(r"[_-](III|II|I)(?:[._-]|$)", texture)
        if match:
            roman = match.group(1)
            return {"I": 1, "II": 2, "III": 3}.get(roman, 2)
        name_desc = f"{augment.get('name', '')} {augment.get('description', augment.get('desc', ''))}".lower()
        if "prismatic" in name_desc:
            return 3
        if "silver" in name_desc:
            return 1
        if "gold" in name_desc:
            return 2
        return 2

    def _infer_augment_flags(self, augment: Mapping[str, Any]) -> Tuple[bool, bool, bool]:
        text = f"{augment.get('name', '')} {augment.get('description', augment.get('desc', ''))}".lower()
        associated_traits = augment.get("associatedTraits", []) or []
        has_trait = bool(associated_traits) or any(
            keyword in text for keyword in _TRAIT_AUGMENT_KEYWORDS
        )
        has_econ = any(keyword in text for keyword in _ECON_AUGMENT_KEYWORDS)
        has_combat = any(keyword in text for keyword in _COMBAT_AUGMENT_KEYWORDS) or not has_econ
        return has_econ, has_combat, has_trait

    def _augment_data_candidates(self) -> List[Path]:
        paths: List[Path] = []
        override = os.environ.get("SIMULATOR_AUGMENTS_PATH", "").strip()
        if override:
            paths.append(Path(override).expanduser())
        paths.append(self.repo_root / "simulator" / "data" / "augments_set16.json")
        paths.append(self.repo_root / "data" / "api" / "processed" / "augments_set16.json")
        return paths

    def _load_augments(self) -> None:
        augments: Any = []
        for path in self._augment_data_candidates():
            if not path.exists():
                continue
            augments = self._load_json(path, [])
            break

        if not isinstance(augments, list):
            augments = []

        keyed = []
        for augment in augments:
            if not isinstance(augment, Mapping):
                continue
            api_name = str(augment.get("apiName", ""))
            if not api_name:
                continue
            keyed.append((api_name, augment))
            self.augment_tiers[api_name] = self._infer_augment_tier(augment)
            self.augment_flags[api_name] = self._infer_augment_flags(augment)
            for alias in (api_name, augment.get("name"), augment.get("en_name")):
                key = _normalize_token(alias)
                if key:
                    self.augment_lookup[key] = api_name

        for index, (api_name, _) in enumerate(sorted(keyed, key=lambda entry: entry[0]), start=1):
            self.augment_encoding[api_name] = index

    def _load_personal_reference(self) -> None:
        candidates = [
            self.repo_root / "performance_reference.json",
            self.repo_root / "knowledge-base" / "performance_reference.json",
        ]
        payload: Dict[str, Any] = {}
        for path in candidates:
            if path.exists():
                payload = self._load_json(path, {})
                break

        carries = payload.get("carries", {}) if isinstance(payload, Mapping) else {}
        if isinstance(carries, Mapping):
            for entries in carries.values():
                if not isinstance(entries, list):
                    continue
                for carry in entries:
                    if not isinstance(carry, Mapping):
                        continue
                    name = str(carry.get("name", ""))
                    top4 = _safe_float(carry.get("top4", carry.get("top4_rate")), default=0.0)
                    if top4 > 1.0:
                        top4 /= 100.0
                    avg_place = _safe_float(
                        carry.get("avgPlace", carry.get("avg_placement")),
                        default=self._numeric_config.default_avg_placement,
                    )
                    key = _normalize_token(name)
                    if key:
                        self.personal_carry_stats[key] = (top4, avg_place)

        items = payload.get("items", {}) if isinstance(payload, Mapping) else {}
        if isinstance(items, Mapping):
            for entries in items.values():
                if not isinstance(entries, list):
                    continue
                for item in entries:
                    if not isinstance(item, Mapping):
                        continue
                    name = str(item.get("name", ""))
                    top4 = _safe_float(item.get("top4", item.get("top4_rate")), default=0.0)
                    if top4 > 1.0:
                        top4 /= 100.0
                    avg_place = _safe_float(
                        item.get("avgPlace", item.get("avg_placement")),
                        default=self._numeric_config.default_avg_placement,
                    )
                    score = top4 + (
                        (self._numeric_config.default_avg_placement - avg_place)
                        / self._numeric_config.personal_score_placement_divisor
                    )
                    key = _normalize_token(name)
                    if key:
                        self.personal_item_scores[key] = score

        # CSV fallback from personal exports.
        carry_csv = (
            self.repo_root / "data" / "local" / "personal" / "carry_performance_corrected.csv"
        )
        if carry_csv.exists() and not self.personal_carry_stats:
            with carry_csv.open("r", encoding="utf-8") as handle:
                header = handle.readline().strip().split(",")
                row_map = {name: index for index, name in enumerate(header)}
                for line in handle:
                    parts = [part.strip() for part in line.rstrip("\n").split(",")]
                    if len(parts) < len(header):
                        continue
                    name = parts[row_map["carry"]]
                    top4 = _safe_float(parts[row_map["top4_rate"]], default=0.0)
                    if top4 > 1.0:
                        top4 /= 100.0
                    avg_place = _safe_float(
                        parts[row_map["avg_placement"]],
                        default=self._numeric_config.default_avg_placement,
                    )
                    self.personal_carry_stats[_normalize_token(name)] = (top4, avg_place)

    def _canonical_champion_id(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        if text in self.champion_costs:
            return text
        key = _normalize_token(text)
        return self.champion_lookup.get(key, "")

    def _canonical_item_name(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        if text in self.item_stats:
            return text
        key = _normalize_token(text)
        return self.item_lookup.get(key, text)

    def _canonical_trait_api(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value)
        if text in self._trait_api_names:
            return text
        key = _normalize_token(text)
        return self.trait_lookup.get(key, "")

    def _normalize_trait_name(self, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        canonical = self._canonical_trait_api(text)
        if canonical:
            return canonical
        return text.lower()

    def _extract_augments(self, row: Mapping[str, Any]) -> List[str]:
        raw = _decode_maybe_json(row.get("augments", []))
        augments: List[Any]
        if isinstance(raw, list):
            augments = raw
        else:
            augments = []
            for key in ("aug1", "aug2", "aug3"):
                if key in row and row[key] is not None:
                    augments.append(row[key])

        resolved: List[str] = []
        for augment in augments[:3]:
            api_name = str(augment)
            if api_name in self.augment_encoding:
                resolved.append(api_name)
                continue
            key = _normalize_token(api_name)
            resolved.append(self.augment_lookup.get(key, api_name))
        while len(resolved) < 3:
            resolved.append("")
        return resolved[:3]

    def _extract_traits(self, row: Mapping[str, Any], prefix: str = "") -> Dict[str, int]:
        raw = _decode_maybe_json(row.get(f"{prefix}traits"))
        traits: Dict[str, int] = {}
        if isinstance(raw, dict):
            for trait_name, count in raw.items():
                api_name = self._canonical_trait_api(trait_name)
                if not api_name:
                    continue
                traits[api_name] = _safe_int(count, default=0)
            if traits:
                return traits

        names = _decode_maybe_json(row.get(f"{prefix}trait_names", []))
        counts = _decode_maybe_json(row.get(f"{prefix}trait_counts", []))
        if isinstance(names, str):
            names = [item.strip() for item in names.split("|") if item.strip()]
        if isinstance(counts, str):
            counts = [item.strip() for item in counts.split("|") if item.strip()]
        if isinstance(names, list):
            for idx, name in enumerate(names):
                count = counts[idx] if isinstance(counts, list) and idx < len(counts) else 0
                api_name = self._canonical_trait_api(name)
                if api_name:
                    traits[api_name] = _safe_int(count, default=0)
        return traits

    def _extract_units(self, row: Mapping[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
        units_key = f"{prefix}units"
        raw_units = _decode_maybe_json(row.get(units_key))
        units: List[Dict[str, Any]] = []
        if isinstance(raw_units, list):
            for unit in raw_units:
                parsed = self._parse_unit(unit)
                if parsed is not None:
                    units.append(parsed)
            if units:
                return units

        board_key = f"{prefix}board"
        raw_board = _decode_maybe_json(row.get(board_key))
        if isinstance(raw_board, list):
            for unit in raw_board:
                parsed = self._parse_unit(unit)
                if parsed is not None:
                    units.append(parsed)
            if units:
                return units

        names = _decode_maybe_json(row.get(f"{prefix}board_names", []))
        stars = _decode_maybe_json(row.get(f"{prefix}board_stars", []))
        if isinstance(names, str):
            names = [entry.strip() for entry in names.split("|") if entry.strip()]
        if isinstance(stars, str):
            stars = [entry.strip() for entry in stars.split("|") if entry.strip()]
        if not isinstance(names, list):
            return units
        for idx, name in enumerate(names):
            star = stars[idx] if isinstance(stars, list) and idx < len(stars) else 1
            api_name = self._canonical_champion_id(name)
            if not api_name:
                continue
            units.append(
                {
                    "champion_id": api_name,
                    "star_level": max(1, min(3, _safe_int(star, default=1))),
                    "items": [],
                    "position": None,
                }
            )
        return units

    def _parse_unit(self, raw_unit: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(raw_unit, dict):
            return None

        # Fast path: Parquet data always has champion_id
        champion = raw_unit.get("champion_id")
        if champion is None:
            champion = (
                raw_unit.get("name") or raw_unit.get("champion") or raw_unit.get("character_id")
            )
        if not champion:
            return None

        api_name = self._canonical_champion_id(champion)
        if not api_name:
            return None

        # Fast path: star_level is always int in Parquet data
        star_raw = raw_unit.get("star_level")
        if star_raw is None:
            star_raw = raw_unit.get("star") or raw_unit.get("tier") or 1
        star_level = (
            star_raw
            if isinstance(star_raw, int) and 1 <= star_raw <= 3
            else max(1, min(3, _safe_int(star_raw, 1)))
        )

        items_raw = raw_unit.get("items") or raw_unit.get("itemNames")
        if items_raw is not None and isinstance(items_raw, str):
            items_raw = _decode_maybe_json(items_raw)
        items: List[str] = []
        if isinstance(items_raw, list):
            for item in items_raw[:3]:
                canonical = self._canonical_item_name(item)
                if canonical:
                    items.append(canonical)

        position_raw = raw_unit.get("position")
        if position_raw is None:
            position_raw = raw_unit.get("pos")
        position: Optional[int]
        if isinstance(position_raw, list) and len(position_raw) == 2:
            position = _safe_int(position_raw[0]) * BOARD_COLS + _safe_int(position_raw[1])
        elif isinstance(position_raw, dict):
            position = _safe_int(position_raw.get("row")) * BOARD_COLS + _safe_int(
                position_raw.get("col")
            )
        elif position_raw is None:
            position = None
        else:
            position = _safe_int(position_raw)

        return {
            "champion_id": api_name,
            "star_level": star_level,
            "items": items,
            "position": position,
        }

    def _position_row(self, position: Optional[int]) -> Optional[int]:
        if position is None or position < 0:
            return None
        return position // BOARD_COLS

    def _team_summary(self, units: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        if _CYTHON_FE and self._champion_packed:
            return _cy_team_summary(
                list(units),
                self._champion_packed,
                self._item_packed,
                self._canonical_item_name,
                math.ceil(len(units) / 2) if units else 0,
            )
        if not units:
            return {
                "num_units": 0.0,
                "total_cost": 0.0,
                "avg_star": 0.0,
                "num_3_stars": 0.0,
                "num_cost_1": 0.0,
                "num_cost_2": 0.0,
                "num_cost_3": 0.0,
                "num_cost_4": 0.0,
                "num_cost_5": 0.0,
                "num_cost_7": 0.0,
                "total_hp_pool": 0.0,
                "total_ad_pool": 0.0,
                "avg_attack_speed": 0.0,
                "avg_armor": 0.0,
                "avg_mr": 0.0,
                "team_dps": 0.0,
                "frontline_hp": 0.0,
                "backline_damage": 0.0,
                "carry_cost": 0.0,
                "carry_star": 0.0,
                "carry_item_count": 0.0,
                "total_items": 0.0,
                "total_completed_items": 0.0,
                "total_components": 0.0,
                "item_offensive": 0.0,
                "item_defensive": 0.0,
                "item_utility": 0.0,
                "item_ad": 0.0,
                "item_ap": 0.0,
                "item_hp": 0.0,
                "item_as": 0.0,
                "item_armor": 0.0,
                "item_mr": 0.0,
                "qss_count": 0.0,
                "cc_heavy_units": 0.0,
                "physical_share": 0.5,
                "magic_share": 0.5,
                "has_qss": 0.0,
                "has_guardbreaker": 0.0,
                "has_blue_buff": 0.0,
                "has_shojin": 0.0,
                "has_morello": 0.0,
                "has_ionic": 0.0,
                "carry_api_name": "",
            }

        n_units = 0
        total_cost = 0.0
        star_sum = 0.0
        num_3_stars = 0.0
        cost_counts: Dict[float, float] = {}
        hp_pool = 0.0
        ad_pool = 0.0
        as_sum = 0.0
        armor_sum = 0.0
        mr_sum = 0.0
        team_dps = 0.0
        frontline_hp = 0.0
        backline_damage = 0.0
        total_items = 0.0
        completed_items = 0.0
        components = 0.0
        item_offensive = 0.0
        item_defensive = 0.0
        item_utility = 0.0
        item_ad = 0.0
        item_ap = 0.0
        item_hp = 0.0
        item_as = 0.0
        item_armor = 0.0
        item_mr = 0.0
        qss_count = 0.0
        cc_heavy_units = 0.0
        has_qss = 0.0
        has_guardbreaker = 0.0
        has_blue_buff = 0.0
        has_shojin = 0.0
        has_morello = 0.0
        has_ionic = 0.0

        best_carry_key = (-1, -1, -1)
        carry_cost = 0.0
        carry_star = 0.0
        carry_item_count = 0.0
        carry_api_name = ""

        half_count = math.ceil(len(units) / 2)
        _champion_packed = self._champion_packed
        _item_packed = self._item_packed
        _canonical_item = self._canonical_item_name

        for unit in units:
            api_name = unit.get("champion_id", "")
            packed = _champion_packed.get(api_name)
            if packed is None:
                continue
            cost, base_hp, base_ad, base_as, base_armor, base_mr, is_cc = packed

            star_raw = unit.get("star_level", 1)
            star_int = (
                star_raw
                if isinstance(star_raw, int) and 1 <= star_raw <= 3
                else max(1, min(3, _safe_int(star_raw, 1)))
            )
            star = float(star_int)
            hp_scale = STAR_SCALING_HP.get(star_int, 1.0)
            ad_scale = STAR_SCALING_AD.get(star_int, 1.0)

            n_units += 1
            total_cost += cost
            star_sum += star
            if star_int >= 3:
                num_3_stars += 1.0
            cost_counts[cost] = cost_counts.get(cost, 0.0) + 1.0

            scaled_hp = base_hp * hp_scale
            scaled_ad = base_ad * ad_scale
            hp_pool += scaled_hp
            ad_pool += scaled_ad

            unit_items = unit.get("items") or []
            item_count = len(unit_items)
            total_items += item_count

            bonus_ad = 0.0
            bonus_ap = 0.0
            bonus_hp = 0.0
            bonus_as = 0.0
            bonus_armor = 0.0
            bonus_mr = 0.0

            for raw_item in unit_items:
                canonical_item = _canonical_item(raw_item)
                ipacked = _item_packed.get(canonical_item)
                if ipacked is None:
                    continue
                i_ad, i_ap, i_hp, i_as, i_armor, i_mr, itype, is_comp, iflags = ipacked

                bonus_ad += i_ad
                item_ad += i_ad
                bonus_ap += i_ap
                item_ap += i_ap
                bonus_hp += i_hp
                item_hp += i_hp
                bonus_as += i_as
                item_as += i_as
                bonus_armor += i_armor
                item_armor += i_armor
                bonus_mr += i_mr
                item_mr += i_mr

                if is_comp:
                    components += 1.0
                else:
                    completed_items += 1.0

                if itype == 0:
                    item_offensive += 1.0
                elif itype == 1:
                    item_defensive += 1.0
                else:
                    item_utility += 1.0

                if iflags & 1:
                    qss_count += 1.0
                    has_qss = 1.0
                if iflags & 2:
                    has_guardbreaker = 1.0
                if iflags & 4:
                    has_blue_buff = 1.0
                if iflags & 8:
                    has_shojin = 1.0
                if iflags & 16:
                    has_morello = 1.0
                if iflags & 32:
                    has_ionic = 1.0

            effective_as = min(ATTACK_SPEED_CAP, base_as * (1.0 + max(0.0, bonus_as)))
            effective_armor = base_armor + bonus_armor
            effective_mr = base_mr + bonus_mr
            effective_ad = scaled_ad * (1.0 + max(0.0, bonus_ad))
            effective_hp = scaled_hp + bonus_hp

            as_sum += effective_as
            armor_sum += effective_armor
            mr_sum += effective_mr
            team_dps += effective_ad * effective_as

            pos = unit.get("position")
            if pos is not None and pos >= 0:
                row_index = pos // BOARD_COLS
            else:
                row_index = 1 if n_units <= half_count else 2
            if row_index <= 1:
                frontline_hp += effective_hp
            else:
                backline_damage += effective_ad + bonus_ap

            carry_key = (item_count, int(cost), star_int)
            if carry_key > best_carry_key:
                best_carry_key = carry_key
                carry_cost = cost
                carry_star = star
                carry_item_count = float(item_count)
                carry_api_name = api_name

            if is_cc:
                cc_heavy_units += 1.0

        total_magic_proxy = item_ap + 1.0
        total_physical_proxy = (
            ad_pool + team_dps * self._numeric_config.dps_weight_in_physical_proxy + 1.0
        )
        physical_share = total_physical_proxy / (total_physical_proxy + total_magic_proxy)
        magic_share = 1.0 - physical_share

        inv_n = 1.0 / max(1, n_units)
        return {
            "num_units": float(n_units),
            "total_cost": total_cost,
            "avg_star": star_sum * inv_n,
            "num_3_stars": num_3_stars,
            "num_cost_1": cost_counts.get(1.0, 0.0),
            "num_cost_2": cost_counts.get(2.0, 0.0),
            "num_cost_3": cost_counts.get(3.0, 0.0),
            "num_cost_4": cost_counts.get(4.0, 0.0),
            "num_cost_5": cost_counts.get(5.0, 0.0),
            "num_cost_7": cost_counts.get(7.0, 0.0),
            "total_hp_pool": float(hp_pool),
            "total_ad_pool": float(ad_pool),
            "avg_attack_speed": as_sum * inv_n,
            "avg_armor": armor_sum * inv_n,
            "avg_mr": mr_sum * inv_n,
            "team_dps": float(team_dps),
            "frontline_hp": float(frontline_hp),
            "backline_damage": float(backline_damage),
            "carry_cost": carry_cost,
            "carry_star": carry_star,
            "carry_item_count": carry_item_count,
            "total_items": float(total_items),
            "total_completed_items": float(completed_items),
            "total_components": float(components),
            "item_offensive": float(item_offensive),
            "item_defensive": float(item_defensive),
            "item_utility": float(item_utility),
            "item_ad": float(item_ad),
            "item_ap": float(item_ap),
            "item_hp": float(item_hp),
            "item_as": float(item_as),
            "item_armor": float(item_armor),
            "item_mr": float(item_mr),
            "qss_count": float(qss_count),
            "cc_heavy_units": float(cc_heavy_units),
            "physical_share": float(physical_share),
            "magic_share": float(magic_share),
            "has_qss": has_qss,
            "has_guardbreaker": has_guardbreaker,
            "has_blue_buff": has_blue_buff,
            "has_shojin": has_shojin,
            "has_morello": has_morello,
            "has_ionic": has_ionic,
            "carry_api_name": carry_api_name,
        }

    def _composition_feature_names(self) -> List[str]:
        return [
            "total_team_cost",
            "avg_star_level",
            "num_3_stars",
            "num_units",
            "num_units_cost_1",
            "num_units_cost_2",
            "num_units_cost_3",
            "num_units_cost_4",
            "num_units_cost_5",
            "num_units_cost_7",
            "total_hp_pool",
            "total_ad_pool",
            "total_ap_pool",
            "avg_attack_speed",
            "avg_armor",
            "avg_mr",
            "team_dps_estimate",
            "frontline_tankiness",
            "backline_damage",
            "carry_cost",
            "carry_stars",
        ]

    def _composition_features(
        self,
        row: Mapping[str, Any],
        *,
        _units: Optional[List[Dict[str, Any]]] = None,
        _summary: Optional[Dict[str, float]] = None,
        _traits: Optional[Dict[str, int]] = None,
    ) -> List[float]:
        units = _units if _units is not None else self._extract_units(row, prefix="")
        traits = _traits if _traits is not None else self._extract_traits(row, prefix="")
        summary = _summary if _summary is not None else self._team_summary(units)
        trait_active_count = float(sum(1 for value in traits.values() if value > 0))
        total_ap_pool = summary["item_ap"] + (
            trait_active_count * self._numeric_config.trait_ap_proxy_per_trait
        )
        return [
            summary["total_cost"],
            summary["avg_star"],
            summary["num_3_stars"],
            summary["num_units"],
            summary["num_cost_1"],
            summary["num_cost_2"],
            summary["num_cost_3"],
            summary["num_cost_4"],
            summary["num_cost_5"],
            summary["num_cost_7"],
            summary["total_hp_pool"],
            summary["total_ad_pool"],
            total_ap_pool,
            summary["avg_attack_speed"],
            summary["avg_armor"],
            summary["avg_mr"],
            summary["team_dps"],
            summary["frontline_hp"],
            summary["backline_damage"],
            summary["carry_cost"],
            summary["carry_star"],
        ]

    def _economy_feature_names(self) -> List[str]:
        return [
            "level",
            "hp",
            "hp_percentage",
            "gold",
            "streak",
            "round",
            "stage",
            "interest_gold",
        ]

    def _economy_features(self, row: Mapping[str, Any]) -> List[float]:
        level = _safe_float(row.get("level"))
        hp = _safe_float(row.get("hp"))
        gold = _safe_float(row.get("gold"))
        round_num = _safe_float(row.get("round"))
        stage = float(int(round_num // DEFAULT_STAGE_DIVISOR) + 1)
        streak = _safe_float(row.get("streak"))
        if streak == 0.0:
            win_streak = _safe_float(row.get("win_streak"))
            loss_streak = _safe_float(row.get("loss_streak"))
            streak = win_streak - loss_streak
        nc = self._numeric_config
        interest = min(nc.max_interest, max(0.0, math.floor(gold / nc.interest_gold_divisor)))
        return [
            level,
            hp,
            hp / nc.hp_divisor,
            gold,
            streak,
            round_num,
            stage,
            interest,
        ]

    def _trait_feature_names(self) -> List[str]:
        names: List[str] = []
        for trait in self.traits:
            names.append(f"trait_{trait.api_name}_count")
            names.append(f"trait_{trait.api_name}_active")
            names.append(f"trait_{trait.api_name}_tier")
        return names

    def _trait_features(
        self,
        row: Mapping[str, Any],
        *,
        _traits: Optional[Dict[str, int]] = None,
    ) -> List[float]:
        active_traits = _traits if _traits is not None else self._extract_traits(row, prefix="")
        values: List[float] = []
        for trait in self.traits:
            count = float(active_traits.get(trait.api_name, 0))
            if trait.breakpoints:
                active = 1.0 if count >= trait.breakpoints[0] else 0.0
                tier = float(sum(1 for breakpoint in trait.breakpoints if count >= breakpoint))
            else:
                active = 1.0 if count > 0 else 0.0
                tier = active
            values.extend([count, active, tier])
        return values

    def _item_feature_names(self) -> List[str]:
        return [
            "total_completed_items",
            "total_components",
            "has_qss",
            "has_guardbreaker",
            "has_blue_buff",
            "has_shojin",
            "has_morello",
            "has_ionic_spark",
            "carry_item_count",
            "carry_has_bis",
            "item_offensive_count",
            "item_defensive_count",
            "item_utility_count",
            "total_item_ad",
            "total_item_ap",
            "total_item_hp",
            "total_item_as",
            "total_item_armor",
            "total_item_mr",
        ]

    def _item_features(
        self,
        row: Mapping[str, Any],
        *,
        _units: Optional[List[Dict[str, Any]]] = None,
        _summary: Optional[Dict[str, float]] = None,
    ) -> List[float]:
        units = _units if _units is not None else self._extract_units(row, prefix="")
        summary = _summary if _summary is not None else self._team_summary(units)
        carry_has_bis = (
            1.0 if summary["carry_item_count"] >= self._numeric_config.bis_item_threshold else 0.0
        )
        return [
            summary["total_completed_items"],
            summary["total_components"],
            summary["has_qss"],
            summary["has_guardbreaker"],
            summary["has_blue_buff"],
            summary["has_shojin"],
            summary["has_morello"],
            summary["has_ionic"],
            summary["carry_item_count"],
            carry_has_bis,
            summary["item_offensive"],
            summary["item_defensive"],
            summary["item_utility"],
            summary["item_ad"],
            summary["item_ap"],
            summary["item_hp"],
            summary["item_as"],
            summary["item_armor"],
            summary["item_mr"],
        ]

    def _augment_feature_names(self) -> List[str]:
        return [
            "augment_tier_sum",
            "has_econ_augment",
            "has_combat_augment",
            "has_trait_augment",
            "augment_slot_1_id",
            "augment_slot_2_id",
            "augment_slot_3_id",
        ]

    def _augment_features(self, row: Mapping[str, Any]) -> List[float]:
        augments = self._extract_augments(row)
        tier_sum = 0.0
        has_econ = 0.0
        has_combat = 0.0
        has_trait = 0.0
        encoded = [0.0, 0.0, 0.0]
        for idx, augment in enumerate(augments):
            if not augment:
                continue
            tier_sum += float(self.augment_tiers.get(augment, 2))
            flags = self.augment_flags.get(augment, (False, True, False))
            has_econ = max(has_econ, 1.0 if flags[0] else 0.0)
            has_combat = max(has_combat, 1.0 if flags[1] else 0.0)
            has_trait = max(has_trait, 1.0 if flags[2] else 0.0)
            encoded[idx] = float(self.augment_encoding.get(augment, 0))
        return [tier_sum, has_econ, has_combat, has_trait, encoded[0], encoded[1], encoded[2]]

    def _matchup_feature_names(self) -> List[str]:
        return [
            "cost_advantage",
            "star_advantage",
            "hp_advantage",
            "item_advantage",
            "frontline_hp_ratio",
            "backline_dps_ratio",
            "armor_vs_physical",
            "mr_vs_magic",
            "has_qss_vs_cc",
            "trait_overlap",
            "carry_cost_advantage",
            "carry_star_advantage",
            "team_dps_advantage",
            "unit_count_advantage",
            "stage_hp_pressure",
        ]

    def _matchup_features(
        self,
        row: Mapping[str, Any],
        *,
        _units: Optional[List[Dict[str, Any]]] = None,
        _summary: Optional[Dict[str, float]] = None,
        _traits: Optional[Dict[str, int]] = None,
    ) -> List[float]:
        your_units = _units if _units is not None else self._extract_units(row, prefix="")
        opponent_units = self._extract_units(row, prefix="opponent_")
        your_traits = _traits if _traits is not None else self._extract_traits(row, prefix="")
        opp_traits = self._extract_traits(row, prefix="opponent_")
        your_summary = _summary if _summary is not None else self._team_summary(your_units)
        opp_summary = self._team_summary(opponent_units)

        hp_you = _safe_float(row.get("hp"))
        hp_opp = _safe_float(row.get("opponent_hp", row.get("enemy_hp")))
        round_num = _safe_float(row.get("round"))
        stage = float(int(round_num // DEFAULT_STAGE_DIVISOR) + 1)
        nc = self._numeric_config
        stage_hp_pressure = max(0.0, stage * nc.stage_hp_pressure_multiplier - hp_you)

        shared_traits = set(name for name, count in your_traits.items() if count > 0).intersection(
            set(name for name, count in opp_traits.items() if count > 0)
        )
        trait_overlap = float(len(shared_traits))

        return [
            your_summary["total_cost"] - opp_summary["total_cost"],
            your_summary["avg_star"] - opp_summary["avg_star"],
            hp_you - hp_opp,
            your_summary["total_items"] - opp_summary["total_items"],
            your_summary["frontline_hp"] / max(EPSILON, opp_summary["frontline_hp"]),
            your_summary["backline_damage"] / max(EPSILON, opp_summary["backline_damage"] + 1.0),
            your_summary["avg_armor"]
            - (opp_summary["physical_share"] * nc.share_to_percent_multiplier),
            your_summary["avg_mr"] - (opp_summary["magic_share"] * nc.share_to_percent_multiplier),
            your_summary["qss_count"] - opp_summary["cc_heavy_units"],
            trait_overlap,
            your_summary["carry_cost"] - opp_summary["carry_cost"],
            your_summary["carry_star"] - opp_summary["carry_star"],
            your_summary["team_dps"] - opp_summary["team_dps"],
            your_summary["num_units"] - opp_summary["num_units"],
            stage_hp_pressure,
        ]

    def _personal_feature_names(self) -> List[str]:
        return [
            "carry_personal_winrate",
            "carry_personal_avg_place",
            "item_personal_score",
        ]

    def _personal_features(
        self,
        row: Mapping[str, Any],
        *,
        _units: Optional[List[Dict[str, Any]]] = None,
        _summary: Optional[Dict[str, float]] = None,
    ) -> List[float]:
        nc = self._numeric_config
        units = _units if _units is not None else self._extract_units(row, prefix="")
        if not units:
            return [0.0, nc.default_avg_placement, 0.0]
        summary = _summary if _summary is not None else self._team_summary(units)
        carry_name = ""
        best_key = (-1, -1, -1)
        for unit in units:
            cost = _safe_int(self.champion_costs.get(str(unit.get("champion_id", ""))), default=0)
            star = _safe_int(unit.get("star_level"), default=1)
            item_count = len(unit.get("items", []) or [])
            key = (item_count, cost, star)
            if key > best_key:
                best_key = key
                carry_name = str(unit.get("champion_id", ""))

        carry_key = _normalize_token(carry_name.replace("TFT16_", "").replace("TFT_", ""))
        carry_stats = self.personal_carry_stats.get(carry_key, (0.0, nc.default_avg_placement))

        item_scores: List[float] = []
        for unit in units:
            for item in unit.get("items", []):
                normalized = _normalize_token(self._canonical_item_name(item))
                if normalized in self.personal_item_scores:
                    item_scores.append(self.personal_item_scores[normalized])
        item_personal_score = float(np.mean(item_scores)) if item_scores else 0.0

        return [
            float(carry_stats[0]),
            float(carry_stats[1]),
            item_personal_score + (summary["carry_item_count"] * nc.carry_item_score_weight),
        ]

    def _build_feature_names(self) -> List[str]:
        names: List[str] = []
        if self.config.use_composition:
            names.extend(self._composition_feature_names())
        if self.config.use_economy:
            names.extend(self._economy_feature_names())
        if self.config.use_traits:
            names.extend(self._trait_feature_names())
        if self.config.use_items:
            names.extend(self._item_feature_names())
        if self.config.use_augments:
            names.extend(self._augment_feature_names())
        if self.config.use_matchup:
            names.extend(self._matchup_feature_names())
        if self.config.use_personal_weights:
            names.extend(self._personal_feature_names())
        return names

    def transform(self, row: Mapping[str, Any]) -> np.ndarray:
        """Transform a single collector row into an ordered feature vector."""
        # Pre-compute shared intermediates once (avoids 3-4x redundant extraction)
        units = self._extract_units(row, prefix="")
        summary = self._team_summary(units)
        traits = self._extract_traits(row, prefix="")

        features: List[float] = []
        if self.config.use_composition:
            features.extend(
                self._composition_features(row, _units=units, _summary=summary, _traits=traits)
            )
        if self.config.use_economy:
            features.extend(self._economy_features(row))
        if self.config.use_traits:
            features.extend(self._trait_features(row, _traits=traits))
        if self.config.use_items:
            features.extend(self._item_features(row, _units=units, _summary=summary))
        if self.config.use_augments:
            features.extend(self._augment_features(row))
        if self.config.use_matchup:
            features.extend(
                self._matchup_features(row, _units=units, _summary=summary, _traits=traits)
            )
        if self.config.use_personal_weights:
            features.extend(self._personal_features(row, _units=units, _summary=summary))
        return np.asarray(features, dtype=np.float32)

    def _validate_columns(self, present: set, *, path_name: str) -> None:
        """Raise ValueError if required columns are missing.

        Called at entry to transform_batch() and transform_arrow_batch()
        after normalization, before any computation.

        Checks both strict required columns and column groups where the
        code accepts alternative names (e.g. ``streak`` vs
        ``win_streak``/``loss_streak``).
        """
        missing = sorted(REQUIRED_COLUMNS - present)
        missing_groups = []
        for group in _REQUIRED_COLUMN_GROUPS:
            if not any(name in present for name in group):
                missing_groups.append(group)
        if missing or missing_groups:
            parts = []
            if missing:
                parts.append(f"Missing required columns: {missing}")
            for group in missing_groups:
                parts.append(f"Missing column group (need at least one of {list(group)})")
            raise ValueError(
                f"Missing required columns in {path_name} input. "
                + "; ".join(parts)
                + f". Present columns: {sorted(present)}."
            )

    def transform_batch(self, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
        """Transform multiple rows, vectorizing economy/trait features."""
        n = len(rows)
        if n == 0:
            return np.zeros((0, len(self._feature_names_cache)), dtype=np.float32)

        # Validate required columns are present (after normalization).
        self._validate_columns(set(rows[0].keys()), path_name="dict")

        # Pre-compute shared intermediates once per row
        all_units = [self._extract_units(row, prefix="") for row in rows]
        all_summaries = [self._team_summary(units) for units in all_units]
        all_traits = [self._extract_traits(row, prefix="") for row in rows]

        n_features = len(self._feature_names_cache)
        result = np.empty((n, n_features), dtype=np.float32)
        col = 0

        if self.config.use_composition:
            width = len(self._composition_feature_names())
            result[:, col : col + width] = self._composition_features_batch(
                rows, all_units, all_summaries, all_traits
            )
            col += width

        if self.config.use_economy:
            width = len(self._economy_feature_names())
            result[:, col : col + width] = self._economy_features_batch(rows)
            col += width

        if self.config.use_traits:
            width = len(self._trait_feature_names())
            result[:, col : col + width] = self._trait_features_batch(all_traits)
            col += width

        if self.config.use_items:
            width = len(self._item_feature_names())
            result[:, col : col + width] = self._item_features_batch(all_summaries)
            col += width

        if self.config.use_augments:
            width = len(self._augment_feature_names())
            result[:, col : col + width] = self._augment_features_batch(rows)
            col += width

        if self.config.use_matchup:
            width = len(self._matchup_feature_names())
            result[:, col : col + width] = self._matchup_features_batch(
                rows, all_summaries, all_traits
            )
            col += width

        if self.config.use_personal_weights:
            width = len(self._personal_feature_names())
            result[:, col : col + width] = self._personal_features_batch(
                rows, all_units, all_summaries
            )
            col += width

        return result

    def _parse_units_column(self, decoded_col: List[Any]) -> List[List[Dict[str, Any]]]:
        """Parse a column of decoded unit lists into parsed unit dicts.

        Uses Cython fast path when available; otherwise inlines _parse_unit
        and _canonical_champion_id/_canonical_item_name to avoid per-call
        method dispatch overhead.
        """
        if _CYTHON_FE and _cy_parse_units_column is not None:
            return _cy_parse_units_column(
                decoded_col,
                self.champion_costs,
                self.champion_lookup,
                self.item_stats,
                self.item_lookup,
            )

        # Inlined Python fallback: avoid method dispatch per unit
        result: List[List[Dict[str, Any]]] = []
        _champ_costs = self.champion_costs
        _champ_lookup = self.champion_lookup
        _item_stats = self.item_stats
        _item_lookup = self.item_lookup

        for raw_units in decoded_col:
            if not isinstance(raw_units, list):
                result.append([])
                continue
            parsed: List[Dict[str, Any]] = []
            for raw_unit in raw_units:
                if not isinstance(raw_unit, dict):
                    continue

                champion = raw_unit.get("champion_id")
                if champion is None:
                    champion = (
                        raw_unit.get("name")
                        or raw_unit.get("champion")
                        or raw_unit.get("character_id")
                    )
                if not champion:
                    continue

                api_name = champion if isinstance(champion, str) else str(champion)
                if api_name not in _champ_costs:
                    api_name = _champ_lookup.get(_normalize_token(api_name), "")
                    if not api_name:
                        continue

                star_raw = raw_unit.get("star_level")
                if star_raw is None:
                    star_raw = raw_unit.get("star") or raw_unit.get("tier") or 1
                if isinstance(star_raw, int) and 1 <= star_raw <= 3:
                    star_level = star_raw
                else:
                    star_level = max(1, min(3, _safe_int(star_raw, 1)))

                items_raw = raw_unit.get("items") or raw_unit.get("itemNames")
                if items_raw is not None and isinstance(items_raw, str):
                    items_raw = _decode_maybe_json(items_raw)
                items: List[str] = []
                if isinstance(items_raw, list):
                    for item in items_raw[:3]:
                        item_str = item if isinstance(item, str) else str(item)
                        if item_str in _item_stats:
                            items.append(item_str)
                        else:
                            key = _normalize_token(item_str)
                            canonical = _item_lookup.get(key, item_str)
                            if canonical:
                                items.append(canonical)

                position_raw = raw_unit.get("position")
                if position_raw is None:
                    position_raw = raw_unit.get("pos")
                position: Optional[int] = None
                if isinstance(position_raw, int):
                    position = position_raw
                elif isinstance(position_raw, list) and len(position_raw) == 2:
                    position = _safe_int(position_raw[0]) * BOARD_COLS + _safe_int(position_raw[1])
                elif isinstance(position_raw, dict):
                    position = _safe_int(position_raw.get("row")) * BOARD_COLS + _safe_int(
                        position_raw.get("col")
                    )
                elif position_raw is not None:
                    position = _safe_int(position_raw)

                parsed.append(
                    {
                        "champion_id": api_name,
                        "star_level": star_level,
                        "items": items,
                        "position": position,
                    }
                )
            result.append(parsed)
        return result

    def _parse_traits_column(self, decoded_col: List[Any]) -> List[Dict[str, int]]:
        """Parse a column of decoded trait dicts into canonical trait counts."""
        result: List[Dict[str, int]] = []
        _api_names = self._trait_api_names
        for raw_traits in decoded_col:
            traits: Dict[str, int] = {}
            if isinstance(raw_traits, dict):
                for k, v in raw_traits.items():
                    if k in _api_names:
                        traits[k] = _safe_int(v, 0)
                    else:
                        api = self._canonical_trait_api(k)
                        if api:
                            traits[api] = _safe_int(v, 0)
            result.append(traits)
        return result

    def _augment_features_from_decoded(self, augments_decoded: List[Any]) -> np.ndarray:
        """Compute augment features from pre-decoded augment lists (Arrow path)."""
        n = len(augments_decoded)
        result = np.empty((n, 7), dtype=np.float32)
        _encoding = self.augment_encoding
        _tiers = self.augment_tiers
        _flags_map = self.augment_flags
        _lookup = self.augment_lookup

        for i in range(n):
            raw = augments_decoded[i]
            augments: List[str] = []
            if isinstance(raw, list):
                for aug in raw[:3]:
                    api_name = str(aug)
                    if api_name in _encoding:
                        augments.append(api_name)
                    else:
                        key = _normalize_token(api_name)
                        augments.append(_lookup.get(key, api_name))
            while len(augments) < 3:
                augments.append("")

            tier_sum = 0.0
            has_econ = 0.0
            has_combat = 0.0
            has_trait = 0.0
            encoded_0 = 0.0
            encoded_1 = 0.0
            encoded_2 = 0.0
            for idx, aug in enumerate(augments):
                if not aug:
                    continue
                tier_sum += float(_tiers.get(aug, 2))
                flags = _flags_map.get(aug, (False, True, False))
                if flags[0]:
                    has_econ = 1.0
                if flags[1]:
                    has_combat = 1.0
                if flags[2]:
                    has_trait = 1.0
                enc = float(_encoding.get(aug, 0))
                if idx == 0:
                    encoded_0 = enc
                elif idx == 1:
                    encoded_1 = enc
                else:
                    encoded_2 = enc
            result[i, 0] = tier_sum
            result[i, 1] = has_econ
            result[i, 2] = has_combat
            result[i, 3] = has_trait
            result[i, 4] = encoded_0
            result[i, 5] = encoded_1
            result[i, 6] = encoded_2
        return result

    def transform_arrow_batch(self, batch: Any) -> np.ndarray:
        """Transform an Arrow RecordBatch without full to_pylist().

        Decodes JSON columns individually and extracts scalar columns to numpy,
        skipping Python dict creation for scalar columns entirely.  Economy
        features are computed as pure numpy ops with zero dict access.
        """
        n = batch.num_rows
        if n == 0:
            return np.zeros((0, len(self._feature_names_cache)), dtype=np.float32)

        schema_names = set(batch.schema.names)

        # Validate required columns are present (after normalization).
        self._validate_columns(schema_names, path_name="Arrow")

        def _col_np(name: str, default: float = 0.0) -> np.ndarray:
            if name in schema_names:
                return batch.column(name).to_numpy(zero_copy_only=False).astype(np.float32)
            return np.full(n, default, dtype=np.float32)

        def _col_decoded(name: str) -> List[Any]:
            if name not in schema_names:
                return [None] * n
            return [_decode_maybe_json(v) for v in batch.column(name).to_pylist()]

        # -- Scalar columns → numpy (no Python dict creation) --
        level_arr = _col_np("level")
        hp_arr = _col_np("hp")
        gold_arr = _col_np("gold")
        round_arr = _col_np("round")
        streak_arr = _col_np("streak")
        opp_hp_arr = _col_np("opponent_hp")

        # -- JSON columns → per-column decoded Python lists --
        units_decoded = _col_decoded("units")
        traits_decoded = _col_decoded("traits")
        augments_decoded = _col_decoded("augments")

        # -- Pre-parse units, traits, summaries --
        all_units = self._parse_units_column(units_decoded)
        all_traits = self._parse_traits_column(traits_decoded)
        all_summaries = [self._team_summary(u) for u in all_units]

        # -- Build result matrix --
        n_features = len(self._feature_names_cache)
        result = np.empty((n, n_features), dtype=np.float32)
        col = 0

        if self.config.use_composition:
            width = len(self._composition_feature_names())
            result[:, col : col + width] = self._composition_features_batch(
                all_summaries, all_units, all_summaries, all_traits
            )
            col += width

        if self.config.use_economy:
            width = len(self._economy_feature_names())
            nc = self._numeric_config
            stages = np.floor(round_arr / DEFAULT_STAGE_DIVISOR).astype(np.float32) + 1.0
            interests = np.minimum(
                nc.max_interest, np.maximum(0.0, np.floor(gold_arr / nc.interest_gold_divisor))
            )
            result[:, col] = level_arr
            result[:, col + 1] = hp_arr
            result[:, col + 2] = hp_arr / nc.hp_divisor
            result[:, col + 3] = gold_arr
            result[:, col + 4] = streak_arr
            result[:, col + 5] = round_arr
            result[:, col + 6] = stages
            result[:, col + 7] = interests
            col += width

        if self.config.use_traits:
            width = len(self._trait_feature_names())
            result[:, col : col + width] = self._trait_features_batch(all_traits)
            col += width

        if self.config.use_items:
            width = len(self._item_feature_names())
            result[:, col : col + width] = self._item_features_batch(all_summaries)
            col += width

        if self.config.use_augments:
            width = len(self._augment_feature_names())
            result[:, col : col + width] = self._augment_features_from_decoded(augments_decoded)
            col += width

        if self.config.use_matchup:
            width = len(self._matchup_feature_names())
            opp_units_decoded = _col_decoded("opponent_units")
            opp_traits_decoded = _col_decoded("opponent_traits")
            all_opp_units = self._parse_units_column(opp_units_decoded)
            all_opp_traits = self._parse_traits_column(opp_traits_decoded)
            all_opp_summaries = [self._team_summary(u) for u in all_opp_units]
            result[:, col : col + width] = self._matchup_features_batch(
                [],
                all_summaries,
                all_traits,
                all_opp_summaries=all_opp_summaries,
                all_opp_traits=all_opp_traits,
                hp_arr=hp_arr,
                opp_hp_arr=opp_hp_arr,
                round_arr=round_arr,
            )
            col += width

        if self.config.use_personal_weights:
            width = len(self._personal_feature_names())
            result[:, col : col + width] = self._personal_features_batch(
                all_summaries, all_units, all_summaries
            )
            col += width

        return result

    def _economy_features_batch(self, rows: Sequence[Mapping[str, Any]]) -> np.ndarray:
        """Vectorized economy features for a batch of rows."""
        n = len(rows)
        levels = np.empty(n, dtype=np.float32)
        hps = np.empty(n, dtype=np.float32)
        golds = np.empty(n, dtype=np.float32)
        round_nums = np.empty(n, dtype=np.float32)
        streaks = np.empty(n, dtype=np.float32)

        for i, row in enumerate(rows):
            levels[i] = _safe_float(row.get("level"))
            hps[i] = _safe_float(row.get("hp"))
            golds[i] = _safe_float(row.get("gold"))
            round_nums[i] = _safe_float(row.get("round"))
            streak = _safe_float(row.get("streak"))
            if streak == 0.0:
                streak = _safe_float(row.get("win_streak")) - _safe_float(row.get("loss_streak"))
            streaks[i] = streak

        nc = self._numeric_config
        stages = np.floor(round_nums / DEFAULT_STAGE_DIVISOR).astype(np.float32) + 1.0
        interests = np.minimum(
            nc.max_interest, np.maximum(0.0, np.floor(golds / nc.interest_gold_divisor))
        )
        hp_pcts = hps / nc.hp_divisor

        return np.column_stack(
            [levels, hps, hp_pcts, golds, streaks, round_nums, stages, interests]
        )

    def _trait_features_batch(self, all_traits: Sequence[Dict[str, int]]) -> np.ndarray:
        """Vectorized trait features for a batch of pre-extracted trait dicts."""
        n = len(all_traits)
        n_traits = len(self.traits)

        counts = np.zeros((n, n_traits), dtype=np.float32)
        for i, active_traits in enumerate(all_traits):
            for j, trait in enumerate(self.traits):
                count = active_traits.get(trait.api_name, 0)
                if count:
                    counts[i, j] = float(count)

        actives = np.zeros((n, n_traits), dtype=np.float32)
        tiers = np.zeros((n, n_traits), dtype=np.float32)
        for j, trait in enumerate(self.traits):
            col = counts[:, j]
            if trait.breakpoints:
                actives[:, j] = (col >= trait.breakpoints[0]).astype(np.float32)
                for bp in trait.breakpoints:
                    tiers[:, j] += (col >= bp).astype(np.float32)
            else:
                actives[:, j] = (col > 0).astype(np.float32)
                tiers[:, j] = actives[:, j]

        # Interleave: [count_0, active_0, tier_0, count_1, active_1, tier_1, ...]
        result = np.empty((n, n_traits * 3), dtype=np.float32)
        result[:, 0::3] = counts
        result[:, 1::3] = actives
        result[:, 2::3] = tiers
        return result

    def _composition_features_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
        all_units: List[List[Dict[str, Any]]],
        all_summaries: List[Dict[str, float]],
        all_traits: List[Dict[str, int]],
    ) -> np.ndarray:
        """Vectorized composition features for a batch."""
        n = len(rows)
        result = np.empty((n, 21), dtype=np.float32)
        for i in range(n):
            s = all_summaries[i]
            trait_active_count = float(sum(1 for v in all_traits[i].values() if v > 0))
            total_ap_pool = s["item_ap"] + (
                trait_active_count * self._numeric_config.trait_ap_proxy_per_trait
            )
            result[i, 0] = s["total_cost"]
            result[i, 1] = s["avg_star"]
            result[i, 2] = s["num_3_stars"]
            result[i, 3] = s["num_units"]
            result[i, 4] = s["num_cost_1"]
            result[i, 5] = s["num_cost_2"]
            result[i, 6] = s["num_cost_3"]
            result[i, 7] = s["num_cost_4"]
            result[i, 8] = s["num_cost_5"]
            result[i, 9] = s["num_cost_7"]
            result[i, 10] = s["total_hp_pool"]
            result[i, 11] = s["total_ad_pool"]
            result[i, 12] = total_ap_pool
            result[i, 13] = s["avg_attack_speed"]
            result[i, 14] = s["avg_armor"]
            result[i, 15] = s["avg_mr"]
            result[i, 16] = s["team_dps"]
            result[i, 17] = s["frontline_hp"]
            result[i, 18] = s["backline_damage"]
            result[i, 19] = s["carry_cost"]
            result[i, 20] = s["carry_star"]
        return result

    def _item_features_batch(
        self,
        all_summaries: List[Dict[str, float]],
    ) -> np.ndarray:
        """Vectorized item features for a batch (flags pre-computed in summary)."""
        n = len(all_summaries)
        result = np.empty((n, 19), dtype=np.float32)
        for i in range(n):
            s = all_summaries[i]
            result[i, 0] = s["total_completed_items"]
            result[i, 1] = s["total_components"]
            result[i, 2] = s["has_qss"]
            result[i, 3] = s["has_guardbreaker"]
            result[i, 4] = s["has_blue_buff"]
            result[i, 5] = s["has_shojin"]
            result[i, 6] = s["has_morello"]
            result[i, 7] = s["has_ionic"]
            result[i, 8] = s["carry_item_count"]
            result[i, 9] = (
                1.0 if s["carry_item_count"] >= self._numeric_config.bis_item_threshold else 0.0
            )
            result[i, 10] = s["item_offensive"]
            result[i, 11] = s["item_defensive"]
            result[i, 12] = s["item_utility"]
            result[i, 13] = s["item_ad"]
            result[i, 14] = s["item_ap"]
            result[i, 15] = s["item_hp"]
            result[i, 16] = s["item_as"]
            result[i, 17] = s["item_armor"]
            result[i, 18] = s["item_mr"]
        return result

    def _augment_features_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
    ) -> np.ndarray:
        """Vectorized augment features for a batch."""
        n = len(rows)
        result = np.empty((n, 7), dtype=np.float32)
        for i in range(n):
            augments = self._extract_augments(rows[i])
            tier_sum = 0.0
            has_econ = 0.0
            has_combat = 0.0
            has_trait = 0.0
            encoded_0 = 0.0
            encoded_1 = 0.0
            encoded_2 = 0.0
            for idx, augment in enumerate(augments):
                if not augment:
                    continue
                tier_sum += float(self.augment_tiers.get(augment, 2))
                flags = self.augment_flags.get(augment, (False, True, False))
                if flags[0]:
                    has_econ = 1.0
                if flags[1]:
                    has_combat = 1.0
                if flags[2]:
                    has_trait = 1.0
                enc = float(self.augment_encoding.get(augment, 0))
                if idx == 0:
                    encoded_0 = enc
                elif idx == 1:
                    encoded_1 = enc
                else:
                    encoded_2 = enc
            result[i, 0] = tier_sum
            result[i, 1] = has_econ
            result[i, 2] = has_combat
            result[i, 3] = has_trait
            result[i, 4] = encoded_0
            result[i, 5] = encoded_1
            result[i, 6] = encoded_2
        return result

    def _matchup_features_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
        all_summaries: List[Dict[str, Any]],
        all_traits: List[Dict[str, int]],
        *,
        all_opp_summaries: Optional[List[Dict[str, Any]]] = None,
        all_opp_traits: Optional[List[Dict[str, int]]] = None,
        hp_arr: Optional[np.ndarray] = None,
        opp_hp_arr: Optional[np.ndarray] = None,
        round_arr: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Vectorized matchup features for a batch.

        When pre-computed opponent data and numpy scalar arrays are provided
        (Arrow path), skips per-row extraction and dict access entirely.
        """
        n = len(all_summaries)
        result = np.empty((n, 15), dtype=np.float32)
        for i in range(n):
            if all_opp_summaries is not None:
                opp_summary = all_opp_summaries[i]
                opp_traits_i = all_opp_traits[i] if all_opp_traits is not None else {}
            else:
                row = rows[i]
                opp_units = self._extract_units(row, prefix="opponent_")
                opp_traits_i = self._extract_traits(row, prefix="opponent_")
                opp_summary = self._team_summary(opp_units)
            your = all_summaries[i]

            if hp_arr is not None:
                hp_you = float(hp_arr[i])
                hp_opp = float(opp_hp_arr[i]) if opp_hp_arr is not None else 0.0
                round_num = float(round_arr[i]) if round_arr is not None else 0.0
            else:
                row = rows[i]
                hp_you = _safe_float(row.get("hp"))
                hp_opp = _safe_float(row.get("opponent_hp", row.get("enemy_hp")))
                round_num = _safe_float(row.get("round"))
            stage = float(int(round_num // DEFAULT_STAGE_DIVISOR) + 1)

            your_active = set(name for name, count in all_traits[i].items() if count > 0)
            opp_active = set(name for name, count in opp_traits_i.items() if count > 0)
            trait_overlap = float(len(your_active & opp_active))

            result[i, 0] = your["total_cost"] - opp_summary["total_cost"]
            result[i, 1] = your["avg_star"] - opp_summary["avg_star"]
            result[i, 2] = hp_you - hp_opp
            result[i, 3] = your["total_items"] - opp_summary["total_items"]
            result[i, 4] = your["frontline_hp"] / max(EPSILON, opp_summary["frontline_hp"])
            result[i, 5] = your["backline_damage"] / max(
                EPSILON, opp_summary["backline_damage"] + 1.0
            )
            nc = self._numeric_config
            result[i, 6] = your["avg_armor"] - (
                opp_summary["physical_share"] * nc.share_to_percent_multiplier
            )
            result[i, 7] = your["avg_mr"] - (
                opp_summary["magic_share"] * nc.share_to_percent_multiplier
            )
            result[i, 8] = your["qss_count"] - opp_summary["cc_heavy_units"]
            result[i, 9] = trait_overlap
            result[i, 10] = your["carry_cost"] - opp_summary["carry_cost"]
            result[i, 11] = your["carry_star"] - opp_summary["carry_star"]
            result[i, 12] = your["team_dps"] - opp_summary["team_dps"]
            result[i, 13] = your["num_units"] - opp_summary["num_units"]
            result[i, 14] = max(0.0, stage * nc.stage_hp_pressure_multiplier - hp_you)
        return result

    def _personal_features_batch(
        self,
        rows: Sequence[Mapping[str, Any]],
        all_units: List[List[Dict[str, Any]]],
        all_summaries: List[Dict[str, Any]],
    ) -> np.ndarray:
        """Vectorized personal features for a batch."""
        n = len(rows)
        result = np.empty((n, 3), dtype=np.float32)
        _personal_carry = self.personal_carry_stats
        _item_personal = self._item_personal_by_canonical
        _canonical_item = self._canonical_item_name

        for i in range(n):
            units = all_units[i]
            summary = all_summaries[i]
            if not units:
                result[i, 0] = 0.0
                result[i, 1] = self._numeric_config.default_avg_placement
                result[i, 2] = 0.0
                continue

            carry_name = summary.get("carry_api_name", "")
            if not carry_name:
                # Fallback for Cython path that may not return carry_api_name
                best_key = (-1, -1, -1)
                for unit in units:
                    packed = self._champion_packed.get(unit.get("champion_id", ""))
                    if packed is None:
                        continue
                    star = unit.get("star_level", 1)
                    item_count = len(unit.get("items") or ())
                    key = (item_count, int(packed[0]), star if isinstance(star, int) else 1)
                    if key > best_key:
                        best_key = key
                        carry_name = unit.get("champion_id", "")

            carry_key = _normalize_token(carry_name.replace("TFT16_", "").replace("TFT_", ""))
            carry_stats = _personal_carry.get(
                carry_key, (0.0, self._numeric_config.default_avg_placement)
            )

            item_score_sum = 0.0
            item_score_count = 0
            for unit in units:
                for item in unit.get("items") or ():
                    canonical = _canonical_item(item)
                    score = _item_personal.get(canonical)
                    if score is not None:
                        item_score_sum += score
                        item_score_count += 1
            item_personal_score = item_score_sum / item_score_count if item_score_count else 0.0

            result[i, 0] = float(carry_stats[0])
            result[i, 1] = float(carry_stats[1])
            result[i, 2] = item_personal_score + (
                summary["carry_item_count"] * self._numeric_config.carry_item_score_weight
            )
        return result

    def feature_names(self) -> List[str]:
        """Return ordered feature names matching :meth:`transform` output."""
        return list(self._feature_names_cache)
