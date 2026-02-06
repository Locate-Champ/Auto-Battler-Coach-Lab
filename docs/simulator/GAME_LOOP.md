# TFT Game Loop (`simulator/game/`)

Full 8-player TFT game simulation wrapping the combat engine. Built as a clean replacement for the legacy Set 4 `simulator/Simulator/` game loop.

---

## Quick Start

```bash
# Run a full game with random agents
python -m simulator.game

# From Python
from simulator.game import TFTGame
game = TFTGame(seed=42, verbose=True)
placements = game.play()
# placements = [(player_id, placement), ...]
```

---

## Architecture

```
simulator/game/
  __init__.py          # Public API exports
  __main__.py          # python -m simulator.game entry point
  types.py             # Shared dataclasses and enums
  constants.py         # All game rules (imports pool_stats + origin_class_stats)
  champion_pool.py     # Shared champion pool across 8 players
  player.py            # Player state: gold, HP, board, bench, upgrades
  shop.py              # Shop rolling, buying, selling, refreshing
  actions.py           # Legal action enumeration + random agent
  game.py              # Main game loop: rounds, matchmaking, combat
```

### Data Flow

```
TFTGame.play()
  |
  |-- PvE rounds (0-3): grant income, generate shops, run agent actions
  |
  |-- PvP rounds (4+):
  |     1. Income phase: gold + interest + streak bonus + passive XP
  |     2. Planning phase: generate shop, run agent actions, auto-fill board
  |     3. Matchmaking: weighted pairing to avoid repeat opponents
  |     4. Combat phase: CombatEngine.run_combat() for each pair
  |     5. Damage phase: loser takes base_damage + per_unit_damage
  |     6. Elimination: players at 0 HP are eliminated
  |
  |-- Game ends when 1 player remains
```

### Integration with Combat Engine

The game loop calls `simulator/core/combat_engine.py` through two methods only:

```python
# 1. Create units from board state
unit = engine.create_unit(api_name, star_level, position, team, items)

# 2. Run combat between two teams
result = engine.run_combat(team0, team1)
# result = {winner, combat_time, team0_survivors, team1_survivors, ...}
```

The `Player.build_combat_team(engine)` method converts board state into combat Unit objects.

---

## Public API

### TFTGame

```python
class TFTGame:
    def __init__(self, num_players=8, seed=None, agent_fn=None, verbose=False)
    def play(self) -> List[Tuple[int, int]]  # [(player_id, placement)]
    def get_state(player_id) -> Dict          # Observable game state for RL

    # Properties
    game.alive_players -> List[Player]
    game.round_num -> int
    game.placements -> List[Tuple[int, int]]
    game.pool -> ChampionPool
    game.engine -> CombatEngine
    game.players -> List[Player]
```

### Player

```python
class Player:
    # State
    player_id: int
    gold: int
    hp: int           # Starts at 100
    level: int         # 1-9
    xp: int
    board: Dict[Tuple[int,int], ChampionInstance]  # (row,col) -> champion
    bench: List[Optional[ChampionInstance]]          # 9 slots
    shop: List[Optional[str]]                        # 5 champion names
    win_streak: int
    loss_streak: int
    alive: bool
    placement: int     # 1=winner, 8=first out

    # Properties
    player.max_units -> int       # Equals level
    player.board_count -> int     # Current board units

    # Economy
    add_income(round_num)
    buy_xp() -> bool

    # Shop
    buy_champion(shop_slot, pool) -> bool

    # Selling
    sell_from_board(row, col, pool) -> bool
    sell_from_bench(bench_idx, pool) -> bool

    # Board management
    bench_to_board(bench_idx, row, col) -> bool
    board_to_bench(row, col) -> bool
    move_on_board(from_row, from_col, to_row, to_col) -> bool
    auto_fill_board()

    # Combat
    build_combat_team(engine) -> List[Unit]
    get_active_traits() -> Dict[str, int]

    # Damage
    take_damage(amount)
    win_round()
    lose_round(damage)
```

### ChampionInstance

```python
@dataclass
class ChampionInstance:
    name: str           # Lowercase key ('jinx')
    api_name: str       # 'TFT16_Jinx'
    cost: int           # 1-5
    star_level: int     # 1, 2, or 3
    items: List[str]    # Item names
    sell_value -> int   # Gold refund (property)
```

### Actions

```python
from simulator.game import Action, ActionType, get_legal_actions, execute_action

# Get all legal actions
actions = get_legal_actions(player, pool)

# Execute one
success = execute_action(Action.buy(0), player, pool)

# Action types
Action.buy(shop_slot)           # Buy from shop
Action.sell((row, col))         # Sell from board
Action.sell((bench_idx,))       # Sell from bench
Action.move((bench_idx,), (row, col))  # Bench to board
Action.move((r1,c1), (r2,c2))  # Board reposition
Action.level()                  # Buy 4 XP for 4 gold
Action.refresh()                # Reroll shop for 2 gold
Action.pass_action()            # End planning phase
```

### ChampionPool

```python
class ChampionPool:
    pool: Dict[str, int]           # name -> remaining copies

    roll_shop(level) -> List[str]  # Generate 5 champions
    take(name) -> bool             # Remove 1 copy
    return_champion(name, count=1) # Return copies
    available(name) -> int         # Remaining copies
    return_player_champions(champs)# Return all on elimination
```

---

## Game Constants

All constants are in `simulator/game/constants.py`:

