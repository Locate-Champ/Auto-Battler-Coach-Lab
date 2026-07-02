"""Shared champion pool across all players.

In TFT, all players draw from the same pool. When a champion is bought,
one copy is removed. When sold or a player is eliminated, copies return.
"""

import random
from typing import Dict, Iterable, List, Optional, Set

from .constants import (
    CHAMPIONS_BY_COST,
    LEVEL_ODDS,
    NAME_TO_COST,
    POOL_SIZES,
    SHOP_SIZE,
)


class ChampionPool:
    """Manages the shared champion pool for a TFT game."""

    def __init__(self):
        # pool[name] = remaining copies
        self.pool: Dict[str, int] = {}
        for _cost, champs in CHAMPIONS_BY_COST.items():
            for name, count in champs.items():
                self.pool[name] = count

        # Build cost → list of names for fast lookup during rolling
        # 7-cost champions share the same shop odds as 5-cost,
        # so they are included in the cost-5 roll pool.
        self._names_by_cost: Dict[int, List[str]] = {}
        for cost, champs in CHAMPIONS_BY_COST.items():
            if cost == 7:
                # 7-costs roll with 5-costs (same odds, different gold price)
                if 5 not in self._names_by_cost:
                    self._names_by_cost[5] = []
                self._names_by_cost[5].extend(champs.keys())
            else:
                self._names_by_cost[cost] = list(champs.keys())

        self._name_index_by_cost: Dict[int, Dict[str, int]] = {}
        self._weights_by_cost: Dict[int, List[int]] = {}
        self._cum_weights_by_cost: Dict[int, List[int]] = {}
        self._total_by_cost: Dict[int, int] = {}
        for cost, names in self._names_by_cost.items():
            indices: Dict[str, int] = {}
            weights: List[int] = []
            cum_weights: List[int] = []
            running_total = 0
            for idx, name in enumerate(names):
                weight = max(0, self.pool.get(name, 0))
                indices[name] = idx
                weights.append(weight)
                running_total += weight
                cum_weights.append(running_total)
            self._name_index_by_cost[cost] = indices
            self._weights_by_cost[cost] = weights
            self._cum_weights_by_cost[cost] = cum_weights
            self._total_by_cost[cost] = running_total

    def roll_shop(
        self,
        level: int,
        *,
        allowed_names: Optional[Iterable[str]] = None,
        guaranteed_names: Optional[Iterable[str]] = None,
    ) -> List[Optional[str]]:
        """Generate a shop of 5 champions based on player level.

        Uses level-based odds to determine cost tier, then picks
        a random champion from that tier weighted by remaining copies.

        Args:
            level: Player level (1-9), used as index into LEVEL_ODDS.
            allowed_names: Optional subset of unit names allowed to appear.
            guaranteed_names: Optional list of champions guaranteed to appear
                in this shop (in order, up to shop size).

        Returns:
            List of 5 champion names (or None if tier is empty).
        """
        allowed_set: Optional[Set[str]] = None
        if allowed_names is not None:
            allowed_set = {name for name in allowed_names if name in self.pool}

        # Clamp level to valid range
        level_idx = max(0, min(level - 1, len(LEVEL_ODDS) - 1))
        odds = LEVEL_ODDS[level_idx]

        shop = []
        if guaranteed_names:
            for guaranteed in guaranteed_names:
                if len(shop) >= SHOP_SIZE:
                    break
                if guaranteed not in self.pool:
                    continue
                if allowed_set is not None and guaranteed not in allowed_set:
                    continue
                if self.pool.get(guaranteed, 0) <= 0:
                    continue
                shop.append(guaranteed)

        for _ in range(SHOP_SIZE):
            if len(shop) >= SHOP_SIZE:
                break
            # Pick a cost tier
            roll = random.random()
            cumulative = 0.0
            chosen_cost = 1
            for cost_idx, prob in enumerate(odds):
                cumulative += prob
                if roll < cumulative:
                    chosen_cost = cost_idx + 1
                    break

            # Pick a champion from that tier, weighted by remaining copies
            champ = self._pick_from_tier(chosen_cost, allowed_names=allowed_set)
            shop.append(champ)

        while len(shop) < SHOP_SIZE:
            shop.append(None)

        return shop

    def _pick_from_tier(
        self,
        cost: int,
        *,
        allowed_names: Optional[Set[str]] = None,
    ) -> Optional[str]:
        """Pick a random champion from a cost tier, weighted by pool count."""
        names = self._names_by_cost.get(cost, [])
        if not names:
            return None

        if allowed_names is not None:
            filtered_names: List[str] = []
            filtered_cum_weights: List[int] = []
            running = 0
            for name in names:
                if name not in allowed_names:
                    continue
                weight = max(0, self.pool.get(name, 0))
                if weight <= 0:
                    continue
                running += weight
                filtered_names.append(name)
                filtered_cum_weights.append(running)
            if not filtered_names:
                return None
            return random.choices(filtered_names, cum_weights=filtered_cum_weights, k=1)[0]

        total = self._total_by_cost.get(cost, 0)
        if total == 0:
            return None

        cum_weights = self._cum_weights_by_cost.get(cost)
        if not cum_weights:
            return None
        return random.choices(names, cum_weights=cum_weights, k=1)[0]

    def take(self, name: str) -> bool:
        """Remove one copy of a champion from the pool.

        Returns True if successful, False if no copies remain.
        """
        if self.pool.get(name, 0) <= 0:
            return False
        self.pool[name] -= 1
        self._update_cached_weights(name, -1)
        return True

    def return_champion(self, name: str, count: int = 1):
        """Return copies of a champion to the pool (on sell or elimination)."""
        if name not in self.pool:
            return
        max_count = POOL_SIZES.get(NAME_TO_COST.get(name, 1), 29)
        old_count = self.pool[name]
        self.pool[name] = min(old_count + count, max_count)
        restored = self.pool[name] - old_count
        if restored:
            self._update_cached_weights(name, restored)

    def available(self, name: str) -> int:
        """Get remaining copies of a champion in the pool."""
        return self.pool.get(name, 0)

    def return_player_champions(self, champions: list):
        """Return all of an eliminated player's champions to the pool.

        Args:
            champions: List of ChampionInstance objects.
        """
        for champ in champions:
            # A 2-star = 3 copies, 3-star = 9 copies
            copies = 3 ** (champ.star_level - 1)
            self.return_champion(champ.name, copies)

    def _update_cached_weights(self, name: str, delta: int) -> None:
        """Incrementally update cached tier weights/cumulative totals."""
        base_cost = NAME_TO_COST.get(name)
        if base_cost is None:
            return
        tier_cost = 5 if base_cost == 7 else base_cost
        indices = self._name_index_by_cost.get(tier_cost)
        if not indices:
            return
        idx = indices.get(name)
        if idx is None:
            return

        weights = self._weights_by_cost[tier_cost]
        old_weight = weights[idx]
        new_weight = max(0, old_weight + delta)
        actual_delta = new_weight - old_weight
        if actual_delta == 0:
            return

        weights[idx] = new_weight
        cum_weights = self._cum_weights_by_cost[tier_cost]
        for i in range(idx, len(cum_weights)):
            cum_weights[i] += actual_delta
        self._total_by_cost[tier_cost] += actual_delta
