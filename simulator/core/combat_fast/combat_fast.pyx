# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3
"""
Cython-accelerated combat math for the TFT simulator.

Provides drop-in replacements for the hottest functions in the Python
combat engine. Import these and monkey-patch the engine, or call
directly from performance-critical batch loops.

Build:
    cd simulator/core/combat_fast && python setup.py build_ext --inplace
"""

from libc.math cimport fabs
from libc.stdlib cimport rand, RAND_MAX

# ===========================================================================
# Hex distance lookup table (same as Python HexGrid._DISTANCE_LUT)
# ===========================================================================

cdef int BOARD_ROWS = 4
cdef int BOARD_COLS = 7
cdef int NUM_HEXES = 28

# Flat [28][28] distance matrix
cdef int _dist_lut[28][28]
cdef bint _lut_built = False

cdef void _build_dist_lut() noexcept nogil:
    """Build the hex distance lookup table once."""
    cdef int r1, c1, r2, c2, idx1, idx2
    cdef int x1, y1, z1, x2, y2, z2

    for r1 in range(BOARD_ROWS):
        for c1 in range(BOARD_COLS):
            idx1 = r1 * BOARD_COLS + c1
            x1 = c1
            z1 = r1 - (c1 - (c1 & 1)) // 2
            y1 = -x1 - z1
            for r2 in range(BOARD_ROWS):
                for c2 in range(BOARD_COLS):
                    idx2 = r2 * BOARD_COLS + c2
                    x2 = c2
                    z2 = r2 - (c2 - (c2 & 1)) // 2
                    y2 = -x2 - z2
                    _dist_lut[idx1][idx2] = (abs(x1 - x2) + abs(y1 - y2) + abs(z1 - z2)) // 2

# Build on import
_build_dist_lut()


def hex_distance_fast(int r1, int c1, int r2, int c2) -> int:
    """Fast hex distance via precomputed LUT.

    >>> hex_distance_fast(0, 0, 3, 6)
    6
    """
    return _dist_lut[r1 * BOARD_COLS + c1][r2 * BOARD_COLS + c2]


# ===========================================================================
# Damage calculation (pure numeric, no Python objects in tight loop)
# ===========================================================================

cpdef tuple calculate_damage_fast(
    double base_damage,
    double attacker_damage_amp,
    double attacker_crit_chance,
    double attacker_crit_multiplier,
    double defender_armor,
    double defender_magic_resist,
    double defender_damage_reduction,
    double defender_max_hp,
    int damage_type,           # 0=physical, 1=magic, 2=true
    bint can_crit,
    bint is_ability,
    bint has_jeweled_gauntlet,
    bint has_giant_slayer,
    bint defender_dragonborn,
    double longshot_bonus,
    double rng_roll,           # pre-rolled random [0, 1)
):
    """Calculate final damage and whether it crits.

    Returns (final_damage: float, did_crit: bool).

    This function avoids all Python object access — it works on raw doubles
    and ints, making it ~5-10x faster than the Python equivalent.
    """
    cdef double damage = base_damage
    cdef bint did_crit = False
    cdef double effective_resist

    # Damage amp
    damage *= (1.0 + attacker_damage_amp + longshot_bonus)

    # Crit check
    if can_crit:
        if not is_ability or has_jeweled_gauntlet:
            if rng_roll < attacker_crit_chance:
                damage *= attacker_crit_multiplier
                did_crit = True

    # Resistance
    if damage_type == 0:  # Physical
        effective_resist = defender_armor
        if effective_resist > 0:
            damage *= 100.0 / (100.0 + effective_resist)
    elif damage_type == 1:  # Magic
        effective_resist = defender_magic_resist
        if effective_resist > 0:
            damage *= 100.0 / (100.0 + effective_resist)
    # True damage: no reduction

    # Durability (damage reduction)
    if defender_damage_reduction > 0:
        damage *= (1.0 - defender_damage_reduction)

    # Dragonborn aura: -10% ability damage
    if is_ability and defender_dragonborn:
        damage *= 0.90

    # Giant Slayer: +15% vs tanks
    if has_giant_slayer and defender_max_hp > 1750.0:
        damage *= 1.15

    if damage < 0:
        damage = 0

    return (damage, did_crit)


# ===========================================================================
# Shield absorption + HP application
# ===========================================================================

cpdef tuple apply_damage_with_shield(
    double damage,
    double current_hp,
    double shield,
    double max_hp,
):
    """Apply damage to HP, absorbing with shield first.

    Returns (remaining_hp, remaining_shield, actual_hp_damage).
    """
    cdef double hp_damage = damage
    cdef double new_shield = shield
    cdef double new_hp = current_hp

    # Shield absorbs first
    if new_shield > 0:
        if hp_damage <= new_shield:
            new_shield -= hp_damage
            return (current_hp, new_shield, 0.0)
        else:
            hp_damage -= new_shield
            new_shield = 0.0

    new_hp -= hp_damage
    if new_hp < 0:
        new_hp = 0

    return (new_hp, new_shield, hp_damage)


# ===========================================================================
# Mana generation on damage taken
# ===========================================================================

cpdef double mana_on_damage(double pre_mitigation, double post_mitigation) noexcept:
    """Calculate mana gained from taking damage.

    TFT formula: 1% of pre-mitigation + 3% of post-mitigation, cap 42.5.
    """
    cdef double gain = pre_mitigation * 0.01 + post_mitigation * 0.03
    if gain > 42.5:
        gain = 42.5
    return gain


# ===========================================================================
# Batch combat outcome (for Monte Carlo without full simulation)
# ===========================================================================

cpdef int find_nearest_enemy_idx(
    int unit_row, int unit_col,
    int[:] enemy_rows, int[:] enemy_cols, bint[:] enemy_alive, bint[:] enemy_targetable,
    bint[:] enemy_frontline,
    int num_enemies,
):
    """Find the index of the nearest targetable enemy, preferring frontline.

    Returns -1 if no valid target.
    """
    cdef int i, d, min_dist, best_idx
    cdef int unit_idx_flat = unit_row * BOARD_COLS + unit_col
    cdef int threshold

    min_dist = 999
    for i in range(num_enemies):
        if enemy_alive[i] and enemy_targetable[i]:
            d = _dist_lut[unit_idx_flat][enemy_rows[i] * BOARD_COLS + enemy_cols[i]]
            if d < min_dist:
                min_dist = d

    if min_dist == 999:
        return -1

    threshold = min_dist + 1

    # Prefer frontline within threshold
    best_idx = -1
    cdef int best_dist = 999
    for i in range(num_enemies):
        if not enemy_alive[i] or not enemy_targetable[i]:
            continue
        d = _dist_lut[unit_idx_flat][enemy_rows[i] * BOARD_COLS + enemy_cols[i]]
        if d <= threshold and enemy_frontline[i]:
            if d < best_dist:
                best_dist = d
                best_idx = i

    if best_idx >= 0:
        return best_idx

    # Fallback: closest overall
    best_dist = 999
    for i in range(num_enemies):
        if not enemy_alive[i] or not enemy_targetable[i]:
            continue
        d = _dist_lut[unit_idx_flat][enemy_rows[i] * BOARD_COLS + enemy_cols[i]]
        if d < best_dist:
            best_dist = d
            best_idx = i

    return best_idx
