from __future__ import annotations

from coach.actions import ActionPlan
from coach.explain import Explanation, ScoreBreakdown, explain_action
from coach.state import GameState

from .candidates import generate_candidates
from .execute import execute

__all__ = ["execute", "explain", "generate_candidates"]


def explain(state: GameState, action: ActionPlan, score: ScoreBreakdown) -> Explanation:
    return explain_action(action, score)
