from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from simulator.game.constants import (
    BENCH_SIZE,
    BOARD_COLS,
    BOARD_ROWS,
    ITEM_BENCH_SIZE,
    MAX_ITEMS_PER_UNIT,
)


@dataclass(frozen=True, slots=True)
class UnitState:
    instance_id: str
    champion_id: str  # API name, e.g. "TFT16_Ekko"
    star_level: int = 1
    items: tuple[str, ...] = ()
    position: Optional[tuple[int, int]] = None  # (row, col) if on board
    location: str = "board"  # "board" | "bench"

    def with_items(self, items: Iterable[str]) -> "UnitState":
        return UnitState(
            instance_id=self.instance_id,
            champion_id=self.champion_id,
            star_level=self.star_level,
            items=tuple(items),
            position=self.position,
            location=self.location,
        )

    def with_position(self, position: Optional[tuple[int, int]], location: str) -> "UnitState":
        return UnitState(
            instance_id=self.instance_id,
            champion_id=self.champion_id,
            star_level=self.star_level,
            items=self.items,
            position=position,
            location=location,
        )


@dataclass(frozen=True, slots=True)
class ShopUnit:
    champion_id: str  # API name
    cost: int


@dataclass(frozen=True, slots=True)
class PlayerState:
    level: int
    hp: int
    gold: int
    xp: Optional[int] = None
    win_streak: int = 0
    loss_streak: int = 0

    @property
    def interest(self) -> int:
        # TFT interest is 1g per 10g saved, capped at 5g.
        return min(max(self.gold, 0) // 10, 5)

    @property
    def streak(self) -> int:
        # Signed streak representation used by model pipeline: win - loss.
        return int(self.win_streak) - int(self.loss_streak)


@dataclass(frozen=True, slots=True)
class OpponentState:
    opponent_id: str
    board: tuple[UnitState, ...] = ()
    augments: tuple[str, ...] = ()
    level: Optional[int] = None
    hp: Optional[int] = None


@dataclass(frozen=True, slots=True)
class GameState:
    stage: str  # e.g. "4-2"
    player: PlayerState
    board: tuple[UnitState, ...]
    bench: tuple[UnitState, ...] = ()
    shop: tuple[ShopUnit, ...] = ()
    items: tuple[str, ...] = ()  # unassigned components + completed items
    augments: tuple[str, ...] = ()
    traits: tuple[tuple[str, int], ...] = ()
    opponents: tuple[OpponentState, ...] = ()
    notes: tuple[str, ...] = ()
    schema_version: int = 1

    @property
    def stage_number(self) -> int:
        try:
            return int(self.stage.split("-")[0])
        except (ValueError, IndexError):
            return 0

    @property
    def round_number(self) -> int:
        try:
            return int(self.stage.split("-")[1])
        except (ValueError, IndexError):
            return 0

    def traits_dict(self) -> dict[str, int]:
        return {name: count for name, count in self.traits}


def validate_coach_state(state: GameState) -> list[str]:
    errors: list[str] = []

    if not isinstance(state.stage, str) or not state.stage:
        errors.append("stage: missing/empty")

    level = int(getattr(state.player, "level", 0) or 0)
    if level < 1 or level > 10:
        errors.append(f"player.level: out of range ({level})")

    hp = int(getattr(state.player, "hp", 0) or 0)
    if hp < 0:
        errors.append(f"player.hp: negative ({hp})")

    gold = int(getattr(state.player, "gold", 0) or 0)
    if gold < 0:
        errors.append(f"player.gold: negative ({gold})")

    instance_ids: set[str] = set()
    taken_positions: set[tuple[int, int]] = set()

    board_units = [u for u in state.board if getattr(u, "location", None) == "board"]
    if len(board_units) > level:
        errors.append(f"board: exceeds cap (board={len(board_units)} level={level})")

    for u in state.board:
        if not isinstance(u.instance_id, str) or not u.instance_id:
            errors.append("unit.instance_id: missing/empty (board)")
            continue
        if u.instance_id in instance_ids:
            errors.append(f"unit.instance_id: duplicate ({u.instance_id})")
        instance_ids.add(u.instance_id)

        if not isinstance(u.champion_id, str) or not u.champion_id:
            errors.append(f"unit.champion_id: missing/empty ({u.instance_id})")

        items = u.items or ()
        if len(items) > MAX_ITEMS_PER_UNIT:
            errors.append(f"unit.items: exceeds max ({u.instance_id} items={len(items)})")

        if u.location != "board":
            errors.append(
                f"unit.location: expected 'board' ({u.instance_id} location={u.location})"
            )

        if u.position is None:
            errors.append(f"unit.position: missing ({u.instance_id})")
            continue
        row, col = u.position
        if not (0 <= int(row) < BOARD_ROWS and 0 <= int(col) < BOARD_COLS):
            errors.append(f"unit.position: out of bounds ({u.instance_id} pos={u.position})")
            continue
        if u.position in taken_positions:
            errors.append(f"unit.position: collision ({u.instance_id} pos={u.position})")
        taken_positions.add(u.position)

    if len(state.bench) > BENCH_SIZE:
        errors.append(f"bench: exceeds cap ({len(state.bench)} > {BENCH_SIZE})")

    for u in state.bench:
        if not isinstance(u.instance_id, str) or not u.instance_id:
            errors.append("unit.instance_id: missing/empty (bench)")
            continue
        if u.instance_id in instance_ids:
            errors.append(f"unit.instance_id: duplicate ({u.instance_id})")
        instance_ids.add(u.instance_id)

        items = u.items or ()
        if len(items) > MAX_ITEMS_PER_UNIT:
            errors.append(f"unit.items: exceeds max ({u.instance_id} items={len(items)})")

        if u.location != "bench":
            errors.append(
                f"unit.location: expected 'bench' ({u.instance_id} location={u.location})"
            )
        if u.position is not None:
            errors.append(
                f"unit.position: expected None on bench ({u.instance_id} pos={u.position})"
            )

    if len(state.items) > ITEM_BENCH_SIZE:
        errors.append(f"items: exceeds cap ({len(state.items)} > {ITEM_BENCH_SIZE})")

    for su in state.shop:
        if not isinstance(su.champion_id, str) or not su.champion_id:
            errors.append("shop_unit.champion_id: missing/empty")
        cost = int(getattr(su, "cost", 0) or 0)
        if cost < 0:
            errors.append(f"shop_unit.cost: negative ({su.champion_id} cost={cost})")

    return errors
