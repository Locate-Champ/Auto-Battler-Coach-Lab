"""Agent action interface for the TFT game loop.

Provides legal action enumeration and execution for RL agents.
"""

from __future__ import annotations

import random
from typing import List, TYPE_CHECKING

from .types import Action, ActionType
from .constants import (
    BENCH_SIZE, BOARD_ROWS, BOARD_COLS, SHOP_SIZE,
    REFRESH_COST, XP_COST, MAX_LEVEL, MAX_ITEMS_PER_UNIT,
    NAME_TO_COST,
)
from .shop import buy_from_shop, sell_unit, refresh_shop

if TYPE_CHECKING:
    from .player import Player
    from .champion_pool import ChampionPool


def get_legal_actions(player: 'Player', pool: 'ChampionPool') -> List[Action]:
    """Get all legal actions for a player in the current state.

    Returns a list of valid Action objects the player can take.
    """
    actions = [Action.pass_action()]

    # Buy from shop
    for slot in range(SHOP_SIZE):
        name = player.shop[slot]
        if name is None:
            continue
        cost = NAME_TO_COST.get(name, 1)
        if player.gold >= cost and player._find_empty_bench() is not None:
            actions.append(Action.buy(slot))

    # Sell from board
    for (row, col) in list(player.board.keys()):
        actions.append(Action.sell((row, col)))

    # Sell from bench
    for idx in range(BENCH_SIZE):
        if player.bench[idx] is not None:
            actions.append(Action.sell((idx,)))

    # Move: bench to board
    for idx in range(BENCH_SIZE):
        if player.bench[idx] is None:
            continue
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                pos = (row, col)
                if pos not in player.board:
                    # Only allow if board has capacity
                    if player.board_count < player.max_units:
                        actions.append(Action.move((idx,), pos))
                else:
                    # Swap is always allowed
                    actions.append(Action.move((idx,), pos))

    # Move: board to board (reposition)
    board_positions = list(player.board.keys())
    for from_pos in board_positions:
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                to_pos = (row, col)
                if to_pos != from_pos:
                    actions.append(Action.move(from_pos, to_pos))

    # Level up
    if player.gold >= XP_COST and player.level < MAX_LEVEL:
        actions.append(Action.level())

    # Refresh shop
    if player.gold >= REFRESH_COST:
        actions.append(Action.refresh())

    # Equip items from item bench onto board or bench champions
    for item_idx in range(len(player.item_bench)):
        # Equip onto board champions
        for (row, col), champ in player.board.items():
            if len(champ.items) < MAX_ITEMS_PER_UNIT:
                actions.append(Action.equip_item(item_idx, (row, col)))
        # Equip onto bench champions
        for bench_idx in range(BENCH_SIZE):
            champ = player.bench[bench_idx]
            if champ is not None and len(champ.items) < MAX_ITEMS_PER_UNIT:
                actions.append(Action.equip_item(item_idx, (-1, bench_idx)))

    # Place Freljord tower (if Freljord 3+ active)
    if player.has_freljord_active():
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                actions.append(Action.place_tower(row, col))

    # Place Azir soldiers (if Azir on board, max 2)
    if player.has_azir_on_board() and len(player.soldier_positions) < 2:
        occupied = set(player.board.keys()) | set(player.soldier_positions)
        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                if (row, col) not in occupied:
                    actions.append(Action.place_soldier(row, col))

    return actions


def execute_action(action: Action, player: 'Player',
                   pool: 'ChampionPool') -> bool:
    """Execute an action for a player. Returns True if successful."""

    if action.action_type == ActionType.PASS:
        return True

    elif action.action_type == ActionType.BUY:
        slot = action.args[0]
        return buy_from_shop(player, pool, slot)

    elif action.action_type == ActionType.SELL:
        pos = action.args
        if len(pos) == 2:
            return sell_unit(player, pool, 'board', pos)
        else:
            return sell_unit(player, pool, 'bench', pos[0])

    elif action.action_type == ActionType.MOVE:
        from_pos, to_pos = action.args
        if len(from_pos) == 1:
            # Bench to board
            return player.bench_to_board(from_pos[0], to_pos[0], to_pos[1])
        else:
            # Board to board
            return player.move_on_board(
                from_pos[0], from_pos[1], to_pos[0], to_pos[1]
            )

    elif action.action_type == ActionType.LEVEL:
        return player.buy_xp()

    elif action.action_type == ActionType.REFRESH:
        return refresh_shop(player, pool)

    elif action.action_type == ActionType.EQUIP_ITEM:
        item_idx, target = action.args
        if target[0] == -1:
            # Bench target: (-1, bench_idx)
            return player.equip_item_bench(item_idx, target[1])
        else:
            # Board target: (row, col)
            return player.equip_item(item_idx, target)

    elif action.action_type == ActionType.CHOOSE_AUGMENT:
        # Handled directly by game loop, not via execute_action
        return False

    elif action.action_type == ActionType.PLACE_TOWER:
        row, col = action.args
        return player.place_tower(row, col)

    elif action.action_type == ActionType.PLACE_SOLDIER:
        row, col = action.args
        return player.place_soldier(row, col)

    return False


