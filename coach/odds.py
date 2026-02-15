from __future__ import annotations

import random
from typing import Sequence

from coach.scoring.features import champion_cost, copy_counts, champions_by_cost, lobby_copy_counts
from coach.state import GameState


# Shop odds by player level (percentages for each cost tier)
# Format: level -> [1-cost%, 2-cost%, 3-cost%, 4-cost%, 5-cost%]
SHOP_ODDS_BY_LEVEL: dict[int, list[int]] = {
    1: [100, 0, 0, 0, 0],
    2: [100, 0, 0, 0, 0],
    3: [75, 25, 0, 0, 0],
    4: [55, 30, 15, 0, 0],
    5: [45, 33, 20, 2, 0],
    6: [30, 40, 25, 5, 0],
    7: [19, 35, 35, 10, 1],
    8: [18, 25, 36, 18, 3],
    9: [10, 20, 25, 35, 10],
    10: [5, 10, 20, 40, 25],
}


def cost_odds_for_level(level: int) -> Sequence[float]:
    clamped = max(1, min(10, int(level)))
    odds = SHOP_ODDS_BY_LEVEL[clamped]
    return [x / 100.0 for x in odds]


# Per-champion pool sizes by cost (Set 16 baseline).
POOL_SIZES_BY_COST: dict[int, int] = {
    1: 30,
    2: 25,
    3: 18,
    4: 10,
    5: 9,
}


def pool_size_for_cost(cost: int) -> int:
    return POOL_SIZES_BY_COST.get(int(cost), 18)


def _sample_cost_tier(rng: random.Random, level: int) -> int:
    odds = cost_odds_for_level(level)
    r = rng.random()
    acc = 0.0
    for i, p in enumerate(odds, start=1):
        acc += float(p)
        if r <= acc:
            return i
    return 5


def _sample_champion_from_tier(
    rng: random.Random,
    *,
    cost: int,
    in_play: dict[str, int],
) -> str | None:
    by_cost = champions_by_cost()
    champs = by_cost.get(int(cost), ())
    if not champs:
        return None

    per_champ = pool_size_for_cost(cost)
    weights = []
    total = 0
    for cid in champs:
        remaining = max(0, int(per_champ) - int(in_play.get(cid, 0)))
        if remaining <= 0:
            continue
        weights.append((cid, remaining))
        total += remaining

    if total <= 0:
        return champs[rng.randrange(len(champs))]

    r = rng.randrange(total)
    for cid, w in weights:
        if r < w:
            return cid
        r -= w
    return weights[-1][0]


def estimate_upgrade_hit_prob(
    state: GameState,
    *,
    level: int,
    rolls: int,
    seed: int,
    num_trials: int,
    max_targets: int = 6,
) -> tuple[float, dict[str, float], tuple[str, ...]]:
    """
    Short-horizon Monte Carlo:
    Estimate probability that rolling `rolls` times hits an immediate (1-copy) upgrade target.
    """
    r = max(0, int(rolls))
    trials = max(1, int(num_trials))
    if r <= 0:
        return 0.0, {}, ()

    my_counts = copy_counts(tuple((*state.board, *state.bench)))
    # Targets are champions where we are 1 copy away from next star breakpoint (2* or 3*).
    candidates: list[tuple[int, str]] = []
    for cid, copies in my_counts.items():
        copies_i = int(copies)
        if copies_i <= 0:
            continue
        if copies_i < 3:
            needed = 3 - copies_i
        elif copies_i < 9:
            needed = 9 - copies_i
        else:
            continue
        if needed != 1:
            continue
        candidates.append((champion_cost(cid), cid))

    candidates.sort(reverse=True)
    targets = tuple(cid for _, cid in candidates[: max(0, int(max_targets))])
    if not targets:
        return 0.0, {}, ()

    rng = random.Random(int(seed))
    in_play = lobby_copy_counts(state)

    any_hits = 0
    per_target_hits = {t: 0 for t in targets}

    for _ in range(trials):
        hit_any = False
        hit_targets: set[str] = set()

        for _roll in range(r):
            for _slot in range(5):
                cost = _sample_cost_tier(rng, level=int(level))
                cid = _sample_champion_from_tier(rng, cost=cost, in_play=in_play)
                if cid is None:
                    continue
                if cid in per_target_hits:
                    hit_any = True
                    hit_targets.add(cid)

        if hit_any:
            any_hits += 1
        for t in hit_targets:
            per_target_hits[t] += 1

    prob_any = any_hits / trials
    per_target = {t: per_target_hits[t] / trials for t in targets}
    return prob_any, per_target, targets
