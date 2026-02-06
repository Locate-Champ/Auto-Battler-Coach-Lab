"""Shared champion pool across all players.

In TFT, all players draw from the same pool. When a champion is bought,
one copy is removed. When sold or a player is eliminated, copies return.
"""

import random
from typing import List, Optional, Dict

from .constants import (
    CHAMPIONS_BY_COST, POOL_SIZES, LEVEL_ODDS, SHOP_SIZE,
    NAME_TO_COST,
)


class ChampionPool:
    """Manages the shared champion pool for a TFT game."""

    def __init__(self):
        # pool[name] = remaining copies
        self.pool: Dict[str, int] = {}
        for cost, champs in CHAMPIONS_BY_COST.items():
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

    def roll_shop(self, level: int) -> List[Optional[str]]:
        """Generate a shop of 5 champions based on player level.

        Uses level-based odds to determine cost tier, then picks
        a random champion from that tier weighted by remaining copies.

        Args:
            level: Player level (1-9), used as index into LEVEL_ODDS.

        Returns:
            List of 5 champion names (or None if tier is empty).
        """
        # Clamp level to valid range
        level_idx = max(0, min(level - 1, len(LEVEL_ODDS) - 1))
        odds = LEVEL_ODDS[level_idx]

        shop = []
        for _ in range(SHOP_SIZE):
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
            champ = self._pick_from_tier(chosen_cost)
            shop.append(champ)

        return shop

    def _pick_from_tier(self, cost: int) -> Optional[str]:
        """Pick a random champion from a cost tier, weighted by pool count."""
        names = self._names_by_cost.get(cost, [])
        if not names:
            return None

        # Build weights from remaining copies
        weights = [max(0, self.pool.get(n, 0)) for n in names]
        total = sum(weights)
        if total == 0:
            return None

        return random.choices(names, weights=weights, k=1)[0]

    def take(self, name: str) -> bool:
        """Remove one copy of a champion from the pool.

        Returns True if successful, False if no copies remain.
        """
        if self.pool.get(name, 0) <= 0:
            return False
        self.pool[name] -= 1
        return True

    def return_champion(self, name: str, count: int = 1):
        """Return copies of a champion to the pool (on sell or elimination)."""
        if name not in self.pool:
            return
        max_count = POOL_SIZES.get(NAME_TO_COST.get(name, 1), 29)
        self.pool[name] = min(self.pool[name] + count, max_count)

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
