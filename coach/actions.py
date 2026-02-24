from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DecisionType(str, Enum):
    SHOP = "shop"
    ITEMS = "items"
    POSITION = "position"
    ECON = "econ"


@dataclass(frozen=True, slots=True)
class HoldDetails:
    note: Optional[str] = None


# -- Items --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ItemSlamDetails:
    component_a: str
    component_b: str
    resulting_item: str
    target_unit_id: str


@dataclass(frozen=True, slots=True)
class ItemEquipDetails:
    item: str
    target_unit_id: str


# -- Position -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PositioningDetails:
    name: str
    assignments: tuple[tuple[str, int, int], ...]  # (unit_id, row, col)


# -- Econ ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EconDetails:
    name: str
    gold_spent: int = 0
    levels_gained: int = 0
    rolls: int = 0


# -- Shop ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShopBuyDetails:
    name: str
    champion_id: str
    cost: int


ActionDetails = (
    HoldDetails
    | ItemSlamDetails
    | ItemEquipDetails
    | PositioningDetails
    | EconDetails
    | ShopBuyDetails
)


@dataclass(frozen=True, slots=True)
class ActionPlan:
    decision_type: DecisionType
    action_id: str
    title: str
    details: ActionDetails
    constraints: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
