from simulator.game.champion_pool import ChampionPool
from simulator.game.player import Player
from simulator.game.types import ChampionInstance
from simulator.game.unlocks import (
    CombatUnlockContext,
    PreCombatUnitSnapshot,
    UnlockRequirementsManager,
)
from simulator.game.constants import NAME_TO_API, NAME_TO_COST


def _snap(
    *,
    idx: int,
    name: str,
    row: int,
    star: int = 1,
    traits: tuple[str, ...],
    items: tuple[str, ...] = (),
    max_hp: float = 1200.0,
    omnivamp: float = 0.0,
    is_tank: bool = False,
) -> PreCombatUnitSnapshot:
    return PreCombatUnitSnapshot(
        instance_id=f"u{idx}",
        name=name,
        api_name=NAME_TO_API.get(name, f"TFT16_{name.capitalize()}"),
        row=row,
        star_level=star,
        item_count=len(items),
        normalized_items=items,
        traits=traits,
        max_hp=max_hp,
        omnivamp=omnivamp,
        is_tank=is_tank,
    )


def _board_unit(player: Player, *, name: str, row: int, col: int, star_level: int = 1) -> None:
    champion = ChampionInstance(
        instance_id=player._alloc_instance_id(),
        name=name,
        api_name=NAME_TO_API.get(name, f"TFT16_{name.capitalize()}"),
        cost=NAME_TO_COST.get(name, 1),
        star_level=star_level,
    )
    player._board_add((row, col), champion)


def test_unlocks_multi_unit_and_next_shop_guarantee() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.level = 7
    manager.initialize_player(player)

    precombat = [
        _snap(idx=1, name="poppy", row=0, star=1, traits=("yordle", "demacia", "juggernaut")),
        _snap(idx=2, name="kennen", row=0, star=2, traits=("ionia", "yordle", "defender")),
        _snap(idx=3, name="kobuko", row=1, star=3, traits=("yordle", "bruiser", "invoker")),
        _snap(idx=4, name="fizz", row=1, star=1, traits=("bilgewater", "yordle")),
        _snap(idx=5, name="graves", row=1, star=2, traits=("bilgewater", "gunslinger")),
        _snap(
            idx=6,
            name="leblanc",
            row=0,
            star=1,
            traits=("noxus", "invoker"),
            items=("rabadonsdeathcap", "rabadonsdeathcap"),
        ),
        _snap(idx=7, name="orianna", row=0, star=2, traits=("piltover", "invoker")),
    ]

    unlocked = manager.evaluate_post_combat(
        player=player,
        precombat_units=precombat,
        context=CombatUnlockContext(phase="pvp", outcome="win"),
    )
    assert {"fizz", "kobuko", "veigar"} == set(unlocked)

    guaranteed = manager.consume_shop_guarantees_for_player(player)
    assert {"fizz", "kobuko", "veigar"} == set(guaranteed)
    assert manager.consume_shop_guarantees_for_player(player) == []

    pool = ChampionPool()
    shop = pool.roll_shop(
        level=7,
        allowed_names=manager.allowed_shop_units_for_player(player),
        guaranteed_names=guaranteed,
    )
    assert all(unit in shop for unit in ("fizz", "kobuko", "veigar"))


def test_bard_unlock_only_counts_pre_carousel_rerolls() -> None:
    manager = UnlockRequirementsManager()

    player = Player(player_id=0)
    manager.initialize_player(player)
    for _ in range(4):
        manager.record_reroll(player, round_num=0)
    assert "bard" in player.unlock_progress.unlocked_units
    assert manager.consume_shop_guarantees_for_player(player) == ["bard"]

    player_late = Player(player_id=1)
    manager.initialize_player(player_late)
    for _ in range(4):
        manager.record_reroll(player_late, round_num=3)
    unlocked_late = manager.evaluate_post_combat(
        player=player_late,
        precombat_units=[],
        context=CombatUnlockContext(phase="pve", outcome=None),
    )
    assert "bard" not in unlocked_late


def test_sylas_unlock_can_happen_before_combat() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.level = 9
    manager.initialize_player(player)

    manager.record_sell(player, "jarvaniv", star_level=2)
    assert "sylas" not in player.unlock_progress.unlocked_units
    manager.record_sell(player, "garen", star_level=2)

    assert "sylas" in player.unlock_progress.unlocked_units
    assert manager.consume_shop_guarantees_for_player(player) == ["sylas"]


