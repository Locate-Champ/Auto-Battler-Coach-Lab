"""
Pool Tracker Service

Tracks unit pool state across all players and calculates
rolling probabilities for finding specific champions.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# TFT Set 16 Pool sizes by champion cost
POOL_SIZES = {
    1: 30,  # 1-cost champions
    2: 25,  # 2-cost champions
    3: 18,  # 3-cost champions
    4: 10,  # 4-cost champions
    5: 9,  # 5-cost champions
}

# Shop odds by player level (percentages for each cost tier)
# Format: level -> [1-cost%, 2-cost%, 3-cost%, 4-cost%, 5-cost%]
SHOP_ODDS = {
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


@dataclass
class PoolState:
    """
    Tracks unit pool state and calculates availability.

    Attributes:
        champion_costs: Mapping of champion_id to cost (1-5)
        units_in_play: Count of each champion currently on all boards
        player_level: Current player level (affects shop odds)
    """

    champion_costs: dict[str, int] = field(default_factory=dict)
    units_in_play: dict[str, int] = field(default_factory=dict)
    player_level: int = 6

    def load_champion_costs(self, data_dir: Path) -> bool:
        """
        Load champion costs from champions.jsonl.

        Args:
            data_dir: Root data directory

        Returns:
            True if loaded successfully
        """
        champions_file = data_dir / "data" / "game_data" / "champions.jsonl"
        if not champions_file.exists():
            logger.warning(f"Champions file not found: {champions_file}")
            return False

        try:
            with open(champions_file, "r") as f:
                for line in f:
                    champ = json.loads(line)
                    api_name = champ.get("apiName", "")
                    cost = champ.get("cost", 0)
                    if api_name and cost:
                        self.champion_costs[api_name] = cost

            logger.info(f"Loaded costs for {len(self.champion_costs)} champions")
            return True

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load champion costs: {e}")
            return False

    def update_from_boards(
        self, your_board: list, your_bench: list, opponent_boards: dict[str, list]
    ):
        """
        Update pool state from all board data.

        Args:
            your_board: List of unit dicts from your board
            your_bench: List of unit dicts from your bench
            opponent_boards: Dict of board_id -> list of unit dicts
        """
        self.units_in_play.clear()

        # Count your units (board + bench)
        for unit in your_board + your_bench:
            champ_id = unit.get("character_id", "")
            if not champ_id:
                continue
            stars = unit.get("stars", 1)
            # 1-star = 1 copy, 2-star = 3 copies, 3-star = 9 copies
            copies = {1: 1, 2: 3, 3: 9}.get(stars, 1)
            self.units_in_play[champ_id] = self.units_in_play.get(champ_id, 0) + copies

        # Count opponent units
        for board_id, units in opponent_boards.items():
            for unit in units:
                champ_id = unit.get("character_id", "")
                if not champ_id:
                    continue
                stars = unit.get("stars", 1)
                copies = {1: 1, 2: 3, 3: 9}.get(stars, 1)
                self.units_in_play[champ_id] = self.units_in_play.get(champ_id, 0) + copies

        total_units = sum(self.units_in_play.values())
        logger.debug(
            f"Pool updated: {len(self.units_in_play)} unique champions, {total_units} total units"
        )

    def get_remaining(self, champion: str) -> int:
        """
        Get remaining copies of a champion in the pool.

        Args:
            champion: Champion API name (e.g., "TFT16_Ekko")

        Returns:
            Number of copies still available
        """
        cost = self.champion_costs.get(champion, 3)
        total = POOL_SIZES.get(cost, 18)
        in_play = self.units_in_play.get(champion, 0)
        return max(0, total - in_play)

    def get_shop_probability(self, champion: str, level: Optional[int] = None) -> float:
        """
        Calculate probability to see a champion in shop.

        This is a simplified calculation that estimates the chance
        of seeing a specific champion in one shop slot.

        Args:
            champion: Champion API name
            level: Player level (uses self.player_level if not provided)

        Returns:
            Probability between 0 and 1
        """
        if level is None:
            level = self.player_level

        cost = self.champion_costs.get(champion, 3)
        remaining = self.get_remaining(champion)

        if remaining <= 0:
            return 0.0

        # Get odds for this cost at player's level
        level = max(1, min(10, level))  # Clamp to valid range
        tier_odds = SHOP_ODDS.get(level, SHOP_ODDS[6])
        tier_chance = tier_odds[cost - 1] / 100.0

        if tier_chance == 0:
            return 0.0

        # Calculate total remaining champions of this cost
        total_remaining_tier = 0
        for champ_id, champ_cost in self.champion_costs.items():
            if champ_cost == cost:
                total_remaining_tier += self.get_remaining(champ_id)

        if total_remaining_tier == 0:
            return 0.0

        # Probability = tier_chance * (remaining / total_in_tier)
        return tier_chance * (remaining / total_remaining_tier)

    def can_three_star(self, champion: str, current_copies: int = 0) -> bool:
        """
        Check if 3-starring a champion is still possible.

        Args:
            champion: Champion API name
            current_copies: Copies you already have

        Returns:
            True if 9 total copies are achievable
        """
        needed = 9 - current_copies
        return self.get_remaining(champion) >= needed

    def get_availability(self, champion: str) -> str:
        """
        Get availability category for a champion.

        Args:
            champion: Champion API name

        Returns:
            One of: 'high', 'medium', 'low', 'none'
        """
        remaining = self.get_remaining(champion)
        cost = self.champion_costs.get(champion, 3)
        total = POOL_SIZES.get(cost, 18)

        if remaining <= 0:
            return "none"

        ratio = remaining / total

        if ratio >= 0.66:
            return "high"
        if ratio >= 0.33:
            return "medium"
        return "low"

    def get_pool_summary(self) -> dict:
        """
        Get a summary of pool state for API responses.

        Returns:
            Dict with pool statistics
        """
        summary = {
            "total_units_in_play": sum(self.units_in_play.values()),
            "unique_champions": len(self.units_in_play),
            "player_level": self.player_level,
            "by_cost": {},
        }

        # Group by cost
        for cost in range(1, 6):
            cost_data = {
                "pool_size": POOL_SIZES[cost],
                "in_play": 0,
                "champions": [],
            }

            for champ_id, champ_cost in self.champion_costs.items():
                if champ_cost == cost:
                    in_play = self.units_in_play.get(champ_id, 0)
                    if in_play > 0:
                        cost_data["in_play"] += in_play
                        cost_data["champions"].append(
                            {
                                "id": champ_id,
                                "in_play": in_play,
                                "remaining": self.get_remaining(champ_id),
                                "availability": self.get_availability(champ_id),
                            }
                        )

            summary["by_cost"][cost] = cost_data

        return summary


# Global pool state instance
_pool_state: Optional[PoolState] = None


def get_pool_state() -> PoolState:
    """Get or create the global pool state instance."""
    global _pool_state
    if _pool_state is None:
        _pool_state = PoolState()
        # Try to load champion costs
        data_dir = Path(__file__).parent.parent.parent
        _pool_state.load_champion_costs(data_dir)
    return _pool_state
