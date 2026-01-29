# Live Board Data Integration Guide

> How to get real-time TFT board data for the overlay

---

## Data Source

MetaTFT/Overwolf logs provide real-time board state through file monitoring.

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

**Important:** Overwolf does NOT provide direct opponent board data.

Options:
1. **Skip opponent board** in overlay (show only player board)
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
MetaTFT Logs → Log Watcher → Parser → State Manager → WebSocket → Overlay
     ↑                                                              ↓
  Overwolf GEP                                              React Components
```

### What Needs to Be Done

1. **Add `tft_board` parsing** to `parser.py` (if not already there)
2. **Add board state** to `game_state.py` model
3. **Connect overlay** to existing WebSocket
4. **Transform data** from parsed format to `PositionedUnit[]`

---

## Transformation: Log Data → Overlay Format

### Input (from logs)
```json
{
  "cell_1": {"name": "TFT16_KogMaw", "level": "2", "item_1": "TFT_Item_BFSword", "item_2": "", "item_3": ""}
}
```

### Output (for overlay)
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
| Champion images | `overlay/images/champion images/` |
| Item images | `overlay/images/craftable items images/` |
| Log parser | `app/watcher/parser.py` |
| Game state | `app/state/game_state.py` |
| WebSocket | `app/server/websocket.py` |
| Overlay components | `overlay/` |

---

## Quick Start

1. **Start the backend:**
   ```bash
   cd app && python main.py
   ```

2. **Start the overlay:**
   ```bash
   cd overlay && npm run dev
   ```

3. **Play a TFT game** with MetaTFT running

4. **Board data flows:** Logs → Parser → WebSocket → Overlay
