from simulator.core.combat_engine import CombatEngine
from simulator.game.champion_pool import ChampionPool
from simulator.game.constants import NAME_TO_API, NAME_TO_COST
from simulator.game.game import TFTGame
from simulator.game.player import Player
from simulator.game.types import ChampionInstance


def _board_unit(
    player: Player,
    *,
    name: str,
    row: int,
    col: int,
    star_level: int = 1,
    items: list[str] | None = None,
) -> None:
    champion = ChampionInstance(
        instance_id=player._alloc_instance_id(),
        name=name,
        api_name=NAME_TO_API.get(name, f"TFT16_{name.capitalize()}"),
        cost=NAME_TO_COST.get(name, 1),
        star_level=star_level,
        items=list(items or []),
    )
    player._board_add((row, col), champion)


def test_bilgewater_shop_resolves_outcomes_and_applies_stat_bonuses() -> None:
    player = Player(player_id=0)
    pool = ChampionPool()

    # Activate Bilgewater (3)
    _board_unit(player, name="illaoi", row=0, col=0)
    _board_unit(player, name="graves", row=0, col=1)
    _board_unit(player, name="twistedfate", row=0, col=2)

    player.add_bilgewater_serpents(200)
    spent = player.auto_purchase_bilgewater_shop(max_purchases=6, pool=pool)
    assert spent > 0
    assert player.bilgewater_purchases

    gained_units = sum(1 for champ in player.bench if champ is not None)
    assert gained_units >= 1
    assert player.bilgewater_stat_purchases.get(1, 0) >= 1

    engine = CombatEngine(logging_enabled=False)
    team = player.build_combat_team(engine, use_rust_engine=False)
    illaoi = next(unit for unit in team if unit.name == "Illaoi")
    assert illaoi.stats.max_hp > illaoi.base_stats.max_hp


def test_ixtal_quest_state_machine_awards_sunshards_and_unlocks_brock() -> None:
    def agent_noop(_player: Player, _pool: ChampionPool) -> list:
        return []

    game = TFTGame(num_players=2, seed=13, agent_fn=agent_noop, verbose=False)
    p1 = game.players[0]
    p2 = game.players[1]

    # Ensure Ixtal is active for P1.
    _board_unit(p1, name="neeko", row=0, col=0)
    _board_unit(p1, name="milio", row=0, col=1)
    _board_unit(p1, name="skarner", row=0, col=2)
    _board_unit(p2, name="darius", row=0, col=0)

    game.round_num = 4
    game._pvp_round()

    assert p1.unlock_progress.total_ixtal_sunshards >= 500
    assert "brock" in p1.unlock_progress.unlocked_units
    assert p1.ixtal_last_completed_round == 4


def test_pve_unlock_guarantees_first_next_shop() -> None:
    def pve_unlock_agent(player: Player, _pool: ChampionPool) -> list:
        if player.level < 7:
            player.level = 7
            player.invalidate_max_units()
        if not any(champ.name == "leblanc" for champ in player.board.values()):
            _board_unit(
                player,
                name="leblanc",
                row=0,
                col=0,
                items=["rabadonsdeathcap", "rabadonsdeathcap"],
            )
        return []

    game = TFTGame(num_players=1, seed=99, agent_fn=pve_unlock_agent, verbose=False)
    player = game.players[0]

    game.round_num = 0
    game._pve_round()
    assert "veigar" in player.unlock_progress.unlocked_units

    game.round_num = 1
    game._pve_round()
    assert "veigar" in player.shop


def test_pvp_unlock_guarantees_first_next_shop() -> None:
    def agent_noop(_player: Player, _pool: ChampionPool) -> list:
        return []

    game = TFTGame(num_players=2, seed=7, agent_fn=agent_noop, verbose=False)
    p1 = game.players[0]
    p2 = game.players[1]

    p1.level = 7
    p2.level = 7
    _board_unit(
        p1,
        name="leblanc",
        row=0,
        col=0,
        items=["rabadonsdeathcap", "rabadonsdeathcap"],
    )
    _board_unit(p1, name="darius", row=1, col=0)
    _board_unit(p2, name="darius", row=0, col=0)

    game.round_num = 4
    game._pvp_round()
    assert "veigar" in p1.unlock_progress.unlocked_units

    game.round_num = 5
    game._pvp_round()
    assert "veigar" in p1.shop
