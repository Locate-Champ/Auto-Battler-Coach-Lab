from __future__ import annotations

from coach.actions import ActionPlan, DecisionType, EconDetails, HoldDetails
from coach.state import GameState


def _action_id(details: EconDetails | HoldDetails) -> str:
    if isinstance(details, HoldDetails):
        return "econ:hold"
    return f"econ:{details.name}:{int(details.gold_spent)}:{int(details.levels_gained)}:{int(details.rolls)}"


def generate_candidates(state: GameState) -> list[ActionPlan]:
    actions: list[ActionPlan] = [
        ActionPlan(
            decision_type=DecisionType.ECON,
            action_id=_action_id(HoldDetails(note="Hold: keep gold for flexibility")),
            title="Hold econ",
            details=HoldDetails(note="Hold: keep gold for flexibility"),
            tags=("flex",),
        )
    ]

    # Simple, legal-ish econ candidates. These are intentionally conservative.
    details = EconDetails(name="Save (maintain interest)", gold_spent=0, levels_gained=0, rolls=0)
    actions.append(
        ActionPlan(
            decision_type=DecisionType.ECON,
            action_id=_action_id(details),
            title=details.name,
            details=details,
            tags=("greed",),
        )
    )

    if state.player.gold >= 4 and state.player.level < 10:
        details = EconDetails(name="Buy XP (4g)", gold_spent=4, levels_gained=0, rolls=0)
        actions.append(
            ActionPlan(
                decision_type=DecisionType.ECON,
                action_id=_action_id(details),
                title=details.name,
                details=details,
                tags=("greed",),
            )
        )

    if state.player.gold >= 8 and state.player.level < 10:
        details = EconDetails(name="Buy XP (8g)", gold_spent=8, levels_gained=0, rolls=0)
        actions.append(
            ActionPlan(
                decision_type=DecisionType.ECON,
                action_id=_action_id(details),
                title=details.name,
                details=details,
                tags=("greed",),
            )
        )

    if state.player.gold >= 16 and state.player.level < 10 and state.stage_number >= 4:
        details = EconDetails(name="Push level (est. 1 level)", gold_spent=16, levels_gained=1, rolls=0)
        actions.append(
            ActionPlan(
                decision_type=DecisionType.ECON,
                action_id=_action_id(details),
                title=details.name,
                details=details,
                tags=("greed",),
            )
        )

    # Basic roll lines. Scored via short-horizon lookahead (pool-aware sampling).
    if state.player.gold >= 4 and state.stage_number >= 2:
        details = EconDetails(name="Roll 2x (4g)", gold_spent=0, levels_gained=0, rolls=2)
        actions.append(
            ActionPlan(
                decision_type=DecisionType.ECON,
                action_id=_action_id(details),
                title=details.name,
                details=details,
                tags=("tempo", "stabilize"),
            )
        )

    if state.player.gold >= 12 and state.stage_number >= 3:
        details = EconDetails(name="Roll 6x (12g)", gold_spent=0, levels_gained=0, rolls=6)
        actions.append(
            ActionPlan(
                decision_type=DecisionType.ECON,
                action_id=_action_id(details),
                title=details.name,
                details=details,
                tags=("tempo", "stabilize"),
            )
        )

    # Stabilize if low HP or late game: spend down to a floor.
    if state.player.gold >= 20 and (state.player.hp <= 40 or state.stage_number >= 4):
        floor = 20 if state.player.gold >= 30 else 10
        rolls = max(0, (state.player.gold - floor) // 2)
        rolls = min(rolls, 30)
        if rolls >= 4:
            details = EconDetails(name=f"Stabilize: roll to {floor}g (~{rolls}x)", gold_spent=0, levels_gained=0, rolls=int(rolls))
            actions.append(
                ActionPlan(
                    decision_type=DecisionType.ECON,
                    action_id=_action_id(details),
                    title=details.name,
                    details=details,
                    tags=("tempo", "stabilize"),
                )
            )

    return actions
