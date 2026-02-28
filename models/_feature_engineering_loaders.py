"""Feature engineering loader mixin: reference data loading methods."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from ._feature_engineering_config import (
    _CC_HEAVY_NAME_KEYS,
    _COMBAT_AUGMENT_KEYWORDS,
    _ECON_AUGMENT_KEYWORDS,
    _TRAIT_AUGMENT_KEYWORDS,
    TraitMetadata,
    _normalize_token,
    _safe_float,
    _safe_int,
)

_log = logging.getLogger(__name__)


class _LoaderMixin:
    """Mixin providing reference data loading for TFTFeatureEngineer."""

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

        # Packed champion data: api_name -> (cost, hp, ad, as, armor, mr, is_cc_heavy)
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

        # Packed item data: canonical -> (ad, ap, hp, as, armor, mr, type_code, is_component, flag_bits)
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

        # Pre-computed personal item scores: canonical_item_name -> score
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
