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

    return False


def random_agent_actions(player: 'Player', pool: 'ChampionPool',
                         max_actions: int = 10) -> List[Action]:
    """Generate random legal actions for testing.

    Takes up to max_actions random actions, always ending with PASS.
    Prioritizes buys and levels over moves to make more interesting games.
    """
    executed = []
    for _ in range(max_actions):
        legal = get_legal_actions(player, pool)
        # Filter to just meaningful actions (not pass, limit moves)
        meaningful = [a for a in legal if a.action_type != ActionType.PASS]
        if not meaningful:
            break

        # Weight towards buys, levels, and item equips
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
            else:
                weights.append(1)

        action = random.choices(meaningful, weights=weights, k=1)[0]
        success = execute_action(action, player, pool)
        if success:
            executed.append(action)

    return executed
