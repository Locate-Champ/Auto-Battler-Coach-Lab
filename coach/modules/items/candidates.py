from __future__ import annotations

from itertools import combinations

from coach.actions import (
    ActionPlan,
    DecisionType,
    HoldDetails,
    ItemEquipDetails,
    ItemSlamDetails,
)
from coach.rules import combine_components, is_component, can_equip_more_items
from coach.scoring.features import detect_carry
from coach.scoring.archetypes import ArchetypeLibrary
from coach.state import GameState


_DEFENSIVE_ITEM_MARKERS = (
    "Bramble",
    "DragonsClaw",
    "Warmogs",
    "Gargoyle",
    "Steadfast",
    "Evenshroud",
    "Sunfire",
    "Crownguard",
    "ProtectorsVow",
    "SpiritVisage",
)

_ARCHETYPES = ArchetypeLibrary()


def _is_defensive_item(item_id: str) -> bool:
    return any(m in item_id for m in _DEFENSIVE_ITEM_MARKERS)


def _action_id_for_items(details: ItemEquipDetails | ItemSlamDetails | HoldDetails) -> str:
    if isinstance(details, HoldDetails):
        return "items:hold"
    if isinstance(details, ItemEquipDetails):
        return f"items:equip:{details.item}:{details.target_unit_id}"
    a, b = sorted((details.component_a, details.component_b))
    return f"items:slam:{a}+{b}->{details.resulting_item}:{details.target_unit_id}"


def generate_candidates(state: GameState) -> list[ActionPlan]:
    actions: list[ActionPlan] = [
        ActionPlan(
            decision_type=DecisionType.ITEMS,
            action_id=_action_id_for_items(HoldDetails(note="Hold: keep options open")),
            title="Hold items",
            details=HoldDetails(note="Hold: keep options open"),
            tags=("greed", "flex"),
        )
    ]

    board_units = [u for u in state.board if u.location == "board" and can_equip_more_items(len(u.items))]
    if not board_units:
        return actions

    best_match = _ARCHETYPES.closest(state, top_n=1)
    archetype_items: set[str] = set()
    if best_match:
        archetype_items = set(_ARCHETYPES.suggest_items_for_archetype(best_match[0].archetype.archetype_id))

    carry = detect_carry(tuple(board_units))
    carry_id = carry.instance_id if carry is not None else board_units[0].instance_id
    suggested = _ARCHETYPES.suggest_carry_candidates(state, top_n=3)
    if suggested:
        for u in board_units:
            if u.champion_id in suggested:
                carry_id = u.instance_id
                break

    components = [i for i in state.items if is_component(i)]
    completed_items = [i for i in state.items if not is_component(i)]

    # Equip completed items already on bench.
    seen: set[tuple[str, str]] = set()
    preferred: list[ActionPlan] = []
    others: list[ActionPlan] = []
    for item in completed_items[:10]:
        target_id = carry_id
        if _is_defensive_item(item):
            front = max(
                (u for u in board_units if u.position is not None),
                key=lambda u: u.position[0],
                default=None,
            )
            if front is not None:
                target_id = front.instance_id
        key = (item, target_id)
        if key in seen:
            continue
        seen.add(key)
        details = ItemEquipDetails(item=item, target_unit_id=target_id)
        is_archetype_item = item in archetype_items
        (preferred if is_archetype_item else others).append(
            ActionPlan(
                decision_type=DecisionType.ITEMS,
                action_id=_action_id_for_items(details),
                title=f"Equip {item}",
                details=details,
                tags=("tempo", "archetype") if is_archetype_item else ("tempo",),
            )
        )

    # Slam craftable items from components.
    if len(components) >= 2:
        for a, b in combinations(components, 2):
            crafted = combine_components(a, b)
            if not crafted:
                continue
            # Target: carry by default, defensive items to the front-most unit.
            target_id = carry_id
            if _is_defensive_item(crafted):
                front = max(
                    (u for u in board_units if u.position is not None),
                    key=lambda u: u.position[0],
                    default=None,
                )
                if front is not None:
                    target_id = front.instance_id
            key = (crafted, target_id)
            if key in seen:
                continue
            seen.add(key)
            details = ItemSlamDetails(
                component_a=a,
                component_b=b,
                resulting_item=crafted,
                target_unit_id=target_id,
            )
            is_archetype_item = crafted in archetype_items
            (preferred if is_archetype_item else others).append(
                ActionPlan(
                    decision_type=DecisionType.ITEMS,
                    action_id=_action_id_for_items(details),
                    title=f"Slam {crafted}",
                    details=details,
                    tags=("tempo", "slam", "archetype") if is_archetype_item else ("tempo", "slam"),
                )
            )

    actions.extend(preferred)
    actions.extend(others)
    return actions
