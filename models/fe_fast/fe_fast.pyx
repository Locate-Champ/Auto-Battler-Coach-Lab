# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
Cython-accelerated feature engineering helpers for TFT.

Provides drop-in replacements for hot paths in TFTFeatureEngineer:
- team_summary_fast()          -> _team_summary()
- parse_units_column_fast()    -> _parse_units_column()

Build:
    cd models/fe_fast && python setup.py build_ext --inplace
"""

# Star scaling constants (index 0 unused, 1-3 for star levels)
cdef double[4] _STAR_HP = [0.0, 1.0, 1.8, 3.24]
cdef double[4] _STAR_AD = [0.0, 1.0, 1.5, 2.25]
cdef double _AS_CAP = 5.0
cdef int _BOARD_COLS = 7


cdef inline str _normalize_token_cy(str text):
    """Fast normalize_token without regex: lowercase, strip non-alnum, & -> and."""
    cdef str lower = text.strip().lower().replace("&", "and")
    cdef Py_ssize_t i, n = len(lower)
    cdef list out = []
    cdef Py_UCS4 c
    for i in range(n):
        c = <Py_UCS4>lower[i]
        if (c >= 97 and c <= 122) or (c >= 48 and c <= 57):  # a-z, 0-9
            out.append(lower[i])
    return "".join(out)


def parse_units_column_fast(list decoded_col, dict champion_costs,
                             dict champion_lookup, dict item_stats,
                             dict item_lookup):
    """Cython-accelerated column-level unit parser.

    Replaces TFTFeatureEngineer._parse_units_column() by inlining
    _parse_unit, _canonical_champion_id, and _canonical_item_name calls
    with C-typed loops and direct dict lookups.

    Args:
        decoded_col: List of decoded JSON unit lists (one per row).
        champion_costs: Dict[str, int] for fast existence check.
        champion_lookup: Dict[str, str] normalized token -> API name.
        item_stats: Dict[str, dict] for fast existence check.
        item_lookup: Dict[str, str] normalized token -> canonical name.

    Returns:
        List of lists of unit dicts (same format as _parse_units_column).
    """
    cdef list result = []
    cdef list parsed, items
    cdef int star_int
    cdef str api_name, item_str, key

    for raw_units in decoded_col:
        if not isinstance(raw_units, list):
            result.append([])
            continue
        parsed = []
        for raw_unit in (<list>raw_units):
            if not isinstance(raw_unit, dict):
                continue

            # -- Champion ID resolution (inline _canonical_champion_id) --
            champion = (<dict>raw_unit).get("champion_id")
            if champion is None:
                champion = (<dict>raw_unit).get("name")
                if champion is None:
                    champion = (<dict>raw_unit).get("champion")
                    if champion is None:
                        champion = (<dict>raw_unit).get("character_id")
            if not champion:
                continue

            api_name = champion if isinstance(champion, str) else str(champion)
            if api_name not in champion_costs:
                key = _normalize_token_cy(api_name)
                api_name = champion_lookup.get(key, "")
                if not api_name:
                    continue

            # -- Star level (fast path: Parquet data is always int) --
            star_raw = (<dict>raw_unit).get("star_level")
            if star_raw is None:
                star_raw = (<dict>raw_unit).get("star")
                if star_raw is None:
                    star_raw = (<dict>raw_unit).get("tier")
                    if star_raw is None:
                        star_raw = 1
            if isinstance(star_raw, int):
                star_int = <int>star_raw
            else:
                try:
                    star_int = int(star_raw)
                except (TypeError, ValueError):
                    star_int = 1
            if star_int < 1:
                star_int = 1
            elif star_int > 3:
                star_int = 3

            # -- Items (inline _canonical_item_name) --
            items_raw = (<dict>raw_unit).get("items")
            if items_raw is None:
                items_raw = (<dict>raw_unit).get("itemNames")
            items = []
            if isinstance(items_raw, list):
                for raw_item in (<list>items_raw)[:3]:
                    item_str = raw_item if isinstance(raw_item, str) else str(raw_item)
                    if item_str in item_stats:
                        items.append(item_str)
                    else:
                        key = _normalize_token_cy(item_str)
                        resolved = item_lookup.get(key, item_str)
                        if resolved:
                            items.append(resolved)

            # -- Position --
            position_raw = (<dict>raw_unit).get("position")
            if position_raw is None:
                position_raw = (<dict>raw_unit).get("pos")
            position = None
            if isinstance(position_raw, int):
                position = position_raw
            elif isinstance(position_raw, list) and len(<list>position_raw) == 2:
                try:
                    position = int((<list>position_raw)[0]) * _BOARD_COLS + int((<list>position_raw)[1])
                except (TypeError, ValueError):
                    pass
            elif position_raw is not None:
                try:
                    position = int(position_raw)
                except (TypeError, ValueError):
                    pass

            parsed.append({
                "champion_id": api_name,
                "star_level": star_int,
                "items": items,
                "position": position,
            })
        result.append(parsed)
    return result


def team_summary_fast(list units, dict champion_packed, dict item_packed,
                       object canonical_item_fn, int half_count):
    """Cython-accelerated version of TFTFeatureEngineer._team_summary().

    Args:
        units: List of unit dicts with champion_id, star_level, items, position.
        champion_packed: Dict mapping API name to
            (cost, hp, ad, as, armor, mr, is_cc_heavy) tuples.
        item_packed: Dict mapping canonical item name to
            (ad, ap, hp, as, armor, mr, type_code, is_component, flag_bits) tuples.
        canonical_item_fn: The _canonical_item_name method for item name resolution.
        half_count: ceil(len(units) / 2) for position heuristic.

    Returns:
        Dict with the same keys as the Python _team_summary().
    """
    if not units:
        return {
            "num_units": 0.0, "total_cost": 0.0, "avg_star": 0.0,
            "num_3_stars": 0.0, "num_cost_1": 0.0, "num_cost_2": 0.0,
            "num_cost_3": 0.0, "num_cost_4": 0.0, "num_cost_5": 0.0,
            "num_cost_7": 0.0, "total_hp_pool": 0.0, "total_ad_pool": 0.0,
            "avg_attack_speed": 0.0, "avg_armor": 0.0, "avg_mr": 0.0,
            "team_dps": 0.0, "frontline_hp": 0.0, "backline_damage": 0.0,
            "carry_cost": 0.0, "carry_star": 0.0, "carry_item_count": 0.0,
            "total_items": 0.0, "total_completed_items": 0.0,
            "total_components": 0.0, "item_offensive": 0.0,
            "item_defensive": 0.0, "item_utility": 0.0,
            "item_ad": 0.0, "item_ap": 0.0, "item_hp": 0.0,
            "item_as": 0.0, "item_armor": 0.0, "item_mr": 0.0,
            "qss_count": 0.0, "cc_heavy_units": 0.0,
            "physical_share": 0.5, "magic_share": 0.5,
            "has_qss": 0.0, "has_guardbreaker": 0.0, "has_blue_buff": 0.0,
            "has_shojin": 0.0, "has_morello": 0.0, "has_ionic": 0.0,
            "carry_api_name": "",
        }

    # Typed accumulators
    cdef int n_units = 0
    cdef double total_cost = 0.0
    cdef double star_sum = 0.0
    cdef double num_3_stars = 0.0
    cdef double cost_1 = 0.0, cost_2 = 0.0, cost_3 = 0.0
    cdef double cost_4 = 0.0, cost_5 = 0.0, cost_7 = 0.0
    cdef double hp_pool = 0.0
    cdef double ad_pool = 0.0
    cdef double as_sum = 0.0
    cdef double armor_sum = 0.0
    cdef double mr_sum = 0.0
    cdef double team_dps = 0.0
    cdef double frontline_hp = 0.0
    cdef double backline_damage = 0.0
    cdef double total_items = 0.0
    cdef double completed_items = 0.0
    cdef double components = 0.0
    cdef double item_offensive = 0.0
    cdef double item_defensive = 0.0
    cdef double item_utility = 0.0
    cdef double item_ad = 0.0
    cdef double item_ap = 0.0
    cdef double item_hp = 0.0
    cdef double item_as = 0.0
    cdef double item_armor = 0.0
    cdef double item_mr = 0.0
    cdef double qss_count = 0.0
    cdef double cc_heavy_units = 0.0
    cdef double has_qss = 0.0
    cdef double has_guardbreaker = 0.0
    cdef double has_blue_buff = 0.0
    cdef double has_shojin = 0.0
    cdef double has_morello = 0.0
    cdef double has_ionic = 0.0

    # Carry tracking
    cdef int best_carry_items = -1
    cdef int best_carry_cost = -1
    cdef int best_carry_star = -1
    cdef double carry_cost = 0.0
    cdef double carry_star = 0.0
    cdef double carry_item_count = 0.0
    carry_api_name = ""

    # Per-unit typed locals
    cdef double cost, base_hp, base_ad, base_as, base_armor, base_mr
    cdef double scaled_hp, scaled_ad, hp_scale, ad_scale, star
    cdef double bonus_ad, bonus_ap, bonus_hp, bonus_as, bonus_armor, bonus_mr
    cdef double i_ad, i_ap, i_hp, i_as, i_armor, i_mr
    cdef double effective_as, effective_armor, effective_mr, effective_ad, effective_hp
    cdef int itype, iflags, item_count, star_int, cost_int
    cdef bint is_comp, is_cc
    cdef int row_index, pos_val
    cdef double inv_n, total_magic_proxy, total_physical_proxy, physical_share, magic_share

    for unit in units:
        api_name = unit.get("champion_id", "")
        packed = champion_packed.get(api_name)
        if packed is None:
            continue
        cost = <double>packed[0]
        base_hp = <double>packed[1]
        base_ad = <double>packed[2]
        base_as = <double>packed[3]
        base_armor = <double>packed[4]
        base_mr = <double>packed[5]
        is_cc = <bint>packed[6]

        star_raw = unit.get("star_level", 1)
        if isinstance(star_raw, int):
            star_int = <int>star_raw
        else:
            star_int = 1
        if star_int < 1:
            star_int = 1
        elif star_int > 3:
            star_int = 3
        star = <double>star_int
        hp_scale = _STAR_HP[star_int]
        ad_scale = _STAR_AD[star_int]

        n_units += 1
        total_cost += cost
        star_sum += star
        if star_int >= 3:
            num_3_stars += 1.0

        cost_int = <int>cost
        if cost_int == 1: cost_1 += 1.0
        elif cost_int == 2: cost_2 += 1.0
        elif cost_int == 3: cost_3 += 1.0
        elif cost_int == 4: cost_4 += 1.0
        elif cost_int == 5: cost_5 += 1.0
        elif cost_int == 7: cost_7 += 1.0

        scaled_hp = base_hp * hp_scale
        scaled_ad = base_ad * ad_scale
        hp_pool += scaled_hp
        ad_pool += scaled_ad

        unit_items = unit.get("items") or []
        item_count = <int>len(unit_items)
        total_items += <double>item_count

        bonus_ad = 0.0
        bonus_ap = 0.0
        bonus_hp = 0.0
        bonus_as = 0.0
        bonus_armor = 0.0
        bonus_mr = 0.0

        for raw_item in unit_items:
            canonical_item = canonical_item_fn(raw_item)
            ipacked = item_packed.get(canonical_item)
            if ipacked is None:
                continue
            i_ad = <double>ipacked[0]
            i_ap = <double>ipacked[1]
            i_hp = <double>ipacked[2]
            i_as = <double>ipacked[3]
            i_armor = <double>ipacked[4]
            i_mr = <double>ipacked[5]
            itype = <int>ipacked[6]
            is_comp = <bint>ipacked[7]
            iflags = <int>ipacked[8]

            bonus_ad += i_ad;   item_ad += i_ad
            bonus_ap += i_ap;   item_ap += i_ap
            bonus_hp += i_hp;   item_hp += i_hp
            bonus_as += i_as;   item_as += i_as
            bonus_armor += i_armor; item_armor += i_armor
            bonus_mr += i_mr;   item_mr += i_mr

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

        # Effective stats
        if bonus_as > 0.0:
            effective_as = base_as * (1.0 + bonus_as)
        else:
            effective_as = base_as
        if effective_as > _AS_CAP:
            effective_as = _AS_CAP
        effective_armor = base_armor + bonus_armor
        effective_mr = base_mr + bonus_mr
        if bonus_ad > 0.0:
            effective_ad = scaled_ad * (1.0 + bonus_ad)
        else:
            effective_ad = scaled_ad
        effective_hp = scaled_hp + bonus_hp

        as_sum += effective_as
        armor_sum += effective_armor
        mr_sum += effective_mr
        team_dps += effective_ad * effective_as

        # Position-based categorization
        pos = unit.get("position")
        if pos is not None and isinstance(pos, int) and pos >= 0:
            row_index = pos // _BOARD_COLS
        else:
            row_index = 1 if n_units <= half_count else 2
        if row_index <= 1:
            frontline_hp += effective_hp
        else:
            backline_damage += effective_ad + bonus_ap

        # Carry tracking (best = most items, then highest cost, then highest star)
        if item_count > best_carry_items or (
            item_count == best_carry_items and (
                cost_int > best_carry_cost or (
                    cost_int == best_carry_cost and star_int > best_carry_star
                )
            )
        ):
            best_carry_items = item_count
            best_carry_cost = cost_int
            best_carry_star = star_int
            carry_cost = cost
            carry_star = star
            carry_item_count = <double>item_count
            carry_api_name = api_name

        if is_cc:
            cc_heavy_units += 1.0

    # Damage type ratio
    total_magic_proxy = item_ap + 1.0
    total_physical_proxy = ad_pool + team_dps * 0.01 + 1.0
    physical_share = total_physical_proxy / (total_physical_proxy + total_magic_proxy)
    magic_share = 1.0 - physical_share

    if n_units > 0:
        inv_n = 1.0 / <double>n_units
    else:
        inv_n = 1.0

    return {
        "num_units": <double>n_units,
        "total_cost": total_cost,
        "avg_star": star_sum * inv_n,
        "num_3_stars": num_3_stars,
        "num_cost_1": cost_1,
        "num_cost_2": cost_2,
        "num_cost_3": cost_3,
        "num_cost_4": cost_4,
        "num_cost_5": cost_5,
        "num_cost_7": cost_7,
        "total_hp_pool": hp_pool,
        "total_ad_pool": ad_pool,
        "avg_attack_speed": as_sum * inv_n,
        "avg_armor": armor_sum * inv_n,
        "avg_mr": mr_sum * inv_n,
        "team_dps": team_dps,
        "frontline_hp": frontline_hp,
        "backline_damage": backline_damage,
        "carry_cost": carry_cost,
        "carry_star": carry_star,
        "carry_item_count": carry_item_count,
        "total_items": total_items,
        "total_completed_items": completed_items,
        "total_components": components,
        "item_offensive": item_offensive,
        "item_defensive": item_defensive,
        "item_utility": item_utility,
        "item_ad": item_ad,
        "item_ap": item_ap,
        "item_hp": item_hp,
        "item_as": item_as,
        "item_armor": item_armor,
        "item_mr": item_mr,
        "qss_count": qss_count,
        "cc_heavy_units": cc_heavy_units,
        "physical_share": physical_share,
        "magic_share": magic_share,
        "has_qss": has_qss,
        "has_guardbreaker": has_guardbreaker,
        "has_blue_buff": has_blue_buff,
        "has_shojin": has_shojin,
        "has_morello": has_morello,
        "has_ionic": has_ionic,
        "carry_api_name": carry_api_name,
    }