def random_agent_actions(player: 'Player', pool: 'ChampionPool',
                         max_actions: int = 10) -> List[Action]:
    """Generate random legal actions for testing (SLOW - enumerates all actions).

    Kept for compatibility and RL training. For batch simulation, use
    fast_random_agent instead.
    """
    executed = []
    for _ in range(max_actions):
        legal = get_legal_actions(player, pool)
        meaningful = [a for a in legal if a.action_type != ActionType.PASS]
        if not meaningful:
            break

        weights = []
        for a in meaningful:
            if a.action_type == ActionType.BUY:
                weights.append(10)
            elif a.action_type == ActionType.LEVEL:
                weights.append(5)
            elif a.action_type == ActionType.EQUIP_ITEM:
                weights.append(8)
            elif a.action_type == ActionType.REFRESH:
                weights.append(3)
            elif a.action_type == ActionType.SELL:
                weights.append(1)
            elif a.action_type == ActionType.PLACE_TOWER:
                weights.append(6)
            elif a.action_type == ActionType.PLACE_SOLDIER:
                weights.append(6)
            else:
                weights.append(1)

        action = random.choices(meaningful, weights=weights, k=1)[0]
        success = execute_action(action, player, pool)
        if success:
            executed.append(action)

    return executed


# ── Fast Random Agent ────────────────────────────────────────────────────
# Direct-sampling agent: picks action type first, then random valid target.
# ~10x faster than random_agent_actions since it avoids enumerating all legal
# actions (which is O(board^2) per call).

_FAST_ACTION_TYPES = [
    ActionType.BUY,
    ActionType.EQUIP_ITEM,
    ActionType.LEVEL,
    ActionType.REFRESH,
    ActionType.MOVE,
    ActionType.SELL,
]
_FAST_ACTION_WEIGHTS = [10, 8, 5, 3, 1, 1]


def _try_buy(player: 'Player', pool: 'ChampionPool') -> bool:
    """Try to buy a random affordable champion from the shop."""
    slots = [i for i in range(SHOP_SIZE)
             if player.shop[i] is not None
             and player.gold >= NAME_TO_COST.get(player.shop[i], 1)
             and player._find_empty_bench() is not None]
    if not slots:
        return False
    return buy_from_shop(player, pool, random.choice(slots))


def _try_equip(player: 'Player') -> bool:
    """Try to equip a random item onto a random champion."""
    if not player.item_bench:
        return False
    # Find champions with item slots available
    targets = []
    for pos, champ in player.board.items():
        if len(champ.items) < MAX_ITEMS_PER_UNIT:
            targets.append(('board', pos))
    for idx in range(BENCH_SIZE):
        champ = player.bench[idx]
        if champ and len(champ.items) < MAX_ITEMS_PER_UNIT:
            targets.append(('bench', idx))
    if not targets:
        return False
    item_idx = random.randrange(len(player.item_bench))
    loc, target = random.choice(targets)
    if loc == 'board':
        return player.equip_item(item_idx, target)
    else:
        return player.equip_item_bench(item_idx, target)


