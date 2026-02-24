"""Cython-accelerated combat math.

Build first:
    cd simulator/core/combat_fast && python setup.py build_ext --inplace

Then import:
    from simulator.core.combat_fast import (
        hex_distance_fast,
        calculate_damage_fast,
        apply_damage_with_shield,
        mana_on_damage,
        find_nearest_enemy_idx,
    )
"""

try:
    from .combat_fast import (
        apply_damage_with_shield,
        calculate_damage_fast,
        find_nearest_enemy_idx,
        hex_distance_fast,
        mana_on_damage,
    )

    CYTHON_AVAILABLE = True
except ImportError:
    CYTHON_AVAILABLE = False
