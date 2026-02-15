from __future__ import annotations

from dataclasses import replace

from coach.actions import ActionPlan, EconDetails, HoldDetails
from coach.state import GameState, PlayerState


def execute(state: GameState, action: ActionPlan) -> GameState:
    if isinstance(action.details, HoldDetails):
        return state

    if not isinstance(action.details, EconDetails):
        return state

    roll_spend = max(0, int(action.details.rolls)) * 2
    gold_after = max(0, state.player.gold - int(action.details.gold_spent) - roll_spend)
    level_after = min(10, state.player.level + int(action.details.levels_gained))

    player = PlayerState(
        level=level_after,
        hp=state.player.hp,
        gold=gold_after,
        xp=state.player.xp,
        win_streak=state.player.win_streak,
        loss_streak=state.player.loss_streak,
    )
    return replace(state, player=player)
