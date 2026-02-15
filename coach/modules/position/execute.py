from __future__ import annotations

from dataclasses import replace

from coach.actions import ActionPlan, HoldDetails, PositioningDetails
from coach.rules import is_valid_board_pos
from coach.state import GameState, UnitState


def execute(state: GameState, action: ActionPlan) -> GameState:
    if isinstance(action.details, HoldDetails):
        return state

    if not isinstance(action.details, PositioningDetails):
        return state

    assignment_map: dict[str, tuple[int, int]] = {}
    for unit_id, row, col in action.details.assignments:
        if not is_valid_board_pos(row, col):
            continue
        assignment_map[unit_id] = (row, col)

    new_board: list[UnitState] = []
    taken: set[tuple[int, int]] = set()
    for u in state.board:
        if u.location != "board":
            new_board.append(u)
            continue
        pos = assignment_map.get(u.instance_id, u.position)
        if pos is None or pos in taken:
            # Leave as-is if collision; candidate generation should avoid this.
            new_board.append(u)
            continue
        taken.add(pos)
        new_board.append(u.with_position(pos, location="board"))

    return replace(state, board=tuple(new_board))