def _try_move(player: 'Player') -> bool:
    """Try a random move (bench→board or board→board reposition)."""
    # 70% chance bench→board, 30% board→board reposition
    if random.random() < 0.7:
        # Bench to board
        bench_occupied = [i for i in range(BENCH_SIZE) if player.bench[i] is not None]
        if not bench_occupied or player.board_count >= player.max_units:
            return False
        idx = random.choice(bench_occupied)
        # Pick a random empty board position
        empty = [(r, c) for r in range(BOARD_ROWS) for c in range(BOARD_COLS)
                 if (r, c) not in player.board]
        if not empty:
            return False
        row, col = random.choice(empty)
        return player.bench_to_board(idx, row, col)
    else:
        # Board to board reposition
        positions = list(player.board.keys())
        if not positions:
            return False
        from_pos = random.choice(positions)
        to_row = random.randrange(BOARD_ROWS)
        to_col = random.randrange(BOARD_COLS)
        if (to_row, to_col) == from_pos:
            return False
        return player.move_on_board(from_pos[0], from_pos[1], to_row, to_col)


def _try_sell(player: 'Player', pool: 'ChampionPool') -> bool:
    """Try to sell a random bench unit (prefer bench over board)."""
    bench_occupied = [i for i in range(BENCH_SIZE) if player.bench[i] is not None]
    if bench_occupied:
        idx = random.choice(bench_occupied)
        return sell_unit(player, pool, 'bench', idx)
    return False


def fast_random_agent(player: 'Player', pool: 'ChampionPool',
                      max_actions: int = 10) -> List[Action]:
    """Fast random agent that avoids full legal action enumeration.

    Instead of building the full O(board^2) action list, this agent:
    1. Picks a random action type (weighted towards buys/items/levels)
    2. Attempts to find and execute a valid target for that type
    3. Falls back to next type on failure

    Produces similar game behavior to random_agent_actions but ~10x faster.
    """
    executed = []
    consecutive_fails = 0
    for _ in range(max_actions):
        action_type = random.choices(_FAST_ACTION_TYPES, _FAST_ACTION_WEIGHTS, k=1)[0]

        success = False
        if action_type == ActionType.BUY:
            success = _try_buy(player, pool)
        elif action_type == ActionType.EQUIP_ITEM:
            success = _try_equip(player)
        elif action_type == ActionType.LEVEL:
            if player.gold >= XP_COST and player.level < MAX_LEVEL:
                success = player.buy_xp()
        elif action_type == ActionType.REFRESH:
            if player.gold >= REFRESH_COST:
                success = refresh_shop(player, pool)
        elif action_type == ActionType.MOVE:
            success = _try_move(player)
        elif action_type == ActionType.SELL:
            success = _try_sell(player, pool)

        if success:
            consecutive_fails = 0
        else:
            consecutive_fails += 1
            # If we fail 5 times in a row, probably nothing useful left to do
            if consecutive_fails >= 5:
                break

    return executed


# ── Heuristic Agents ────────────────────────────────────────────────────

def _has_copy(player: 'Player', name: str) -> bool:
    """Check if the player has any copy of this champion (board or bench)."""
    for champ in player.board.values():
        if champ.name == name:
            return True
    for champ in player.bench:
        if champ and champ.name == name:
            return True
    return False


def _equip_on_best_unit(player: 'Player') -> int:
    """Equip all items from item bench onto the highest-value board units.

    Prefers high-cost, high-star units. Returns number of items equipped.
    """
    equipped = 0
    for _ in range(20):  # Safety limit
        if not player.item_bench:
            break
        best_pos = None
        best_score = -1
        for pos, champ in player.board.items():
            if len(champ.items) < MAX_ITEMS_PER_UNIT:
                score = champ.cost * 10 + champ.star_level
                if score > best_score:
                    best_score = score
                    best_pos = pos
        if best_pos is None:
            break
        if not player.equip_item(0, best_pos):
            break
        equipped += 1
    return equipped


