from __future__ import annotations

import hashlib

from coach.actions import ActionPlan, DecisionType, HoldDetails, PositioningDetails
from coach.rules import is_valid_board_pos
from coach.scoring.features import detect_carry
from coach.state import GameState, UnitState


_BACKLINE_PREF = [(0, 0), (0, 3), (0, 6), (1, 1), (1, 5), (1, 3), (0, 2), (0, 4)]
_FRONTLINE_PREF = [(3, 3), (3, 2), (3, 4), (2, 3), (3, 1), (3, 5), (2, 2), (2, 4), (2, 1), (2, 5)]


def _canonical(assignments: list[tuple[str, int, int]]) -> tuple[tuple[str, int, int], ...]:
    return tuple(sorted(assignments, key=lambda x: x[0]))


def _build_assignment(
    units: list[UnitState],
    *,
    carry_pos: tuple[int, int],
    frontline_pref: list[tuple[int, int]] = _FRONTLINE_PREF,
    backline_pref: list[tuple[int, int]] = _BACKLINE_PREF,
) -> tuple[tuple[str, int, int], ...]:
    carry = detect_carry(tuple(units))
    carry_id = carry.instance_id if carry is not None else units[0].instance_id

    taken: set[tuple[int, int]] = set()
    assignments: list[tuple[str, int, int]] = []

    def _take(unit_id: str, pos: tuple[int, int]) -> None:
        if pos in taken:
            return
        taken.add(pos)
        assignments.append((unit_id, pos[0], pos[1]))

    # Place carry first.
    if is_valid_board_pos(carry_pos[0], carry_pos[1]):
        _take(carry_id, carry_pos)

    # Split remaining units by current row heuristic: row>=2 treated as frontline.
    remaining = [u for u in units if u.instance_id != carry_id]
    frontline = [u for u in remaining if u.position is not None and u.position[0] >= 2]
    backline = [u for u in remaining if u not in frontline]

    # Fill frontline, then backline.
    for u in frontline:
        for pos in frontline_pref:
            if pos not in taken:
                _take(u.instance_id, pos)
                break

    for u in backline:
        for pos in backline_pref:
            if pos not in taken:
                _take(u.instance_id, pos)
                break

    # Any remaining units: fill any free hex.
    for u in remaining:
        if any(a[0] == u.instance_id for a in assignments):
            continue
        for row in range(4):
            for col in range(7):
                pos = (row, col)
                if pos in taken:
                    continue
                _take(u.instance_id, pos)
                break
            else:
                continue
            break

    return _canonical(assignments)


def _action_id(assignments: tuple[tuple[str, int, int], ...]) -> str:
    h = hashlib.sha1(repr(assignments).encode("utf-8")).hexdigest()[:10]
    return f"position:{h}"


def generate_candidates(state: GameState) -> list[ActionPlan]:
    actions: list[ActionPlan] = [
        ActionPlan(
            decision_type=DecisionType.POSITION,
            action_id="position:hold",
            title="Hold positioning",
            details=HoldDetails(note="Hold: keep current positioning"),
            tags=("flex",),
        )
    ]

    units = [u for u in state.board if u.location == "board"]
    if not units:
        return actions

    # If any unit lacks a position, avoid suggesting positional changes.
    if any(u.position is None for u in units):
        return actions

    templates: list[tuple[str, tuple[int, int], list[tuple[int, int]], list[tuple[int, int]]]] = [
        ("Corner carry (left)", (0, 0), _FRONTLINE_PREF, _BACKLINE_PREF),
        ("Corner carry (right)", (0, 6), _FRONTLINE_PREF, _BACKLINE_PREF),
        ("Backline carry (center)", (0, 3), _FRONTLINE_PREF, _BACKLINE_PREF),
        ("Second row carry (left)", (1, 0), _FRONTLINE_PREF, _BACKLINE_PREF),
        ("Second row carry (right)", (1, 6), _FRONTLINE_PREF, _BACKLINE_PREF),
        ("Second row carry (center)", (1, 3), _FRONTLINE_PREF, _BACKLINE_PREF),
        (
            "Clumped frontline (center)",
            (0, 3),
            [(3, 3), (3, 2), (3, 4), (2, 3), (2, 2), (2, 4)],
            _BACKLINE_PREF,
        ),
        (
            "Spread frontline (wide)",
            (0, 3),
            [(3, 0), (3, 6), (3, 2), (3, 4), (2, 1), (2, 5)],
            _BACKLINE_PREF,
        ),
    ]

    seen: set[tuple[tuple[str, int, int], ...]] = set()

    def _add(name: str, assignments: tuple[tuple[str, int, int], ...]) -> None:
        if not assignments:
            return
        if assignments in seen:
            return
        seen.add(assignments)
        details = PositioningDetails(name=name, assignments=assignments)
        actions.append(
            ActionPlan(
                decision_type=DecisionType.POSITION,
                action_id=_action_id(assignments),
                title=name,
                details=details,
                tags=("tempo",),
            )
        )

    def _perturb(name: str, base: tuple[tuple[str, int, int], ...]) -> None:
        # Generate a small, deterministic set of local perturbations.
        # 1) Shift the detected carry horizontally if possible.
        if not base:
            return
        carry = detect_carry(tuple(units))
        carry_id = carry.instance_id if carry is not None else None
        if carry_id is None:
            return

        pos_map = {uid: (r, c) for uid, r, c in base}
        carry_pos = pos_map.get(carry_id)
        if carry_pos is None:
            return
        row0, col0 = carry_pos
        occupied = {(r, c) for _, r, c in base}
        for dc in (-1, 1):
            new_col = col0 + dc
            if not is_valid_board_pos(row0, new_col):
                continue
            if (row0, new_col) in occupied:
                continue
            moved = [(uid, r, c) if uid != carry_id else (uid, row0, new_col) for uid, r, c in base]
            _add(f"{name} (shift {dc:+d})", _canonical(moved))

        # 2) Swap the first two frontline-looking units.
        frontline = [(uid, r, c) for uid, r, c in base if r >= 2]
        if len(frontline) >= 2:
            a = frontline[0]
            b = frontline[1]
            swapped = []
            for uid, r, c in base:
                if uid == a[0]:
                    swapped.append((uid, b[1], b[2]))
                elif uid == b[0]:
                    swapped.append((uid, a[1], a[2]))
                else:
                    swapped.append((uid, r, c))
            _add(f"{name} (swap frontline)", _canonical(swapped))

    for name, pos, front_pref, back_pref in templates:
        base = _build_assignment(units, carry_pos=pos, frontline_pref=front_pref, backline_pref=back_pref)
        _add(name, base)
        _perturb(name, base)

    return actions
