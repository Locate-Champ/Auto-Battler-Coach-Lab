from __future__ import annotations

from dataclasses import replace

from coach.actions import ActionPlan, HoldDetails, ItemEquipDetails, ItemSlamDetails
from coach.rules import can_equip_more_items
from coach.state import GameState, UnitState


def _remove_once(items: list[str], value: str) -> bool:
    try:
        items.remove(value)
        return True
    except ValueError:
        return False


def _replace_unit(units: tuple[UnitState, ...], unit_id: str, new_unit: UnitState) -> tuple[UnitState, ...]:
    out = []
    replaced = False
    for u in units:
        if u.instance_id == unit_id:
            out.append(new_unit)
            replaced = True
        else:
            out.append(u)
    return tuple(out) if replaced else units


def execute(state: GameState, action: ActionPlan) -> GameState:
    if isinstance(action.details, HoldDetails):
        return state

    if isinstance(action.details, ItemEquipDetails):
        items = list(state.items)
        if not _remove_once(items, action.details.item):
            return state

        target = next((u for u in state.board if u.instance_id == action.details.target_unit_id), None)
        if target is None:
            return state
        if not can_equip_more_items(len(target.items)):
            return state

        updated = target.with_items((*target.items, action.details.item))
        board = _replace_unit(state.board, target.instance_id, updated)
        return replace(state, board=board, items=tuple(items))

    if isinstance(action.details, ItemSlamDetails):
        items = list(state.items)
        if not _remove_once(items, action.details.component_a):
            return state
        if not _remove_once(items, action.details.component_b):
            # Restore for determinism.
            items.append(action.details.component_a)
            return state

        target = next((u for u in state.board if u.instance_id == action.details.target_unit_id), None)
        if target is None:
            return state
        if not can_equip_more_items(len(target.items)):
            return state

        updated = target.with_items((*target.items, action.details.resulting_item))
        board = _replace_unit(state.board, target.instance_id, updated)
        return replace(state, board=board, items=tuple(items))

    return state
