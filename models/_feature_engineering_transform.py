"""Feature engineering transform mixin: single-row feature extraction methods."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from ._feature_engineering_config import (
    ATTACK_SPEED_CAP,
    BOARD_COLS,
    DEFAULT_STAGE_DIVISOR,
    EPSILON,
    STAR_SCALING_AD,
    STAR_SCALING_HP,
    _decode_maybe_json,
    _normalize_token,
    _safe_float,
    _safe_int,
)

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


class _TransformMixin:
    """Mixin providing single-row transform methods for TFTFeatureEngineer."""

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
