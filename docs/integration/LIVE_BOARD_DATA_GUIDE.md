# Live Board Data Integration Guide

> How to get real-time TFT board data for the frontend

---

## Data Source

Two live data sources exist:
1. Log parsing (file monitoring): reliable for stage/augments/scouting; sometimes contains board/bench/shop.
2. Redux bridge injection (recommended): reliable board/bench/shop + all 8 boards (`board_data`) via `ws://127.0.0.1:8765/redux` (see `app/redux_bridge/inject.js`).

**Log Location:**
```
C:\Users\<USER>\AppData\Local\Overwolf\Log\Apps\MetaTFT\
```

**Key Files:**
| File | Data |
|------|------|
| `background.html.log` | Main game events, board state, roster |
| `ingamecontroller.html.*.log` | Matchup info |

---

## Board Data Format

### Player Board (`tft_board`)

From Overwolf GameEvents Provider logs:

```json
{
  "cell_1": {"name": "TFT16_KogMaw", "level": "1", "item_1": "", "item_2": "", "item_3": ""},
  "cell_24": {"name": "TFT16_Blitzcrank", "level": "1", "item_1": "", "item_2": "", "item_3": ""},
  "cell_25": {"name": "TFT16_ChoGath", "level": "1", "item_1": "TFT_Item_Warmogs", "item_2": "", "item_3": ""},
  "cell_26": {"name": "TFT16_Illaoi", "level": "2", "item_1": "", "item_2": "", "item_3": ""}
}
```

### Cell ID → Row/Col Mapping

TFT board is 7 columns × 4 rows:

```
Row 0 (back):   [0]  [1]  [2]  [3]  [4]  [5]  [6]
Row 1:          [7]  [8]  [9]  [10] [11] [12] [13]
Row 2:          [14] [15] [16] [17] [18] [19] [20]
Row 3 (front):  [21] [22] [23] [24] [25] [26] [27]
```

**Conversion Formula:**
```typescript
const row = Math.floor(cellId / 7);  // 0-3
const col = cellId % 7;              // 0-6
```

### Champion Names

- Format: `TFT16_<ChampionName>`
- Examples: `TFT16_KogMaw`, `TFT16_Anivia`, `TFT16_Blitzcrank`
- Strip prefix for display: `name.replace(/^TFT\d+_/, '')`

### Star Level

- Field: `level` (string)
- Values: `"1"`, `"2"`, `"3"`
- Parse as int for display

### Items

- Fields: `item_1`, `item_2`, `item_3`
- Standard items: `TFT_Item_<Name>` (e.g., `TFT_Item_BFSword`, `TFT_Item_Warmogs`)
- Set-specific: `TFT16_<ItemName>` (e.g., Darkin items)
- Emblems: `Item_Icons/Traits/Spatula/Set16/TFT16_Emblem_<Trait>.TFT_Set16`
- Empty = `""`

### Item Name → Image File Mapping

```typescript
function getItemImageFile(itemId: string): string {
  if (!itemId) return '';

  // Standard items: TFT_Item_BFSword → BF Sword.png
  const standardMatch = itemId.match(/^TFT_Item_(.+)$/);
  if (standardMatch) {
    return formatItemName(standardMatch[1]) + '.png';
  }

  // Handle emblem items, darkin items, etc.
  // ...
}
```

---

## Opponent Data

### Current Opponent

```json
{"feature":"match_info","key":"opponent","value":"{\"name\":\"TeemoTherapie\",\"tag_line\":\"80085\"}"}
```

### Opponent Board

**Log parsing:** Overwolf does NOT provide direct opponent board data.

**Redux bridge:** MetaTFT Redux `board_data` includes all 8 boards; the backend forwards it as `opponent_boards`.

Options (when opponent boards are missing):
1. **Skip opponent board** in frontend (show only player board)
2. **Use mock/demo data** for opponent
3. **Build scouting feature** - track what you see when scouting

---

## Roster Data (All 8 Players)

```json
{
  "TeemoTherapie": {"index": 1, "health": 94, "xp": 3, "localplayer": false, "rank": 0, "tag_line": "80085"},
  "Karina Super Fan": {"index": 5, "health": 100, "xp": 4, "localplayer": true, "rank": 0, "tag_line": "8148"},
  ...
}
```

Use `localplayer: true` to identify the current player.

---

## Integration Architecture

### Existing Infrastructure

The project already has:

```
app/watcher/log_watcher.py    → Watches MetaTFT log files
app/watcher/parser.py         → Parses log events (11+ patterns)
app/state/game_state.py       → Game state data model
app/state/state_manager.py    → Reconstructs state from events
app/server/websocket.py       → WebSocket server for live updates
app/api/server.py             → REST API endpoints
```

### Data Flow

```
MetaTFT Logs → Log Watcher → Parser → State Manager → WebSocket → Frontend
     ↑                                                              ↓
  Overwolf GEP                                              React Components
```

---

## Current Implementation Status

### Parser (`app/watcher/parser.py`)

**Currently parses:**
- ✅ Stage changes (`[EVT] stage: 2-1`)
- ✅ XP changes (`XP: 0/6 -> 2/6`)
- ✅ Health updates (`Correcting health for player: Name 93 100`)
- ✅ Win chance (`WinChanceNumber: ~96%`)
- ✅ Scouting (`Scouting: PlayerName`)
- ✅ Augment armory (JSON data)
- ✅ Item select (JSON data)
- ✅ Game start indicators

