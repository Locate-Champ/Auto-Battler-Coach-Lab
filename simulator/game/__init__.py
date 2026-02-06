"""TFT Game Loop - Set 16 game simulation wrapping the combat engine.

Usage:
    from simulator.game import TFTGame
    game = TFTGame(seed=42)
    placements = game.play()
"""

from .game import TFTGame
from .player import Player
from .champion_pool import ChampionPool
from .types import Action, ActionType, GamePhase, ChampionInstance, RoundResult
from .actions import get_legal_actions, execute_action, random_agent_actions

__all__ = [
    'TFTGame',
    'Player',
    'ChampionPool',
    'Action',
    'ActionType',
    'GamePhase',
    'ChampionInstance',
    'RoundResult',
    'get_legal_actions',
    'execute_action',
    'random_agent_actions',
]