def test_shurima_thresholds_increase_after_each_shurima_unlock() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.level = 9
    manager.initialize_player(player)

    azir_precombat = [
        _snap(idx=1, name="azir", row=0, star=1, traits=("shurima", "emperor", "disruptor")),
    ]

    unlocks_after_first_loss = manager.evaluate_post_combat(
        player=player,
        precombat_units=azir_precombat,
        context=CombatUnlockContext(phase="pvp", outcome="loss"),
    )
    assert "nasus" not in unlocks_after_first_loss

    unlocks_after_second_loss = manager.evaluate_post_combat(
        player=player,
        precombat_units=azir_precombat,
        context=CombatUnlockContext(phase="pvp", outcome="loss"),
    )
    assert "nasus" in unlocks_after_second_loss

    unlocks_after_two_wins = []
    for _ in range(2):
        unlocks_after_two_wins = manager.evaluate_post_combat(
            player=player,
            precombat_units=azir_precombat,
            context=CombatUnlockContext(phase="pvp", outcome="win"),
        )
    assert "renekton" not in unlocks_after_two_wins

    unlocks_after_third_win = manager.evaluate_post_combat(
        player=player,
        precombat_units=azir_precombat,
        context=CombatUnlockContext(phase="pvp", outcome="win"),
    )
    assert "renekton" in unlocks_after_third_win

    manager.evaluate_post_combat(
        player=player,
        precombat_units=azir_precombat,
        context=CombatUnlockContext(phase="pvp", outcome="draw"),
    )

    alternating = ["win", "loss", "win", "loss", "win"]
    last_unlocks = []
    for outcome in alternating:
        last_unlocks = manager.evaluate_post_combat(
            player=player,
            precombat_units=azir_precombat,
            context=CombatUnlockContext(phase="pvp", outcome=outcome),
        )
    assert "xerath" in last_unlocks


def test_sett_unlock_requires_exactly_one_front_row_unit() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.level = 8
    manager.initialize_player(player)

    one_frontline = [
        _snap(idx=1, name="darius", row=0, star=1, traits=("noxus", "juggernaut")),
        _snap(idx=2, name="orianna", row=2, star=1, traits=("piltover", "invoker")),
        _snap(idx=3, name="neeko", row=3, star=1, traits=("ixtal", "defender")),
    ]
    unlocks = manager.evaluate_post_combat(
        player=player,
        precombat_units=one_frontline,
        context=CombatUnlockContext(phase="pvp", outcome="win"),
    )
    assert "sett" in unlocks

    player2 = Player(player_id=1)
    player2.level = 8
    manager.initialize_player(player2)
    zero_frontline = [
        _snap(idx=11, name="orianna", row=2, star=1, traits=("piltover", "invoker")),
        _snap(idx=12, name="neeko", row=3, star=1, traits=("ixtal", "defender")),
    ]
    unlocks_zero = manager.evaluate_post_combat(
        player=player2,
        precombat_units=zero_frontline,
        context=CombatUnlockContext(phase="pvp", outcome="win"),
    )
    assert "sett" not in unlocks_zero


def test_shop_guarantee_only_after_combat_unlock_evaluation() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.level = 7
    manager.initialize_player(player)

    # Unlock not yet evaluated this round, so no guarantee is queued.
    assert manager.consume_shop_guarantees_for_player(player) == []

    precombat = [
        _snap(
            idx=1,
            name="leblanc",
            row=0,
            star=1,
            traits=("noxus", "invoker"),
            items=("rabadonsdeathcap", "rabadonsdeathcap"),
        ),
        _snap(
            idx=2,
            name="darius",
            row=1,
            star=1,
            traits=("noxus", "juggernaut"),
        ),
    ]
    unlocked = manager.evaluate_post_combat(
        player=player,
        precombat_units=precombat,
        context=CombatUnlockContext(phase="pvp", outcome="win"),
    )
    assert "veigar" in unlocked

    guaranteed = manager.consume_shop_guarantees_for_player(player)
    assert guaranteed == ["veigar"]
    assert manager.consume_shop_guarantees_for_player(player) == []


