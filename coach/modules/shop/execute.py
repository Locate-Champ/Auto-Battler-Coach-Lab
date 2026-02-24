from __future__ import annotations

from dataclasses import replace

from coach.actions import ActionPlan, HoldDetails, ShopBuyDetails
from coach.state import GameState, PlayerState, UnitState
from simulator.game.constants import BENCH_SIZE


def execute(state: GameState, action: ActionPlan) -> GameState:
    if isinstance(action.details, HoldDetails):
        return state

    if not isinstance(action.details, ShopBuyDetails):
        return state

    cid = action.details.champion_id
    if not isinstance(cid, str) or not cid:
        return state

    cost = int(action.details.cost)
    if cost <= 0 or state.player.gold < cost:
        return state

    # Spend gold, remove one instance from shop, and add the bought unit to bench.
    gold_after = max(0, int(state.player.gold) - cost)
    player = PlayerState(
        level=state.player.level,
        hp=state.player.hp,
        gold=gold_after,
        xp=state.player.xp,
        win_streak=state.player.win_streak,
        loss_streak=state.player.loss_streak,
    )

    removed = False
    new_shop = []
    for su in state.shop:
        if not removed and su.champion_id == cid:
            removed = True
            continue
        new_shop.append(su)

    board = list(state.board)
    bench = list(state.bench)
    items = list(state.items)

    bench.append(
        UnitState(
            instance_id=f"buy_{cid}_{len(bench)}", champion_id=cid, star_level=1, location="bench"
        )
    )

    def _remove_unit(unit_id: str) -> UnitState | None:
        for i, u in enumerate(board):
            if u.instance_id == unit_id:
                return board.pop(i)
        for i, u in enumerate(bench):
            if u.instance_id == unit_id:
                return bench.pop(i)
        return None

    def _combine(star_level: int) -> bool:
        candidates: list[UnitState] = [
            u for u in board if u.champion_id == cid and u.star_level == star_level
        ]
        candidates.extend(u for u in bench if u.champion_id == cid and u.star_level == star_level)
        if len(candidates) < 3:
            return False

        # Prefer upgrading a board unit (and/or one holding items).
        candidates.sort(key=lambda u: (u.location == "board", len(u.items)), reverse=True)
        base = candidates[0]

        others = [u for u in candidates[1:]]
        others.sort(key=lambda u: (u.location != "bench", len(u.items)))
        consume = others[:2]

        base_removed = _remove_unit(base.instance_id)
        if base_removed is None:
            return False
        consumed_removed = []
        for u in consume:
            removed_u = _remove_unit(u.instance_id)
            if removed_u is not None:
                consumed_removed.append(removed_u)

        merged = list(base_removed.items)
        for u in consumed_removed:
            merged.extend(u.items)
        if len(merged) > 3:
            items.extend(merged[3:])
            merged = merged[:3]

        upgraded = UnitState(
            instance_id=base_removed.instance_id,
            champion_id=cid,
            star_level=star_level + 1,
            items=tuple(merged),
            position=base_removed.position,
            location=base_removed.location,
        )
        if upgraded.location == "board":
            board.append(upgraded)
        else:
            bench.append(upgraded)
        return True

    # Chain-combine for this champion only.
    while True:
        if _combine(1):
            continue
        if _combine(2):
            continue
        break

    if len(bench) > BENCH_SIZE:
        return state

    return replace(
        state,
        player=player,
        shop=tuple(new_shop),
        board=tuple(board),
        bench=tuple(bench),
        items=tuple(items),
    )
