"""Shop logic: rolling, buying, selling, refreshing."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from .constants import REFRESH_COST, NAME_TO_COST

if TYPE_CHECKING:
    from .player import Player
    from .champion_pool import ChampionPool


def generate_shop(pool: ChampionPool, level: int) -> List[Optional[str]]:
    """Generate a new shop for a player based on their level."""
    return pool.roll_shop(level)


def buy_from_shop(player: Player, pool: ChampionPool, slot: int) -> bool:
    """Buy a champion from the shop.

    Validates gold, bench space, takes from pool, checks upgrades.
    Returns True if successful.
    """
    return player.buy_champion(slot, pool)


def sell_unit(player: Player, pool: ChampionPool,
              location: str, index) -> bool:
    """Sell a unit from board or bench.

    Args:
        location: 'board' or 'bench'
        index: (row, col) tuple for board, int for bench
    """
    if location == 'board':
        row, col = index
        return player.sell_from_board(row, col, pool)
    elif location == 'bench':
        return player.sell_from_bench(index, pool)
    return False


def refresh_shop(player: Player, pool: ChampionPool) -> bool:
    """Refresh the shop for 2 gold.

    Returns unsold champions to the pool, generates new shop.
    Returns True if successful.
    """
    if not player.can_afford(REFRESH_COST):
        return False

    # Return unsold shop champions to the pool
    _return_shop_to_pool(player, pool)

    player.gold -= REFRESH_COST
    player.shop = generate_shop(pool, player.level)
    return True


def _return_shop_to_pool(player: Player, pool: ChampionPool):
    """Return all unsold shop champions back to the pool."""
    for i, name in enumerate(player.shop):
        if name is not None:
            pool.return_champion(name, 1)
            player.shop[i] = None
