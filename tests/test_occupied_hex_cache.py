"""Regression coverage for occupied-hex caching in the Python combat engine."""

from __future__ import annotations

from simulator.core.combat_engine import CombatEngine


def test_occupied_hexes_cache_invalidated_on_dash() -> None:
    engine = CombatEngine(logging_enabled=False)

    fizz = engine.create_unit("TFT16_Fizz", 1, (0, 0), 0)
    leona = engine.create_unit("TFT16_Leona", 1, (3, 3), 1)
    assert fizz is not None
    assert leona is not None

    engine.units = [fizz, leona]

    occupied_before = engine.get_occupied_hexes()
    old_pos = fizz.position
    assert old_pos in occupied_before

    engine.cast_ability(fizz, enemies=[leona], allies=[fizz])
    assert fizz.position != old_pos

    occupied_after = engine.get_occupied_hexes()
    assert fizz.position in occupied_after
    assert old_pos not in occupied_after
