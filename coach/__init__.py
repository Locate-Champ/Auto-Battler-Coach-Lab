"""Planning-based coaching layer for TFT Coach.

This package implements a "planning with a critic" approach:
generate candidate actions, deterministically apply them, then score the
resulting next-states with a small set of interpretable terms.
"""

from .actions import DecisionType
from .coach import Coach
from .state import GameState, OpponentState, PlayerState, ShopUnit, UnitState

__all__ = [
    "Coach",
    "DecisionType",
    "GameState",
    "OpponentState",
    "PlayerState",
    "ShopUnit",
    "UnitState",
]
