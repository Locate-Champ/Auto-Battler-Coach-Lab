from __future__ import annotations

from coach.actions import ActionPlan, ItemEquipDetails, ItemSlamDetails
from coach.explain import Explanation, ScoreBreakdown, explain_action
from coach.scoring.features import champion_name
from coach.state import GameState

from .candidates import generate_candidates
from .execute import execute

__all__ = ["execute", "explain", "generate_candidates"]


def explain(state: GameState, action: ActionPlan, score: ScoreBreakdown) -> Explanation:
    base = explain_action(action, score)

    if isinstance(action.details, ItemSlamDetails):
        target = next(
            (u for u in (*state.board, *state.bench) if u.instance_id == action.details.target_unit_id),
            None,
        )
        target_name = champion_name(target.champion_id) if target is not None else action.details.target_unit_id
        first = f"Slam {action.details.resulting_item} on {target_name}"
        lines = (first, *base.lines[1:]) if base.lines else (first,)
        return Explanation(confidence=base.confidence, lines=lines, numbers=base.numbers)

    if isinstance(action.details, ItemEquipDetails):
        target = next(
            (u for u in (*state.board, *state.bench) if u.instance_id == action.details.target_unit_id),
            None,
        )
        target_name = champion_name(target.champion_id) if target is not None else action.details.target_unit_id
        first = f"Equip {action.details.item} on {target_name}"
        lines = (first, *base.lines[1:]) if base.lines else (first,)
        return Explanation(confidence=base.confidence, lines=lines, numbers=base.numbers)

    return base