def test_tahm_unlock_requires_spent_serpents() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.set_unlock_manager(manager)
    manager.initialize_player(player)

    player.add_bilgewater_serpents(500)
    assert "tahmkench" not in player.unlock_progress.unlocked_units

    assert player.spend_bilgewater_serpents(450)
    assert "tahmkench" in player.unlock_progress.unlocked_units
    assert manager.consume_shop_guarantees_for_player(player) == ["tahmkench"]


def test_noncombat_and_postcombat_unlocks_stack_next_shop_guarantees() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.level = 9
    manager.initialize_player(player)

    manager.record_sell(player, "jarvaniv", star_level=2)
    manager.record_sell(player, "garen", star_level=2)
    assert "sylas" in player.unlock_progress.unlocked_units

    precombat = [
        _snap(
            idx=1,
            name="leblanc",
            row=0,
            star=1,
            traits=("noxus", "invoker"),
            items=("rabadonsdeathcap", "rabadonsdeathcap"),
        ),
        _snap(
            idx=2,
            name="darius",
            row=1,
            star=1,
            traits=("noxus", "juggernaut"),
        ),
    ]
    unlocked = manager.evaluate_post_combat(
        player=player,
        precombat_units=precombat,
        context=CombatUnlockContext(phase="pvp", outcome="win"),
    )
    assert "veigar" in unlocked
    assert manager.consume_shop_guarantees_for_player(player) == ["sylas", "veigar"]


def test_brock_unlock_counts_ixtal_quest_ladders() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.set_unlock_manager(manager)
    manager.initialize_player(player)

    quest_rewards = [
        player.complete_ixtal_quest("TFT16_Explorer_QiyanaTakedownQuest"),
        player.complete_ixtal_quest("Qiyana Takedown"),
        player.complete_ixtal_quest("Qiyana Takedown"),
        player.complete_ixtal_quest("Champs Died"),
        player.complete_ixtal_quest("Champs Died"),
        player.complete_ixtal_quest("Champs Died"),
    ]
    assert quest_rewards[:3] == [30, 50, 80]
    assert sum(quest_rewards) >= 500

    unlocks = manager.evaluate_post_combat(
        player=player,
        precombat_units=[],
        context=CombatUnlockContext(phase="pve", outcome=None),
    )
    assert "brock" in unlocks


def test_auto_bilgewater_shop_spending_tracks_tahm_progress() -> None:
    manager = UnlockRequirementsManager()
    player = Player(player_id=0)
    player.set_unlock_manager(manager)
    manager.initialize_player(player)

    # Activate Bilgewater (3) so the Bilgewater shop is available.
    _board_unit(player, name="illaoi", row=0, col=0)
    _board_unit(player, name="graves", row=0, col=1)
    _board_unit(player, name="twistedfate", row=0, col=2)

    player.add_bilgewater_serpents(600)
    spent = player.auto_purchase_bilgewater_shop(max_purchases=64)
    assert spent >= 450
    assert player.unlock_progress.total_bilgewater_serpents_spent == spent

    unlocks = manager.evaluate_post_combat(
        player=player,
        precombat_units=[],
        context=CombatUnlockContext(phase="pve", outcome=None),
    )
    assert "tahmkench" in player.unlock_progress.unlocked_units
    assert "tahmkench" not in unlocks


def test_ixtal_reward_artifact_loaded() -> None:
    manager = UnlockRequirementsManager()
    assert manager.ixtal_quest_reward_ladders.get("qiyana takedown") == (30, 50, 80, 80, 80)


def test_requirements_csv_parsing_with_preamble_and_aliases(tmp_path) -> None:
    csv_path = tmp_path / "unlock requirements.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Here's the updated table with level requirements included:,,",
                ",,",
                "Unit,Unlock Condition,Level Req",
                "Kobuko & Yuumi,example,7",
                "Kai'Sa,example,7",
                "Bard,example,—",
            ]
        ),
        encoding="utf-8",
    )

    manager = UnlockRequirementsManager(csv_path=csv_path)
    assert manager.unlock_order[:3] == ["kobuko", "kaisa", "bard"]
    assert manager.level_requirements["kobuko"] == 7
    assert manager.level_requirements["kaisa"] == 7
    assert manager.level_requirements["bard"] is None