**Also parses (when present in logs):**
- ✅ `tft_board` - Board unit positions
- ✅ `tft_bench` - Bench units
- ✅ `tft_roster` - All 8 players roster
- ✅ `tft_shop` - Shop offerings

### Game State (`app/state/game_state.py`)

**Data structures exist:**
```python
@dataclass
class Unit:
    character_id: str      # e.g., "TFT16_Ekko"
    star_level: int = 1
    items: list[str] = field(default_factory=list)
    position: Optional[tuple[int, int]] = None  # (row, col)

@dataclass
class PlayerState:
    name: str
    health: int = 100
    level: int = 1
    is_self: bool = False
    board_units: list[Unit] = field(default_factory=list)  # ← Exists!
    traits: dict[str, int] = field(default_factory=dict)
```

**Status:**
- ✅ `to_dict()` serializes `board_units`, `bench_units`, `shop_units`, `unassigned_items`, and `opponent_boards`.
- ✅ `StateManager` populates board/bench/shop from log events (when present) and via the Redux bridge (`/redux`).

---

## What Remains

These implementation steps are now complete. Remaining work is end-to-end validation in a real live game and deciding whether Redux bridge or log parsing is the default for board/bench/shop/opponent boards.

### Step 1 (Done): Add Board Parsing to `parser.py`

Add new event type and pattern:

```python
# In EventType enum:
BOARD_UPDATE = "board_update"
BENCH_UPDATE = "bench_update"

# In PATTERNS dict:
"board": re.compile(r'"key":"tft_board","value":"(\{.+?\})"'),
"bench": re.compile(r'"key":"tft_bench","value":"(\{.+?\})"'),
```

### Step 2 (Done): Update State Manager

Handle new events in `state_manager.py`:

```python
def handle_board_update(self, event: GameEvent):
    board_data = event.data.get("board", {})
    units = []
    for cell_key, unit_data in board_data.items():
        cell_id = int(cell_key.replace("cell_", ""))
        row = cell_id // 7
        col = cell_id % 7
        units.append(Unit(
            character_id=unit_data["name"],
            star_level=int(unit_data["level"]),
            items=[unit_data[f"item_{i}"] for i in range(1,4) if unit_data.get(f"item_{i}")],
            position=(row, col)
        ))
    self.state.player.board_units = units
```

### Step 3 (Done): Fix `to_dict()` Serialization

Add board units to JSON output in `game_state.py`:

```python
def to_dict(self) -> dict:
    return {
        # ... existing fields ...
        "board_units": [
            {
                "id": f"cell_{u.position[0]*7 + u.position[1]}",
                "name": u.name,
                "character_id": u.character_id,
                "stars": u.star_level,
                "items": u.items,
                "position": {"row": u.position[0], "col": u.position[1]}
            }
            for u in self.player.board_units if u.position
        ],
    }
```

### Step 4 (Done): Connect Frontend to WebSocket

In `app/frontend/`, subscribe to WebSocket updates (via the Vite `/ws` proxy in dev).

---

## Transformation: Live Data → Frontend Format

### Input (from logs)
```json
{
  "cell_1": {"name": "TFT16_KogMaw", "level": "2", "item_1": "TFT_Item_BFSword", "item_2": "", "item_3": ""}
}
```

### Output (for frontend)
```typescript
{
  id: "cell_1",
  name: "KogMaw",               // Strip TFT16_ prefix
  cost: 3,                       // Look up from champion data
  stars: 2,                      // Parse level string
  items: [
    { name: "BF Sword", imageFile: "BF Sword.png" }
  ],
  position: { row: 0, col: 1 }   // cell_1 → row 0, col 1
}
```

### Transformer Function

```typescript
function transformBoardData(logData: Record<string, LogUnit>): PositionedUnit[] {
  return Object.entries(logData).map(([cellKey, unit]) => {
    const cellId = parseInt(cellKey.replace('cell_', ''));
    const row = Math.floor(cellId / 7);
    const col = cellId % 7;

    return {
      id: cellKey,
      name: unit.name.replace(/^TFT\d+_/, ''),
      cost: getChampionCost(unit.name),  // Look up from data
      stars: parseInt(unit.level) as 1 | 2 | 3,
      items: parseItems(unit),
      position: { row, col }
    };
  });
}
```

---

## Files Reference

| Purpose | File |
|---------|------|
| Champion data | `data/game_data/champions.jsonl` |
| Item data | `data/game_data/items.jsonl` |
| Champion images | `app/frontend/images/champion images/` |
| Item images | `app/frontend/images/craftable items images/` |
| Log parser | `app/watcher/parser.py` |
| Game state | `app/state/game_state.py` |
| WebSocket | `app/server/websocket.py` |
| Frontend components | `app/frontend/` |

---

## Quick Start

1. **Start the backend:**
   ```bash
   python -m app.main
   ```

2. **Start the frontend:**
   ```bash
   npm start
   ```

3. **Play a TFT game** with MetaTFT running

4. **Board data flows:** Logs/Redux → State Manager → WebSocket → Frontend
