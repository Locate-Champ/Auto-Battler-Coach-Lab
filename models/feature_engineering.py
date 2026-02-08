"""Feature engineering for TFT board states."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

EPSILON = 1e-6
STAR_SCALING_HP = {1: 1.0, 2: 1.8, 3: 3.24}
STAR_SCALING_AD = {1: 1.0, 2: 1.5, 3: 2.25}
ATTACK_SPEED_CAP = 5.0
BOARD_COLS = 7
DEFAULT_STAGE_DIVISOR = 7

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
    ) -> None:
        self.config = config or FeatureConfig()
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

        self.augment_tiers: Dict[str, int] = {}
        self.augment_flags: Dict[str, Tuple[bool, bool, bool]] = {}
        self.augment_lookup: Dict[str, str] = {}
        self.augment_encoding: Dict[str, int] = {}

        self.personal_carry_stats: Dict[str, Tuple[float, float]] = {}
        self.personal_item_scores: Dict[str, float] = {}

        self._load_reference_data()
        self._feature_names_cache = self._build_feature_names()

    def _load_reference_data(self) -> None:
        self._load_champions()
        self._load_traits()
        self._load_items()
        self._load_augments()
        self._load_personal_reference()

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

    def _normalize_item_effects(self, effects: Mapping[str, Any]) -> Dict[str, float]:
        def pick(keys: Sequence[str]) -> float:
            for key in keys:
                if key in effects:
                    value = _safe_float(effects.get(key))
                    # Riot data mixes absolute and percentage attack speed values.
                    if key in {"AS", "AttackSpeed"} and value > 1.0:
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
        offensive_signal = stats["ad"] + stats["ap"] + stats["attack_speed"] * 50.0
        defensive_signal = stats["hp"] / 100.0 + stats["armor"] / 20.0 + stats["magic_resist"] / 20.0
        if "damage" in desc_key or "execute" in desc_key or offensive_signal >= defensive_signal + 0.2:
            return "offensive"
        if "shield" in desc_key or "heal" in desc_key or defensive_signal >= offensive_signal + 0.2:
            return "defensive"
        # Utility catches emblems, economy, and hybrid items.
        if any(token in desc_key for token in ("mana", "sunder", "shred", "gold", "stun")):
            return "utility"
        if "artifact" in item_name.lower():
            return "utility"
        return "offensive" if offensive_signal >= defensive_signal else "defensive"

    def _load_items(self) -> None:
        api_items = self._load_json(self.repo_root / "data" / "api" / "processed" / "items_set16.json", [])
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
            self.item_types[api_name] = self._classify_item_type(display_name, tags, stats, description)

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
        except Exception:
            # Keep running even when simulator package import fails.
            pass

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
        has_trait = bool(associated_traits) or any(keyword in text for keyword in _TRAIT_AUGMENT_KEYWORDS)
        has_econ = any(keyword in text for keyword in _ECON_AUGMENT_KEYWORDS)
        has_combat = any(keyword in text for keyword in _COMBAT_AUGMENT_KEYWORDS) or not has_econ
        return has_econ, has_combat, has_trait

    def _load_augments(self) -> None:
        path = self.repo_root / "data" / "api" / "processed" / "augments_set16.json"
        augments = self._load_json(path, [])
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
                    avg_place = _safe_float(carry.get("avgPlace", carry.get("avg_placement")), default=4.5)
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
                    avg_place = _safe_float(item.get("avgPlace", item.get("avg_placement")), default=4.5)
                    score = top4 + ((4.5 - avg_place) / 8.0)
                    key = _normalize_token(name)
                    if key:
                        self.personal_item_scores[key] = score

        # CSV fallback from personal exports.
        carry_csv = self.repo_root / "data" / "personal" / "carry_performance_corrected.csv"
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
                    avg_place = _safe_float(parts[row_map["avg_placement"]], default=4.5)
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
        for trait in self.traits:
            if text == trait.api_name:
                return trait.api_name
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
        if isinstance(raw, Mapping):
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
        if not isinstance(raw_unit, Mapping):
            return None
        champion = (
            raw_unit.get("champion_id")
            or raw_unit.get("name")
            or raw_unit.get("champion")
            or raw_unit.get("character_id")
        )
        api_name = self._canonical_champion_id(champion)
        if not api_name:
            return None

        star_level = max(1, min(3, _safe_int(raw_unit.get("star_level", raw_unit.get("star", raw_unit.get("tier"))), 1)))
        items_raw = _decode_maybe_json(raw_unit.get("items", raw_unit.get("itemNames", [])))
        items: List[str] = []
        if isinstance(items_raw, list):
            for item in items_raw[:3]:
                canonical = self._canonical_item_name(item)
                if canonical:
                    items.append(canonical)

        position_raw = raw_unit.get("position", raw_unit.get("pos"))
        position: Optional[int]
        if isinstance(position_raw, list) and len(position_raw) == 2:
            position = _safe_int(position_raw[0]) * BOARD_COLS + _safe_int(position_raw[1])
        elif isinstance(position_raw, Mapping):
            position = _safe_int(position_raw.get("row")) * BOARD_COLS + _safe_int(position_raw.get("col"))
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

    def _team_summary(self, units: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
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
            }

        costs: List[float] = []
        stars: List[float] = []
        hp_pool = 0.0
        ad_pool = 0.0
        attack_speeds: List[float] = []
        armors: List[float] = []
        mrs: List[float] = []
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

        best_carry_key = (-1, -1, -1)
        carry_cost = 0.0
        carry_star = 0.0
        carry_item_count = 0.0

        for unit in units:
            api_name = str(unit.get("champion_id", ""))
            stats = self.champion_stats.get(api_name, {})
            cost = float(self.champion_costs.get(api_name, 0))
            star = float(max(1, min(3, _safe_int(unit.get("star_level"), default=1))))
            hp_scale = STAR_SCALING_HP.get(int(star), 1.0)
            ad_scale = STAR_SCALING_AD.get(int(star), 1.0)

            base_hp = stats.get("hp", 0.0)
            base_ad = stats.get("ad", 0.0)
            base_as = stats.get("attack_speed", 0.7)
            base_armor = stats.get("armor", 0.0)
            base_mr = stats.get("mr", 0.0)

            costs.append(cost)
            stars.append(star)

            scaled_hp = base_hp * hp_scale
            scaled_ad = base_ad * ad_scale
            hp_pool += scaled_hp
            ad_pool += scaled_ad

            unit_items = unit.get("items", []) or []
            item_count = len(unit_items)
            total_items += item_count

            bonus_ad = 0.0
            bonus_ap = 0.0
            bonus_hp = 0.0
            bonus_as = 0.0
            bonus_armor = 0.0
            bonus_mr = 0.0

            for raw_item in unit_items:
                canonical_item = self._canonical_item_name(raw_item)
                stats_by_item = self.item_stats.get(canonical_item, {})
                bonus_ad += stats_by_item.get("ad", 0.0)
                bonus_ap += stats_by_item.get("ap", 0.0)
                bonus_hp += stats_by_item.get("hp", 0.0)
                bonus_as += stats_by_item.get("attack_speed", 0.0)
                bonus_armor += stats_by_item.get("armor", 0.0)
                bonus_mr += stats_by_item.get("magic_resist", 0.0)

                item_ad += stats_by_item.get("ad", 0.0)
                item_ap += stats_by_item.get("ap", 0.0)
                item_hp += stats_by_item.get("hp", 0.0)
                item_as += stats_by_item.get("attack_speed", 0.0)
                item_armor += stats_by_item.get("armor", 0.0)
                item_mr += stats_by_item.get("magic_resist", 0.0)

                if canonical_item in self.component_items:
                    components += 1.0
                else:
                    completed_items += 1.0

                item_type = self.item_types.get(canonical_item, "utility")
                if item_type == "offensive":
                    item_offensive += 1.0
                elif item_type == "defensive":
                    item_defensive += 1.0
                else:
                    item_utility += 1.0

                item_key = _normalize_token(canonical_item)
                if "quicksilver" in item_key or item_key == "qss":
                    qss_count += 1.0

            effective_as = min(ATTACK_SPEED_CAP, base_as * (1.0 + max(0.0, bonus_as)))
            effective_armor = base_armor + bonus_armor
            effective_mr = base_mr + bonus_mr
            effective_ad = scaled_ad * (1.0 + max(0.0, bonus_ad))
            effective_hp = scaled_hp + bonus_hp

            attack_speeds.append(effective_as)
            armors.append(effective_armor)
            mrs.append(effective_mr)
            team_dps += effective_ad * effective_as

            row_index = self._position_row(unit.get("position"))  # type: ignore[arg-type]
            if row_index is None:
                row_index = 1 if len(costs) <= math.ceil(len(units) / 2) else 2
            if row_index <= 1:
                frontline_hp += effective_hp
            else:
                backline_damage += effective_ad + bonus_ap

            carry_key = (item_count, int(cost), int(star))
            if carry_key > best_carry_key:
                best_carry_key = carry_key
                carry_cost = cost
                carry_star = star
                carry_item_count = float(item_count)

            unit_key = _normalize_token(api_name)
            if any(cc in unit_key for cc in _CC_HEAVY_NAME_KEYS):
                cc_heavy_units += 1.0

        total_magic_proxy = item_ap + 1.0
        total_physical_proxy = ad_pool + team_dps * 0.01 + 1.0
        physical_share = total_physical_proxy / (total_physical_proxy + total_magic_proxy)
        magic_share = 1.0 - physical_share

        counts_by_cost = {cost: costs.count(float(cost)) for cost in (1, 2, 3, 4, 5, 7)}
        return {
            "num_units": float(len(units)),
            "total_cost": float(sum(costs)),
            "avg_star": float(np.mean(stars)) if stars else 0.0,
            "num_3_stars": float(sum(1.0 for star in stars if star >= 3.0)),
            "num_cost_1": float(counts_by_cost[1]),
            "num_cost_2": float(counts_by_cost[2]),
            "num_cost_3": float(counts_by_cost[3]),
            "num_cost_4": float(counts_by_cost[4]),
            "num_cost_5": float(counts_by_cost[5]),
            "num_cost_7": float(counts_by_cost[7]),
            "total_hp_pool": float(hp_pool),
            "total_ad_pool": float(ad_pool),
            "avg_attack_speed": float(np.mean(attack_speeds)) if attack_speeds else 0.0,
            "avg_armor": float(np.mean(armors)) if armors else 0.0,
            "avg_mr": float(np.mean(mrs)) if mrs else 0.0,
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

    def _composition_features(self, row: Mapping[str, Any]) -> List[float]:
        units = self._extract_units(row, prefix="")
        traits = self._extract_traits(row, prefix="")
        summary = self._team_summary(units)
        trait_active_count = float(sum(1 for value in traits.values() if value > 0))
        total_ap_pool = summary["item_ap"] + (trait_active_count * 5.0)
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
        interest = min(5.0, max(0.0, math.floor(gold / 10.0)))
        return [
            level,
            hp,
            hp / 100.0,
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

    def _trait_features(self, row: Mapping[str, Any]) -> List[float]:
        active_traits = self._extract_traits(row, prefix="")
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

    def _item_features(self, row: Mapping[str, Any]) -> List[float]:
        units = self._extract_units(row, prefix="")
        summary = self._team_summary(units)
        normalized_items = [
            _normalize_token(self._canonical_item_name(item))
            for unit in units
            for item in unit.get("items", [])
        ]
        has_qss = 1.0 if any("quicksilver" in item or item == "qss" for item in normalized_items) else 0.0
        has_guardbreaker = 1.0 if any("guardbreaker" in item for item in normalized_items) else 0.0
        has_blue_buff = 1.0 if any("bluebuff" in item for item in normalized_items) else 0.0
        has_shojin = 1.0 if any("spearofshojin" in item or "shojin" in item for item in normalized_items) else 0.0
        has_morello = 1.0 if any("morello" in item for item in normalized_items) else 0.0
        has_ionic = 1.0 if any("ionicspark" in item for item in normalized_items) else 0.0
        carry_has_bis = 1.0 if summary["carry_item_count"] >= 3.0 else 0.0
        return [
            summary["total_completed_items"],
            summary["total_components"],
            has_qss,
            has_guardbreaker,
            has_blue_buff,
            has_shojin,
            has_morello,
            has_ionic,
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

    def _matchup_features(self, row: Mapping[str, Any]) -> List[float]:
        your_units = self._extract_units(row, prefix="")
        opponent_units = self._extract_units(row, prefix="opponent_")
        your_traits = self._extract_traits(row, prefix="")
        opp_traits = self._extract_traits(row, prefix="opponent_")
        your_summary = self._team_summary(your_units)
        opp_summary = self._team_summary(opponent_units)

        hp_you = _safe_float(row.get("hp"))
        hp_opp = _safe_float(row.get("opponent_hp", row.get("enemy_hp")))
        round_num = _safe_float(row.get("round"))
        stage = float(int(round_num // DEFAULT_STAGE_DIVISOR) + 1)
        stage_hp_pressure = max(0.0, stage * 10.0 - hp_you)

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
            your_summary["avg_armor"] - (opp_summary["physical_share"] * 100.0),
            your_summary["avg_mr"] - (opp_summary["magic_share"] * 100.0),
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

    def _personal_features(self, row: Mapping[str, Any]) -> List[float]:
        units = self._extract_units(row, prefix="")
        if not units:
            return [0.0, 4.5, 0.0]
        summary = self._team_summary(units)
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
        carry_stats = self.personal_carry_stats.get(carry_key, (0.0, 4.5))

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
            item_personal_score + (summary["carry_item_count"] * 0.01),
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
        features: List[float] = []
        if self.config.use_composition:
            features.extend(self._composition_features(row))
        if self.config.use_economy:
            features.extend(self._economy_features(row))
        if self.config.use_traits:
            features.extend(self._trait_features(row))
        if self.config.use_items:
            features.extend(self._item_features(row))
        if self.config.use_augments:
            features.extend(self._augment_features(row))
        if self.config.use_matchup:
            features.extend(self._matchup_features(row))
        if self.config.use_personal_weights:
            features.extend(self._personal_features(row))
        return np.asarray(features, dtype=np.float32)

    def feature_names(self) -> List[str]:
        """Return ordered feature names matching :meth:`transform` output."""
        return list(self._feature_names_cache)
