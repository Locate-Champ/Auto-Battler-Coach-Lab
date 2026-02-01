"""Lightweight combat engine primitives."""

from .combat_loop import (
    CombatResult,
    CombatRNG,
    Position,
    StateType,
    Stats,
    UnitState,
    World,
    run_combat,
)

__all__ = [
    "CombatResult",
    "CombatRNG",
    "Position",
    "StateType",
    "Stats",
    "UnitState",
    "World",
    "run_combat",
]
