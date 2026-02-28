"""Feature engineering batch mixin: batch and Arrow transform methods."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from ._feature_engineering_config import (
    _REQUIRED_COLUMN_GROUPS,
    BOARD_COLS,
    DEFAULT_STAGE_DIVISOR,
    EPSILON,
    REQUIRED_COLUMNS,
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
except (ImportError, OSError):
    _cy_parse_units_column = None
    _CYTHON_FE = False


class _BatchTransformMixin:
    """Mixin providing batch transform methods for TFTFeatureEngineer."""

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

        # -- Scalar columns -> numpy (no Python dict creation) --
        level_arr = _col_np("level")
        hp_arr = _col_np("hp")
        gold_arr = _col_np("gold")
        round_arr = _col_np("round")
        streak_arr = _col_np("streak")
        opp_hp_arr = _col_np("opponent_hp")

        # -- JSON columns -> per-column decoded Python lists --
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
