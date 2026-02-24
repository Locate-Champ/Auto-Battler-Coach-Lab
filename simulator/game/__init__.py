"""TFT Game Loop - Set 16 game simulation wrapping the combat engine.

Usage:
    from simulator.game import TFTGame
    game = TFTGame(seed=42)
    placements = game.play()
"""

from .actions import execute_action, get_legal_actions, random_agent_actions
from .champion_pool import ChampionPool
from .game import TFTGame
from .player import Player
from .types import Action, ActionType, ChampionInstance, GamePhase, RoundResult

__all__ = [
    "TFTGame",
    "Player",
    "ChampionPool",
    "Action",
    "ActionType",
    "GamePhase",
    "ChampionInstance",
    "RoundResult",
    "get_legal_actions",
    "execute_action",
    "random_agent_actions",
]
