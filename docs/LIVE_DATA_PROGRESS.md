# Live Data Integration Progress

> Tracking implementation progress for connecting overlay to live game data

**Last Updated:** 2026-01-30

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

| Create WebSocket hook | `overlay/hooks/useGameState.ts` | ✅ Auto-reconnect, state management |
| Create data transformer | `overlay/utils/transformBoardData.ts` | ✅ Log format → PositionedUnit[] |
| Add champion cost lookup | `overlay/utils/transformBoardData.ts` | ✅ All Set 16 champions mapped |
| Add item image mapping | `overlay/utils/transformBoardData.ts` | ✅ Component + completed items |
| Create LiveBoard component | `overlay/LiveBoard.tsx` | ✅ Connects WS to DualBoard |
| Add live data toggle | `overlay/src/App.tsx` | ✅ Switch between sample/live |

### ⏳ Up Next

| Task | File | Notes |
|------|------|-------|
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

### Overlay WebSocket Hook (`overlay/hooks/useGameState.ts`)

**Features:**
- Connects to `ws://127.0.0.1:8765/ws`
- Auto-reconnect on disconnect (3s interval)
- Returns `{ state, isConnected, error, reconnect }`

**Usage:**
```tsx
const { state, isConnected, error } = useGameState();
const playerUnits = state?.board_units ? transformBoardUnits(state.board_units) : [];
```

### Data Transformer (`overlay/utils/transformBoardData.ts`)

**Functions:**
- `getChampionCost(characterId)` - Returns cost 1-5 for TFT16 champions
- `getChampionName(characterId)` - Strips TFT16_ prefix
- `parseItem(itemId)` - Converts item ID to `{name, imageFile}`
- `transformBoardUnits(units)` - Converts backend format to `PositionedUnit[]`

**Champion costs:** All 106 Set 16 champions mapped (1-cost through 5-cost)

**Item mappings:** 9 components + 30 completed items with display names and image files

### LiveBoard Component (`overlay/LiveBoard.tsx`)

