"""TFT Set 16 game constants.

Imports pool/trait data from existing files. All game rules in one place.
"""

import sys
import os

# Add project root to path for imports
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from simulator.Simulator.pool_stats import (
    COST_1, COST_2, COST_3, COST_4, COST_5,
    level_percentage, cost_star_values, base_pool_values,
)
from simulator.Simulator.origin_class_stats import origin_class, tiers

# ── Board dimensions ──────────────────────────────────────────────────────────
BOARD_ROWS = 4
BOARD_COLS = 7
BENCH_SIZE = 9
SHOP_SIZE = 5
ITEM_BENCH_SIZE = 10
MAX_ITEMS_PER_UNIT = 3

# ── Starting resources ────────────────────────────────────────────────────────
STARTING_HP = 100
STARTING_GOLD = 0
STARTING_LEVEL = 1
MAX_LEVEL = 9

# ── Economy ───────────────────────────────────────────────────────────────────
BASE_INCOME = 5
MAX_INTEREST = 5
REFRESH_COST = 2
XP_COST = 4        # Gold cost to buy XP
XP_PER_BUY = 4     # XP granted per buy
PASSIVE_XP_PER_ROUND = 2

# XP required to reach each level (index = level)
# Level 1→2: 2 XP, 2→3: 2 XP, 3→4: 6 XP, etc.
LEVEL_XP_REQUIRED = [0, 2, 2, 6, 10, 20, 36, 56, 80, 100]

# Early round gold (rounds 0-4, before standard income kicks in)
STARTING_ROUND_GOLD = [0, 2, 2, 3, 4]

# Win/loss streak gold bonuses
# Key = minimum streak length, value = bonus gold
STREAK_GOLD = {2: 1, 3: 1, 4: 2, 5: 3}

def get_streak_gold(streak: int) -> int:
    """Get bonus gold for a given streak length."""
    if streak >= 5:
        return 3
    elif streak >= 4:
        return 2
    elif streak >= 2:
        return 1
    return 0

# ── Champion pool ─────────────────────────────────────────────────────────────
POOL_SIZES = {1: 29, 2: 22, 3: 18, 4: 12, 5: 10}

# Champion lists by cost tier
CHAMPIONS_BY_COST = {
    1: COST_1,
    2: COST_2,
    3: COST_3,
    4: COST_4,
    5: COST_5,
}

# Sell values: SELL_VALUES[cost-1][star-1]
SELL_VALUES = cost_star_values

# Level roll odds - convert from cumulative to direct probabilities
# level_percentage is cumulative; we need P(cost) for each cost tier
LEVEL_ODDS = []
for level_odds in level_percentage:
    direct = []
    prev = 0.0
    for cum in level_odds:
        p = min(cum, 1.0) - prev
        if p < 0:
            p = 0.0
        direct.append(round(p, 4))
        prev = min(cum, 1.0)
    LEVEL_ODDS.append(direct)

# ── Name mapping ──────────────────────────────────────────────────────────────
# Build lowercase name → api_name and cost mappings
NAME_TO_API = {}
NAME_TO_COST = {}
for cost, champs in CHAMPIONS_BY_COST.items():
    for name in champs:
        # Convert lowercase name to TFT16_ API name
        # Handle special cases
        _API_MAP = {
            'jarvaniv': 'JarvanIV',
            'kogmaw': 'KogMaw',
            'chogath': 'ChoGath',
            'twistedfate': 'TwistedFate',
            'xinzhao': 'XinZhao',
            'reksai': 'RekSai',
            'drmundo': 'DrMundo',
            'leblanc': 'Leblanc',
            'gangplank': 'Gangplank',
            'kaisa': 'Kaisa',
            'missfortune': 'MissFortune',
            'belveth': 'BelVeth',
            'aurelionsol': 'AurelionSol',
            'baronnashor': 'BaronNashor',
            'tahmkench': 'TahmKench',
            'thex': 'THex',
        }
        if name in _API_MAP:
            api_suffix = _API_MAP[name]
        else:
            api_suffix = name.capitalize()
        api_name = f'TFT16_{api_suffix}'
        NAME_TO_API[name] = api_name
        NAME_TO_COST[name] = cost

# Reverse mapping: api_name → lowercase name
API_TO_NAME = {v: k for k, v in NAME_TO_API.items()}

# ── Trait data ────────────────────────────────────────────────────────────────
# Re-exported from origin_class_stats
CHAMPION_TRAITS = origin_class
TRAIT_TIERS = tiers

# ── HP damage per round ──────────────────────────────────────────────────────
# (max_round, base_damage) — base damage for the loser, before per-unit damage
ROUND_BASE_DAMAGE = [
    (3, 0),
    (9, 2),
    (15, 3),
    (21, 5),
    (27, 8),
    (10000, 15),
]

# Damage per surviving enemy unit
DAMAGE_PER_UNIT = [0, 2, 4, 6, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

def get_round_damage(round_num: int, surviving_units: int) -> int:
    """Calculate HP damage for losing a round."""
    base = 0
    for max_round, dmg in ROUND_BASE_DAMAGE:
        if round_num <= max_round:
            base = dmg
            break
    unit_idx = min(surviving_units, len(DAMAGE_PER_UNIT) - 1)
    return base + DAMAGE_PER_UNIT[unit_idx]
