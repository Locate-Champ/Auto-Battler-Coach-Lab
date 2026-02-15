from __future__ import annotations

from coach.actions import ActionPlan, DecisionType, HoldDetails, ShopBuyDetails
from coach.scoring.features import champion_cost, champion_name, copy_counts
from coach.scoring.archetypes import ArchetypeLibrary
from coach.state import GameState
from simulator.game.constants import BENCH_SIZE


_ARCHETYPES = ArchetypeLibrary()

def generate_candidates(state: GameState) -> list[ActionPlan]:
    actions: list[ActionPlan] = [
        ActionPlan(
            decision_type=DecisionType.SHOP,
            action_id="shop:hold",
            title="Hold shop",
            details=HoldDetails(note="Hold: keep current shop"),
            tags=("flex",),
        )
    ]

    if not state.shop:
        return actions

    if len(state.bench) >= BENCH_SIZE:
        return actions

    counts = copy_counts(tuple((*state.board, *state.bench)))
    gold = int(state.player.gold)

    best_match = _ARCHETYPES.closest(state, top_n=1)
    best_units = set(best_match[0].archetype.units) if best_match else set()

    scored: list[tuple[int, ActionPlan]] = []
    for su in state.shop[:10]:
        cid = su.champion_id
        cost = int(su.cost) if su.cost is not None else int(champion_cost(cid))
        if cost <= 0 or cost > gold:
            continue

        owned = int(counts.get(cid, 0))
        if owned < 3:
            needed = 3 - owned
            star_label = "2★"
        elif owned < 9:
            needed = 9 - owned
            star_label = "3★"
        else:
            needed = 999
            star_label = ""

        prio = 100 * cost
        if needed == 1:
            prio += 1000
        if cid in best_units:
            prio += 150

        title = f"Buy {champion_name(cid)} ({cost}g)"
        if needed == 1 and star_label:
            title = f"{title} -> {star_label}"

        scored.append(
            (
                prio,
                ActionPlan(
                    decision_type=DecisionType.SHOP,
                    action_id=f"shop:buy:{cid}",
                    title=title,
                    details=ShopBuyDetails(name=title, champion_id=cid, cost=cost),
                    constraints=("requires_shop_visible",),
                    tags=("tempo",),
                ),
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    actions.extend(a for _, a in scored[:8])
    return actions