**Features:**
- Shows connection status (green/red indicator)
- Displays player name, health, stage
- Uses sample opponent data (Overwolf doesn't provide opponent board)
- Shows debug info: phase, XP, win chance, bench units, augments

---

## Files Modified

### Backend
| File | Changes |
|------|---------|
| `app/watcher/parser.py` | +3 event types, +3 regex patterns, +3 parse handlers |
| `app/state/state_manager.py` | +3 event handlers (board, bench, roster) |
| `app/state/game_state.py` | +board_units, +bench_units in to_dict() |

### Frontend (Overlay)
| File | Changes |
|------|---------|
| `overlay/hooks/useGameState.ts` | New: WebSocket hook with auto-reconnect |
| `overlay/utils/transformBoardData.ts` | New: Data transformer, champion costs, item mappings |
| `overlay/LiveBoard.tsx` | New: Component connecting WebSocket to DualBoard |
| `overlay/src/App.tsx` | Updated: Added toggle for live/sample data |

---

## Data Flow (Complete)

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
useGameState hook (receives state updates)
     ↓
transformBoardUnits (converts to PositionedUnit[])
     ↓
LiveBoard → DualBoard (renders units on hex grid)
```

---

## What's Left

1. ~~**Overlay WebSocket connection**~~ ✅ Done
2. ~~**Data transformer**~~ ✅ Done
3. ~~**Champion cost lookup**~~ ✅ Done
4. ~~**Item image mapping**~~ ✅ Done
5. **Testing** - Run with live game to verify end-to-end

### Testing Checklist
- [ ] Start backend: `python -m app.main`
- [ ] Start overlay: `cd overlay && npm run dev`
- [ ] Click "○ Sample Data" toggle to switch to "● LIVE"
- [ ] Start a TFT game with MetaTFT running
- [ ] Verify units appear on player board
- [ ] Verify items display correctly
- [ ] Verify star levels show correctly

---

## Notes

- Overwolf does NOT provide opponent board data directly via GEP
- Only player board (`tft_board`) and bench (`tft_bench`) available from logs
- Roster data (`tft_roster`) gives health/xp for all 8 players
- Cell IDs: 0-6 = row 0, 7-13 = row 1, 14-20 = row 2, 21-27 = row 3

---

## Alternative Data Source: MetaTFT App Matches (UUID-based)

### Discovery
MetaTFT stores detailed round-by-round data (including ALL 8 players' boards) in DigitalOcean:

```
https://metatft-matches-2.ams3.digitaloceanspaces.com/{UUID}.json
```

### Data Available (from app_matches)
| Feature | Available | Details |
|---------|-----------|---------|
| Unit positions | ✅ Yes | 3D coords (x, z, y) AND hex codes ("D4", "A_5", "F1") |
| Round-by-round snapshots | ✅ Yes | `stage_data` array with one entry per round |
| All 8 boards per round | ✅ Yes | `board_data` contains board_1 through board_8 + benches |
| Your bench | ✅ Yes | Separate bench tracking with positions |
| Augments | ✅ Yes | All 3 augment choices tracked |
| APM/Actions | ✅ Yes | Mouse actions, keyboard actions, APM per round |
| Scouting time | ✅ Yes | Milliseconds spent viewing opponent boards |
| Repositions | ✅ Yes | Count of unit moves per round |
| Gold earned | ✅ Yes | Economy tracking per round |
| Damage breakdown | ✅ Yes | Per-unit damage dealt |
| Shop offerings | ✅ Yes | What appeared in your shop |
| Matchup boards | ✅ Yes | Your board vs opponent's board for each fight |

### How to Access
1. **Requirement:** Must be signed into Overwolf (not just MetaTFT UI)
2. **Account UUID:** Visible in `background.html.log` → `UserParams` when authenticated
3. **Per-game UUID:** Generated server-side, available in `app_matches` array of profile JSON
4. **URL Pattern:** `https://metatft-matches-2.ams3.digitaloceanspaces.com/{PER-GAME-UUID}.json`

### Example from 8148.json
```json
{
  "uuid": "19995f27-01da-4ab2-96bc-31c16dcd62fa",
  "match_id_ow": 5476261011,
  "match_data_url": "https://metatft-matches-2.ams3.digitaloceanspaces.com/19995f27-01da-4ab2-96bc-31c16dcd62fa.json"
}
```

---

## UUID Investigation Findings (2026-01-30)

### Two Types of UUIDs

| UUID Type | Example | Where Found | Purpose |
|-----------|---------|-------------|---------|
| **Account UUID** | `237773f1-7522-4e06-a86d-862bcd9ac478` | `background.html.log` → `UserParams.uuid` | Overwolf session ID |
| **Per-game UUID** | `19995f27-01da-4ab2-96bc-31c16dcd62fa` | Profile API → `app_matches[].uuid` | Match data identifier |

### Key Discovery: Per-game UUIDs are NOT in client logs

**Tested:** With fresh logs from a game played while signed into Overwolf (`new metatft data/` folder)

**Findings:**
- ✅ Account UUID appears in logs when signed in: `"uuid":"237773f1-7522-4e06-a86d-862bcd9ac478"`
- ✅ `UserParams` shows `"status":"success"` when properly authenticated
- ❌ Per-game UUIDs do NOT appear in client-side logs
- ❌ Per-game UUIDs are generated **server-side** when MetaTFT uploads match data

### Authentication Check

**Not signed in (broken):**
```json
{"status":"error","Reason":"Not signed in","uuid":null}
```

**Signed in (working):**
```json
{"status":"success","username":"foretisthedude","uuid":"237773f1-..."}
```

### Conclusion: UUID Approach is POST-GAME Only

| Use Case | Approach | Real-time? |
|----------|----------|------------|
| Live overlay during game | Log parsing (current implementation) | ✅ Yes |
| Post-game analysis with all 8 boards | UUID/DigitalOcean fetch | ❌ No (after game ends) |

**Why:** Per-game UUIDs are assigned server-side after MetaTFT uploads match data. They cannot be discovered during the game from client logs.

### Reference Files
- `new metatft data/background.html.log` - Working Overwolf authentication logs
- `data/api/raw/8148.json` - Profile with 252 app_matches containing UUIDs
- `metatft_logs/` - Older logs (before Overwolf sign-in fix)
- `finding metatft data.txt` (main branch) - Original investigation conversation

### Next Steps for Post-Game Analysis
- [ ] Fetch updated profile JSON after game ends
- [ ] Extract new `app_matches` entries with UUIDs
- [ ] Fetch DigitalOcean URLs for detailed round-by-round data
- [ ] Display opponent boards from historical data