def econ_agent(player: 'Player', pool: 'ChampionPool',
               max_actions: int = 10) -> List[Action]:
    """Economy agent: saves gold for interest, levels to 8, then rolls excess.

    Strategy:
    1. Buy pairs/triples from shop (working toward upgrades)
    2. Level up while keeping 50+ gold (interest cap)
    3. At level 7+, roll excess gold above 50 buying pairs
    4. Buy cheap (1-2 cost) units without breaking interest bracket
    5. Equip items onto highest-value board units
    """
    # 1. Buy pairs from current shop
    for slot in range(SHOP_SIZE):
        name = player.shop[slot]
        if not name:
            continue
        cost = NAME_TO_COST.get(name, 1)
        if player.gold < cost or player._find_empty_bench() is None:
            continue
        if _has_copy(player, name):
            buy_from_shop(player, pool, slot)

    # 2. Level up while maintaining 50g floor
    while player.level < 8 and player.gold >= XP_COST + 50:
        if not player.buy_xp():
            break

    # 3. At level 7+, roll excess above 50 buying pairs
    if player.level >= 7:
        for _ in range(3):
            if player.gold <= 50 + REFRESH_COST:
                break
            refresh_shop(player, pool)
            for slot in range(SHOP_SIZE):
                name = player.shop[slot]
                if not name:
                    continue
                cost = NAME_TO_COST.get(name, 1)
                if player.gold - cost < 50 or player._find_empty_bench() is None:
                    continue
                if _has_copy(player, name):
                    buy_from_shop(player, pool, slot)

    # 4. Buy cheap units without breaking interest bracket
    interest_floor = min((player.gold // 10) * 10, 50)
    for slot in range(SHOP_SIZE):
        name = player.shop[slot]
        if not name:
            continue
        cost = NAME_TO_COST.get(name, 1)
        if cost > 2:
            continue
        if player.gold - cost >= interest_floor and player._find_empty_bench() is not None:
            buy_from_shop(player, pool, slot)

    # 5. Equip items on best units
    _equip_on_best_unit(player)

    return []


def slam_agent(player: 'Player', pool: 'ChampionPool',
               max_actions: int = 10) -> List[Action]:
    """Aggressive agent: equips items immediately, buys everything, levels fast.

    Strategy:
    1. Equip all items onto highest-value units (slam items)
    2. Buy everything affordable from shop
    3. Level up aggressively when gold > 20
    4. Refresh and buy more if gold allows
    5. Sell bench overflow (keep max 3 bench units)
    """
    # 1. Slam all items onto best units
    _equip_on_best_unit(player)

    # 2. Buy everything from shop
    for slot in range(SHOP_SIZE):
        name = player.shop[slot]
        if not name:
            continue
        cost = NAME_TO_COST.get(name, 1)
        if player.gold >= cost and player._find_empty_bench() is not None:
            buy_from_shop(player, pool, slot)

    # 3. Level up aggressively
    while player.gold > 20 and player.level < MAX_LEVEL:
        if not player.buy_xp():
            break

    # 4. Refresh and buy more
    if player.gold >= REFRESH_COST + 3:
        refresh_shop(player, pool)
        for slot in range(SHOP_SIZE):
            name = player.shop[slot]
            if not name:
                continue
            cost = NAME_TO_COST.get(name, 1)
            if player.gold >= cost and player._find_empty_bench() is not None:
                buy_from_shop(player, pool, slot)

    # 5. Sell bench overflow (keep max 3 on bench)
    bench_units = [(i, player.bench[i]) for i in range(BENCH_SIZE)
                   if player.bench[i] is not None]
    if len(bench_units) > 3:
        # Sort by cost ascending (sell cheapest first)
        bench_units.sort(key=lambda x: x[1].cost)
        for idx, _ in bench_units[:len(bench_units) - 3]:
            sell_unit(player, pool, 'bench', idx)

    return []


# ── Mixed Lobby Agent ───────────────────────────────────────────────────

AGENT_REGISTRY = {
    'random': fast_random_agent,
    'econ': econ_agent,
    'slam': slam_agent,
}


class MixedLobbyAgent:
    """Assigns different agent types to different players within a game.

    Each player gets a consistent agent for the whole game, drawn from
    a weighted distribution. This produces more realistic training data
    than pure random play.

    Usage:
        agent = MixedLobbyAgent({'random': 50, 'econ': 30, 'slam': 20})
        agent.assign_players()  # Call after seeding random
        game = TFTGame(agent_fn=agent)
    """

    def __init__(self, mix: dict = None):
        if mix is None:
            mix = {'random': 50, 'econ': 30, 'slam': 20}
        self._names = list(mix.keys())
        self._weights = [mix[n] for n in self._names]
        self._player_agents = {}

    def assign_players(self, num_players: int = 8):
        """Assign a random agent type to each player. Call after random.seed()."""
        self._player_agents = {}
        for pid in range(num_players):
            name = random.choices(self._names, self._weights, k=1)[0]
            self._player_agents[pid] = AGENT_REGISTRY[name]

    def __call__(self, player: 'Player', pool: 'ChampionPool',
                 max_actions: int = 10) -> List[Action]:
        agent_fn = self._player_agents.get(player.player_id, fast_random_agent)
        return agent_fn(player, pool, max_actions)
