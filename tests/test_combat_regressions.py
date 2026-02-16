"""Regression tests for combat correctness issues (HP items, trait scoping, mana, RNG)."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from simulator.core.combat_engine import CombatEngine, DamageType, Item
from simulator.game.champion_pool import ChampionPool
from simulator.game.player import Player
from simulator.game.types import ChampionInstance

PERSISTENT_EFFECT_TEST_CASES: list[tuple[str, float]] = [
    ("ManaRegen", 2.0),
    ("AbilityPower", 25.0),
]


def test_hp_item_updates_max_hp_and_starts_full() -> None:
    engine = CombatEngine(logging_enabled=False)

    base = engine.create_unit("TFT16_Braum", 1, (0, 0), 0, items=None)
    warmogs = engine.create_unit("TFT16_Braum", 1, (0, 0), 0, items=["WarmogsArmor"])
    assert base is not None
    assert warmogs is not None

    assert warmogs.stats.max_hp > base.stats.max_hp
    assert warmogs.stats.hp == warmogs.stats.max_hp


def test_trait_scoping_bilgewater_serpents_award_to_attacker_team_only() -> None:
    engine = CombatEngine(logging_enabled=False)

    class _Sink:
        def __init__(self) -> None:
            self.bilgewater_serpents = 0

        def add_bilgewater_serpents(self, amount: int) -> None:
            self.bilgewater_serpents += amount

    attacker = engine.create_unit("TFT16_Draven", 2, (0, 3), 0)
    defender = engine.create_unit("TFT16_Leona", 2, (3, 3), 1)
    assert attacker is not None
    assert defender is not None

    # Avoid mutating the shared combat-data list by copying.
    attacker.traits = list(attacker.traits) + ["Bilgewater"]

    engine.units = [attacker, defender]
    engine._alive_team0 = [attacker]
    engine._alive_team1 = [defender]

    sink0 = _Sink()
    sink1 = _Sink()
    engine.set_round_persistent_players(sink0, sink1)

    engine.trait_manager.set_bilgewater_count(attacker.team, 3)
    before_team0 = sink0.bilgewater_serpents
    before_team1 = sink1.bilgewater_serpents

    engine.apply_damage(attacker, defender, defender.stats.hp + 9999, DamageType.TRUE, source="test")

    after_team0 = sink0.bilgewater_serpents
    after_team1 = sink1.bilgewater_serpents

    assert after_team0 > before_team0
    assert after_team1 == before_team1

    # Negative control: no Bilgewater trait => no serpents even if count active.
    engine2 = CombatEngine(logging_enabled=False)
    sink2_0 = _Sink()
    sink2_1 = _Sink()
    engine2.set_round_persistent_players(sink2_0, sink2_1)
    attacker2 = engine2.create_unit("TFT16_Draven", 2, (0, 3), 0)
    defender2 = engine2.create_unit("TFT16_Leona", 2, (3, 3), 1)
    assert attacker2 is not None
    assert defender2 is not None
    engine2.units = [attacker2, defender2]
    engine2._alive_team0 = [attacker2]
    engine2._alive_team1 = [defender2]
    engine2.trait_manager.set_bilgewater_count(attacker2.team, 3)
    before = sink2_0.bilgewater_serpents
    engine2.apply_damage(attacker2, defender2, defender2.stats.hp + 9999, DamageType.TRUE, source="test")
    assert sink2_0.bilgewater_serpents == before


def test_trait_scoping_shadow_isles_souls_award_to_attacker_team_only() -> None:
    engine = CombatEngine(logging_enabled=False)

    attacker = engine.create_unit("TFT16_Draven", 2, (0, 3), 0)
    defender = engine.create_unit("TFT16_Leona", 2, (3, 3), 1)
    assert attacker is not None
    assert defender is not None

    attacker.traits = list(attacker.traits) + ["Shadow Isles"]

    engine.units = [attacker, defender]
    engine._alive_team0 = [attacker]
    engine._alive_team1 = [defender]

    engine.trait_manager.set_shadow_isles_count(attacker.team, 2)
    before_team0 = engine.trait_manager.get_team_state(0).shadow_isles_souls
    before_team1 = engine.trait_manager.get_team_state(1).shadow_isles_souls

    engine.apply_damage(attacker, defender, defender.stats.hp + 9999, DamageType.TRUE, source="test")

    after_team0 = engine.trait_manager.get_team_state(0).shadow_isles_souls
    after_team1 = engine.trait_manager.get_team_state(1).shadow_isles_souls

    assert after_team0 > before_team0
    assert after_team1 == before_team1

    # Negative control: no Shadow Isles trait => no souls even if count active.
    engine2 = CombatEngine(logging_enabled=False)
    attacker2 = engine2.create_unit("TFT16_Draven", 2, (0, 3), 0)
    defender2 = engine2.create_unit("TFT16_Leona", 2, (3, 3), 1)
    assert attacker2 is not None
    assert defender2 is not None
    engine2.units = [attacker2, defender2]
    engine2._alive_team0 = [attacker2]
    engine2._alive_team1 = [defender2]
    engine2.trait_manager.set_shadow_isles_count(attacker2.team, 2)
    before = engine2.trait_manager.get_team_state(0).shadow_isles_souls
    engine2.apply_damage(attacker2, defender2, defender2.stats.hp + 9999, DamageType.TRUE, source="test")
    assert engine2.trait_manager.get_team_state(0).shadow_isles_souls == before


def test_invoker_mana_increase_applies_to_damage_taken_mana() -> None:
    engine = CombatEngine(logging_enabled=False)

    defender = engine.create_unit("TFT16_Leona", 1, (3, 3), 1)
    assert defender is not None

    defender.stats.mana = 0
    defender._invoker_mana_increase = 0.25

    engine.units = [defender]
    engine._alive_team0 = []
    engine._alive_team1 = [defender]

    engine.apply_damage(None, defender, 100.0, DamageType.MAGIC, source="test")

    # Base mana gain for 100 damage is 1% pre-mit + 3% post-mit = 4.0.
    # Invoker increase applies multiplicatively.
    assert abs(defender.stats.mana - 5.0) < 1e-6


def test_invoker_mana_increase_applies_to_kill_refund_set_mana_patterns() -> None:
    engine = CombatEngine(logging_enabled=False)

    attacker = engine.create_unit("TFT16_Ambessa", 1, (0, 3), 0)
    defender = engine.create_unit("TFT16_Draven", 1, (3, 3), 1)
    assert attacker is not None
    assert defender is not None

    # Force a kill so we hit Ambessa's kill-reset mana refund path.
    defender.stats.hp = 1.0
    defender.stats.shield = 0.0

    attacker.stats.mana = attacker.stats.max_mana
    attacker._invoker_mana_increase = 0.25

    engine.units = [attacker, defender]
    engine._alive_team0 = [attacker]
    engine._alive_team1 = [defender]
    engine._occupied_dirty = True

    engine.cast_ability(attacker, [defender], [attacker])

    # 80% refund scaled by Invoker (x1.25) clamps to full mana.
    assert abs(attacker.stats.mana - attacker.stats.max_mana) < 1e-6


def test_run_combat_seed_does_not_perturb_python_random_state() -> None:
    engine = CombatEngine(logging_enabled=False)

    unit1 = engine.create_unit("TFT16_Draven", 1, (0, 3), 0)
    unit2 = engine.create_unit("TFT16_Leona", 1, (3, 3), 1)
    assert unit1 is not None
    assert unit2 is not None

    saved_state = random.getstate()
    engine.run_combat([unit1], [unit2], seed=12345)
    assert random.getstate() == saved_state


def test_player_instance_id_keyed_augment_bonus_applies_to_combat_unit() -> None:
    engine = CombatEngine(logging_enabled=False)
    player = Player(player_id=0)
    champion = ChampionInstance(
        instance_id="p0_u0",
        name="draven",
        api_name="TFT16_Draven",
        cost=1,
        star_level=1,
    )
    player._board_add((0, 0), champion)
    player.set_augment_permanent_bonus(champion.instance_id, "mana_regen", 2.0)

    team = player.build_combat_team(engine, use_rust_engine=False)
    assert len(team) == 1
    assert team[0].instance_id == champion.instance_id
    assert abs(team[0].stats.mana_regen - 2.0) < 1e-6


def test_persistent_effect_cases_cover_persistent_effect_stat_map() -> None:
    engine = CombatEngine(logging_enabled=False)
    observed_effects = set(engine.augment_manager.PERSISTENT_EFFECT_STAT_MAP.keys())
    covered_effects = {effect_name for effect_name, _effect_value in PERSISTENT_EFFECT_TEST_CASES}
    assert covered_effects == observed_effects


@pytest.mark.parametrize(
    ("effect_name", "effect_value"),
    PERSISTENT_EFFECT_TEST_CASES,
    ids=[effect_name for effect_name, _effect_value in PERSISTENT_EFFECT_TEST_CASES],
)
def test_item_conditional_augment_persists_effect_by_instance_id_without_double_apply(
    effect_name: str,
    effect_value: float,
) -> None:
    engine = CombatEngine(logging_enabled=False)
    player = Player(player_id=0)
    unit = engine.create_unit("TFT16_Draven", 1, (0, 3), 0, items=[], instance_id="p0_u7")
    assert unit is not None
    unit.items = [Item(name="Spatula")]
    bonus_name, stat_name = engine.augment_manager.PERSISTENT_EFFECT_STAT_MAP[effect_name]
    before_value = float(getattr(unit.stats, stat_name))

    augment = {
        "effects": {effect_name: effect_value},
        "desc": "Units holding Spatula gain persistent stats",
    }

    engine.augment_manager._apply_item_conditional_augment(
        [unit],
        augment,
        round_persistent_player=player,
    )
    first_stat_value = float(getattr(unit.stats, stat_name))
    assert first_stat_value > before_value
    assert player.get_augment_permanent_bonus("p0_u7", bonus_name, 0.0) == effect_value

    engine.augment_manager._apply_item_conditional_augment(
        [unit],
        augment,
        round_persistent_player=player,
    )
    assert abs(float(getattr(unit.stats, stat_name)) - first_stat_value) < 1e-6


def test_instance_id_augment_bonus_persists_through_upgrade_and_clears_on_sell_replacement() -> None:
    engine = CombatEngine(logging_enabled=False)
    player = Player(player_id=0)
    pool = ChampionPool()

    player.bench[0] = ChampionInstance(
        instance_id="p0_u0",
        name="draven",
        api_name="TFT16_Draven",
        cost=1,
        star_level=1,
    )
    player.bench[1] = ChampionInstance(
        instance_id="p0_u1",
        name="draven",
        api_name="TFT16_Draven",
        cost=1,
        star_level=1,
    )
    player.bench[2] = ChampionInstance(
        instance_id="p0_u2",
        name="draven",
        api_name="TFT16_Draven",
        cost=1,
        star_level=1,
    )
    player.set_augment_permanent_bonus("p0_u1", "mana_regen", 2.0)

    player._check_upgrade("draven", pool)

    upgraded = player.bench[0]
    assert upgraded is not None
    assert upgraded.star_level == 2
    assert player.get_augment_permanent_bonus(upgraded.instance_id, "mana_regen", 0.0) == 2.0
    assert "p0_u1" not in player.augment_permanent_bonuses
    assert "p0_u2" not in player.augment_permanent_bonuses

    player._board_add((0, 0), upgraded)
    player.bench[0] = None
    team = player.build_combat_team(engine, use_rust_engine=False)
    assert len(team) == 1
    assert team[0].instance_id == upgraded.instance_id
    assert abs(team[0].stats.mana_regen - 2.0) < 1e-6

    assert player.sell_from_board(0, 0, pool)
    assert upgraded.instance_id not in player.augment_permanent_bonuses

    replacement = ChampionInstance(
        instance_id="p0_u99",
        name="draven",
        api_name="TFT16_Draven",
        cost=1,
        star_level=1,
    )
    player._board_add((0, 0), replacement)
    replacement_team = player.build_combat_team(engine, use_rust_engine=False)
    assert len(replacement_team) == 1
    assert replacement_team[0].instance_id == replacement.instance_id
    assert abs(replacement_team[0].stats.mana_regen) < 1e-6
    assert player.get_augment_permanent_bonus(replacement.instance_id, "mana_regen", 0.0) == 0.0


def test_parity_hp_item_and_takedown_trait_counters_python_vs_rust() -> None:
    pytest.importorskip("tft_combat_engine")
    from tft_combat_engine import RustCombatEngine

    combat_data_path = str((Path(__file__).resolve().parents[1] / "simulator" / "data" / "combat_data.json"))
    rust = RustCombatEngine(combat_data_path)

    # -- HP item parity: Warmog's should swing the duel outcome consistently.
    py = CombatEngine(logging_enabled=False)
    py_team0 = [py.create_unit("TFT16_Braum", 1, (0, 0), 0, items=["WarmogsArmor"])]
    py_team1 = [py.create_unit("TFT16_Braum", 1, (3, 3), 1, items=[])]
    assert py_team0[0] is not None
    assert py_team1[0] is not None
    py_res = py.run_combat(py_team0, py_team1, seed=4242)

    rust_res = rust.run_combat(
        [{'api_name': 'TFT16_Braum', 'star_level': 1, 'position': [0, 0], 'team': 0, 'items': ['WarmogsArmor'], 'traits': []}],
        [{'api_name': 'TFT16_Braum', 'star_level': 1, 'position': [3, 3], 'team': 1, 'items': [], 'traits': []}],
        seed=4242,
    )
    assert py_res["winner"] == rust_res["winner"] == 0

    # -- Trait currency parity: takedown rewards should match between engines.
    py2 = CombatEngine(logging_enabled=False)

    class _Sink:
        def __init__(self) -> None:
            self.bilgewater_serpents = 0

        def add_bilgewater_serpents(self, amount: int) -> None:
            self.bilgewater_serpents += amount

    sink0 = _Sink()
    sink1 = _Sink()
    py2.set_round_persistent_players(sink0, sink1)

    attacker = py2.create_unit("TFT16_Draven", 3, (0, 3), 0, items=[])
    bg1 = py2.create_unit("TFT16_Braum", 1, (0, 0), 0, items=[])
    bg2 = py2.create_unit("TFT16_Braum", 1, (0, 1), 0, items=[])
    defender = py2.create_unit("TFT16_Draven", 1, (3, 3), 1, items=[])
    assert attacker is not None
    assert bg1 is not None
    assert bg2 is not None
    assert defender is not None

    attacker.traits = ["Bilgewater", "Shadow Isles"]
    bg1.traits = ["Bilgewater", "Shadow Isles"]
    bg2.traits = ["Bilgewater", "Shadow Isles"]
    defender.traits = []

    py2_res = py2.run_combat([attacker, bg1, bg2], [defender], seed=1337)
    assert py2_res["winner"] == 0

    py_serpents_t0 = sink0.bilgewater_serpents
    py_serpents_t1 = sink1.bilgewater_serpents
    py_souls_t0 = py2.trait_manager.get_shadow_isles_souls(0)
    py_souls_t1 = py2.trait_manager.get_shadow_isles_souls(1)

    rust_res2 = rust.run_combat(
        [
            {'api_name': 'TFT16_Draven', 'star_level': 3, 'position': [0, 3], 'team': 0, 'items': [], 'traits': ['Bilgewater', 'Shadow Isles']},
            {'api_name': 'TFT16_Braum', 'star_level': 1, 'position': [0, 0], 'team': 0, 'items': [], 'traits': ['Bilgewater', 'Shadow Isles']},
            {'api_name': 'TFT16_Braum', 'star_level': 1, 'position': [0, 1], 'team': 0, 'items': [], 'traits': ['Bilgewater', 'Shadow Isles']},
        ],
        [{'api_name': 'TFT16_Draven', 'star_level': 1, 'position': [3, 3], 'team': 1, 'items': [], 'traits': []}],
        seed=1337,
    )

    assert py_serpents_t0 > 0
    assert py_souls_t0 > 0
    assert py_serpents_t1 == 0
    assert py_souls_t1 == 0

    assert rust_res2["team0_bilgewater_serpents"] == py_serpents_t0
    assert rust_res2["team1_bilgewater_serpents"] == py_serpents_t1
    assert rust_res2["team0_shadow_isles_souls"] == py_souls_t0
    assert rust_res2["team1_shadow_isles_souls"] == py_souls_t1
    assert "debug_takedowns" in rust_res2
    assert isinstance(rust_res2["debug_takedowns"], list)
    assert len(rust_res2["debug_takedowns"]) > 0
    first_takedown = rust_res2["debug_takedowns"][0]
    assert first_takedown["killer_api_name"] in {"TFT16_Draven", "TFT16_Braum"}
