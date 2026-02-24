from __future__ import annotations

from typing import Optional

from simulator.game.constants import (
    BOARD_COLS,
    BOARD_ROWS,
    MAX_ITEMS_PER_UNIT,
)
from simulator.game.constants import (
    combine_items as _combine_items,
)
from simulator.game.constants import (
    is_component as _is_component,
)

_COMPONENT_TFT_ITEM_TO_UNDERSCORE = {
    "TFT_Item_BFSword": "BF_Sword",
    "TFT_Item_RecurveBow": "Recurve_Bow",
    "TFT_Item_NeedlesslyLargeRod": "Needlessly_Large_Rod",
    "TFT_Item_TearOfTheGoddess": "Tear_of_the_Goddess",
    "TFT_Item_ChainVest": "Chain_Vest",
    "TFT_Item_NegatronCloak": "Negatron_Cloak",
    "TFT_Item_GiantsBelt": "Giants_Belt",
    "TFT_Item_SparringGloves": "Sparring_Gloves",
    "TFT_Item_Spatula": "Spatula",
}


def normalize_component_id(item: str) -> str:
    # Crafting recipes in simulator.game.constants use underscore component ids.
    return _COMPONENT_TFT_ITEM_TO_UNDERSCORE.get(item, item)


def is_component(item: str) -> bool:
    return _is_component(normalize_component_id(item))


def combine_components(component_a: str, component_b: str) -> Optional[str]:
    return _combine_items(normalize_component_id(component_a), normalize_component_id(component_b))


def is_valid_board_pos(row: int, col: int) -> bool:
    return 0 <= row < BOARD_ROWS and 0 <= col < BOARD_COLS


def can_equip_more_items(num_items: int) -> bool:
    return num_items < MAX_ITEMS_PER_UNIT