| Constant | Value | Description |
|----------|-------|-------------|
| `BOARD_ROWS` | 4 | Hex grid rows |
| `BOARD_COLS` | 7 | Hex grid columns |
| `BENCH_SIZE` | 9 | Bench slots |
| `SHOP_SIZE` | 5 | Shop slots |
| `STARTING_HP` | 100 | Player starting health |
| `BASE_INCOME` | 5 | Gold per round (round 5+) |
| `MAX_INTEREST` | 5 | Max interest gold |
| `REFRESH_COST` | 2 | Shop reroll cost |
| `XP_COST` | 4 | Gold cost to buy XP |
| `XP_PER_BUY` | 4 | XP granted per buy |
| `PASSIVE_XP_PER_ROUND` | 2 | Auto XP per round |
| `MAX_LEVEL` | 9 | Maximum player level |

### Economy Rules

- **Interest**: `min(floor(gold/10), 5)` — earn up to 5g per round
- **Streaks**: 2-3 = +1g, 4 = +2g, 5+ = +3g
- **Win bonus**: +1g per combat win
- **Early rounds** (0-4): Fixed gold [0, 2, 2, 3, 4] + interest

### Level XP Requirements

| Level | XP Required | Cumulative |
|-------|-------------|------------|
| 2 | 2 | 2 |
| 3 | 2 | 4 |
| 4 | 6 | 10 |
| 5 | 10 | 20 |
| 6 | 20 | 40 |
| 7 | 36 | 76 |
| 8 | 56 | 132 |
| 9 | 80 | 212 |

### Champion Pool Sizes

| Cost | Copies Each | Champions | Total in Pool |
|------|-------------|-----------|---------------|
| 1 | 29 | 14 | 406 |
| 2 | 22 | 19 | 418 |
| 3 | 18 | 18 | 324 |
| 4 | 12 | 24 | 288 |
| 5 | 10 | 24 | 240 |

### Sell Values

| Cost | 1-star | 2-star | 3-star |
|------|--------|--------|--------|
| 1 | 1 | 3 | 9 |
| 2 | 2 | 5 | 17 |
| 3 | 3 | 8 | 26 |
| 4 | 4 | 11 | 35 |
| 5 | 5 | 14 | 44 |

### HP Damage Per Round

| Rounds | Base Damage |
|--------|-------------|
| 0-3 | 0 |
| 4-9 | 2 |
| 10-15 | 3 |
| 16-21 | 5 |
| 22-27 | 8 |
| 28+ | 15 |

Plus per-surviving-unit damage: [0, 2, 4, 6, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

---

## Custom Agents

The default agent takes random actions. Provide your own via `agent_fn`:

```python
def my_agent(player, pool):
    """Custom agent that buys everything and levels aggressively."""
    from simulator.game import get_legal_actions, execute_action, Action, ActionType

    # Buy everything affordable
    for slot in range(5):
        execute_action(Action.buy(slot), player, pool)

    # Level up if possible
    while player.gold >= 4 and player.level < 9:
        execute_action(Action.level(), player, pool)

game = TFTGame(seed=42, agent_fn=my_agent)
placements = game.play()
```

---

## Data Dependencies

The game loop imports from existing modules (no data duplication):

| Import | Source | What |
|--------|--------|------|
| `COST_1-5` | `simulator.Simulator.pool_stats` | Champion pool dictionaries |
| `level_percentage` | `simulator.Simulator.pool_stats` | Roll odds by level |
| `cost_star_values` | `simulator.Simulator.pool_stats` | Sell values |
| `origin_class` | `simulator.Simulator.origin_class_stats` | Champion -> trait mapping |
| `tiers` | `simulator.Simulator.origin_class_stats` | Trait breakpoints |
| `CombatEngine` | `simulator.core.combat_engine` | Combat resolution |
| `combat_data.json` | `simulator/data/` | Champion stats (loaded by engine) |

---

## Name Mapping

Champion names flow through three formats:

1. **Pool key** (lowercase): `'jinx'`, `'kogmaw'`, `'leblanc'`
2. **API name**: `'TFT16_Jinx'`, `'TFT16_KogMaw'`, `'TFT16_Leblanc'`
3. **Display name**: `'Jinx'`, `'Kog\'Maw'`, `'LeBlanc'`

The mapping table is in `constants.py` as `NAME_TO_API` and `API_TO_NAME`.

**Known gotchas**: `TFT16_Leblanc` (lowercase b), `TFT16_Kaisa` (lowercase s).

---

## MVP vs Future

### Implemented (MVP)
- 8-player game with elimination and placement tracking
- Full economy (gold, interest, streaks, per-round income)
- Shop with shared pool and level-based odds
- Champion buying, selling, upgrading (3 copies -> star up)
- Board/bench management with swapping
- Leveling (XP buy, passive XP, auto-level)
- Combat resolution via existing combat engine
- HP damage calculation per round
- Weighted matchmaking (avoids repeat opponents, ghost for odd count)
- Random agent for testing
- Deterministic seeding
- Observable game state (`get_state()`)

### Future Work
- Carousel mechanics (currently skipped)
- Minion combat / PvE loot orbs (currently simplified to income grant)
- Augment selection at specific rounds
- Item combining (2 components -> full item)
- Item equip action in planning phase
- RL observation/action space encoding (for training)
- Smarter agents (heuristic, ML-based)
- Training data generation pipeline

---

*Created: 2026-02-05*
