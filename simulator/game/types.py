"""Shared data structures for the TFT game loop."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict, Any

from .constants import SELL_VALUES


class GamePhase(Enum):
    MINION = "minion"
    PLANNING = "planning"
    COMBAT = "combat"
    CAROUSEL = "carousel"


class ActionType(Enum):
    BUY = "buy"
    SELL = "sell"
    MOVE = "move"
    LEVEL = "level"
    REFRESH = "refresh"
    EQUIP_ITEM = "equip_item"
    CHOOSE_AUGMENT = "choose_augment"
    PLACE_TOWER = "place_tower"
    PLACE_SOLDIER = "place_soldier"
    PASS = "pass"


@dataclass(slots=True)
class Action:
    """An action a player can take during the planning phase."""
    action_type: ActionType
    args: Tuple = ()

    @staticmethod
    def buy(shop_slot: int) -> 'Action':
        return Action(ActionType.BUY, (shop_slot,))

    @staticmethod
    def sell(position: Tuple[int, ...]) -> 'Action':
        """Sell from board (row, col) or bench (bench_idx,)."""
        return Action(ActionType.SELL, position)

    @staticmethod
    def move(from_pos: Tuple[int, ...], to_pos: Tuple[int, ...]) -> 'Action':
        return Action(ActionType.MOVE, (from_pos, to_pos))

    @staticmethod
    def level() -> 'Action':
        return Action(ActionType.LEVEL)

    @staticmethod
    def refresh() -> 'Action':
        return Action(ActionType.REFRESH)

    @staticmethod
    def equip_item(item_idx: int, unit_pos: Tuple[int, ...]) -> 'Action':
        return Action(ActionType.EQUIP_ITEM, (item_idx, unit_pos))

    @staticmethod
    def choose_augment(choice_idx: int) -> 'Action':
        """Choose an augment from the offered options (0, 1, or 2)."""
        return Action(ActionType.CHOOSE_AUGMENT, (choice_idx,))

    @staticmethod
    def place_tower(row: int, col: int) -> 'Action':
        """Place the Freljord tower at (row, col)."""
        return Action(ActionType.PLACE_TOWER, (row, col))

    @staticmethod
    def place_soldier(row: int, col: int) -> 'Action':
        """Place an Azir soldier at (row, col)."""
        return Action(ActionType.PLACE_SOLDIER, (row, col))

    @staticmethod
    def pass_action() -> 'Action':
        return Action(ActionType.PASS)


@dataclass(slots=True)
class ChampionInstance:
    """A champion instance on board, bench, or in shop."""
    name: str           # Lowercase key (e.g., 'jinx')
    api_name: str       # API name (e.g., 'TFT16_Jinx')
    cost: int           # Base cost (1-5)
    star_level: int     # 1, 2, or 3
    items: List[str] = field(default_factory=list)

    @property
    def sell_value(self) -> int:
        return SELL_VALUES[self.cost - 1][self.star_level - 1]


@dataclass(slots=True)
class RoundResult:
    """Result of a combat round between two players."""
    winner_id: int
    loser_id: int
    survivors: int          # Number of surviving units on winning side
    combat_time: float
    damage_to_loser: int    # HP damage dealt to loser
    is_draw: bool = False
