# Live Data Integration Progress

> Tracking implementation progress for connecting overlay to live game data

**Last Updated:** 2026-01-29

---

## Overview

Connecting the TFT overlay to real-time game data from MetaTFT/Overwolf logs.

---

## Progress

### ✅ Completed

| Task | File | Notes |
|------|------|-------|
| Document data format | `docs/LIVE_BOARD_DATA_GUIDE.md` | Cell ID mapping, champion/item formats |
| Analyze existing parser | `app/watcher/parser.py` | Found 11 event types, missing board data |
| Analyze game state | `app/state/game_state.py` | Unit/PlayerState exist, need wiring |
| Add BOARD_UPDATE event type | `app/watcher/parser.py` | ✅ Added |
| Add BENCH_UPDATE event type | `app/watcher/parser.py` | ✅ Added |
| Add ROSTER_UPDATE event type | `app/watcher/parser.py` | ✅ Added |
| Add board/bench/roster regex | `app/watcher/parser.py` | ✅ Patterns added |
| Add parse handlers | `app/watcher/parser.py` | ✅ JSON parsing with unescape |
| Handle board_update | `app/state/state_manager.py` | ✅ Converts to Unit objects |
| Handle bench_update | `app/state/state_manager.py` | ✅ Converts to Unit objects |
| Handle roster_update | `app/state/state_manager.py` | ✅ Updates player/opponent health |
| Serialize board_units | `app/state/game_state.py` | ✅ Added to to_dict() |
| Serialize bench_units | `app/state/game_state.py` | ✅ Added to to_dict() |

### ⏳ Up Next

| Task | File | Notes |
|------|------|-------|
| Connect overlay to WebSocket | `overlay/` | Subscribe to live updates |
| Create data transformer | `overlay/` | Log format → PositionedUnit[] |
| Add champion cost lookup | `overlay/` | Map TFT16_Name → cost |
| Add item image mapping | `overlay/` | TFT_Item_X → image file |
| Test with live game | - | End-to-end verification |

---

## Implementation Details

### Parser Updates (`app/watcher/parser.py`)

**New event types added:**
```python
BOARD_UPDATE = "board_update"
BENCH_UPDATE = "bench_update"
ROSTER_UPDATE = "roster_update"
```

**Regex patterns:**
```python
"board": re.compile(r'"key":"tft_board","value":"(\{[^}]+(?:\}[^}]+)*\})"'),
"bench": re.compile(r'"key":"tft_bench","value":"(\{[^}]+(?:\}[^}]+)*\})"'),
"roster": re.compile(r'"key":"tft_roster","value":"(\[[^\]]+\])"'),
```

**Parse handlers:** Extract JSON, unescape quotes, parse to dict/list.

### State Manager Updates (`app/state/state_manager.py`)

**`_handle_board_update()`:**
- Parses `cell_X` keys to (row, col) positions
- Creates `Unit` objects with character_id, star_level, items, position
- Updates `self.state.player.board_units`

**`_handle_bench_update()`:**
- Parses `slot_X` keys
- Creates `Unit` objects (no position)
- Updates `self.state.bench_units`

**`_handle_roster_update()`:**
- Identifies local player via `localplayer == "1"`
- Updates player name and health
- Updates opponent health in `self.state.opponents`

### Game State Updates (`app/state/game_state.py`)

**`to_dict()` now includes:**
```python
"board_units": [
    {
        "id": "cell_X",
        "character_id": "TFT16_Ekko",
        "name": "Ekko",
        "stars": 2,
        "items": ["TFT_Item_BFSword"],
        "position": {"row": 0, "col": 1}
    },
    ...
],
"bench_units": [...]
```

---

## Files Modified

| File | Changes |
|------|---------|
| `app/watcher/parser.py` | +3 event types, +3 regex patterns, +3 parse handlers |
| `app/state/state_manager.py` | +3 event handlers (board, bench, roster) |
| `app/state/game_state.py` | +board_units, +bench_units in to_dict() |

---

## Data Flow (Now Working)

```
MetaTFT Logs
     ↓
Log Watcher (watches for changes)
     ↓
Parser (extracts tft_board, tft_bench, tft_roster)
     ↓
State Manager (converts to Unit objects)
     ↓
Game State (board_units, bench_units populated)
     ↓
WebSocket (broadcasts state to clients)
     ↓
Overlay (needs: subscribe + transform)
```

---

## What's Left

1. **Overlay WebSocket connection** - Subscribe to state updates
2. **Data transformer** - Convert `board_units[]` → `PositionedUnit[]`
3. **Champion cost lookup** - Need to map TFT16_Name → cost (1-5)
4. **Item image mapping** - TFT_Item_X → local image file name
5. **Testing** - Run with live game to verify end-to-end

---

## Notes

- Overwolf does NOT provide opponent board data directly
- Only player board (`tft_board`) and bench (`tft_bench`) available
- Roster data (`tft_roster`) gives health/xp for all 8 players
- Cell IDs: 0-6 = row 0, 7-13 = row 1, 14-20 = row 2, 21-27 = row 3
