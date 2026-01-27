# TFT Coach Prototype Plan

## Vision

Build a personal TFT coaching overlay that:
1. **Piggybacks off MetaTFT logs** for real-time game data
2. **Adds your personal strategies** and success patterns
3. **Provides actionable advice** during games

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         TFT Game                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MetaTFT (Overwolf)                           │
│              Captures game events via GEP API                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Writes logs
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              MetaTFT Log Files (.log)                           │
│   C:\Users\<USER>\AppData\Local\Overwolf\Log\Apps\MetaTFT\      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ File watching
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Log Watcher Service (Python)                    │
│  • Monitors log file changes                                    │
│  • Parses events into structured data                           │
│  • Maintains game state                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Coach Engine (Python)                         │
│  • Applies your personal rules/strategies                       │
│  • Generates coaching suggestions                               │
│  • Tracks patterns from your past games                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Overlay UI (Electron/Web)                     │
│  • Shows current game state                                     │
│  • Displays coaching suggestions                                │
│  • Your personal notes/reminders                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core Infrastructure (MVP)

### 1.1 Log Watcher Service
**Goal:** Real-time parsing of MetaTFT logs

**Files to create:**
```
app/
├── services/
│   └── log_watcher/
│       ├── __init__.py
│       ├── watcher.py        # File system watcher
│       ├── parser.py         # Log line parser
│       └── events.py         # Event type definitions
```

**Key events to capture:**
- Stage changes (`[EVT] stage: X-X`)
- Augment options (`augment_options: [...]`)
- Item selections (`item_select: {...}`)
- Player health updates
- XP changes
- Scouting events

### 1.2 Game State Model
**Goal:** Reconstruct full game state from log events

```python
@dataclass
class GameState:
    stage: str                    # "2-1", "3-4", etc.
    round_type: str               # "pvp", "pve", "carousel", "augment"

    # Player state
    player_name: str
    health: int
    level: int
    xp: str                       # "2/6"
    gold: int
    win_streak: int
    loss_streak: int

    # Board state
    board_units: List[Unit]
    bench_units: List[Unit]

    # Augments
    augments: List[str]           # Selected augments
    augment_options: List[str]    # Current choices (during armory)

    # Other players
    opponents: List[Opponent]

    # Meta
    game_start_time: datetime
    last_update: datetime
```

### 1.3 WebSocket Server
**Goal:** Push real-time updates to overlay

```python
# Simple FastAPI + WebSocket
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Subscribe to game state updates
    async for state in game_state_stream():
        await websocket.send_json(state.to_dict())
```

---

## Phase 2: Personal Strategy Layer

### 2.1 Strategy Rules Engine
**Goal:** Define your personal rules that trigger suggestions

```python
# Example rule definitions
rules = [
    {
        "name": "Early Sivir",
        "trigger": {"stage": "1-*", "shop_contains": "TFT16_Sivir"},
        "suggestion": "Consider buying Sivir - strong early game carry"
    },
    {
        "name": "Level 8 timing",
        "trigger": {"stage": "4-2", "level": 7, "gold": ">= 50"},
        "suggestion": "Good spot to level to 8 and roll for upgrades"
    },
    {
        "name": "Augment synergy",
        "trigger": {"augment_option": "TFT_Augment_JeweledLotus", "has_trait": "Sorcerer"},
        "suggestion": "Jeweled Lotus is great with your AP comp!"
    }
]
```

### 2.2 Personal Notes System
**Goal:** Add notes tied to specific game situations

```yaml
# personal_notes.yaml
augments:
  TFT_Augment_PortableForge:
    note: "Always take if offered early - flexibility is key"
    priority: "S-tier for me"

champions:
  TFT16_Ekko:
    note: "My comfort pick - prioritize early"
    items: ["TFT_Item_Deathblade", "TFT_Item_LastWhisper", "TFT_Item_GuardianAngel"]

situations:
  low_hp_stage_4:
    condition: "health < 40 AND stage starts with '4-'"
    note: "Time to all-in! Don't save gold"
```

### 2.3 Game History Tracking
**Goal:** Learn from your own patterns

```python
# Track outcomes per decision
game_history = {
    "augments_taken": {
        "TFT_Augment_JeweledLotus": {
            "times_taken": 15,
            "avg_placement": 3.2,
            "with_sorcerer": {"times": 8, "avg": 2.1},
            "without_sorcerer": {"times": 7, "avg": 4.5}
        }
    }
}
```

---

## Phase 3: Overlay UI

### 3.1 Simple Web Overlay
**Goal:** Display coaching info in-game

**Components:**
1. **Stage/Round indicator** - Current phase
2. **Suggestion panel** - Active coaching tips
3. **Augment helper** - Your notes on current options
4. **Personal reminders** - Situation-based notes

**Tech options:**
- **Electron** - Standalone overlay app (always on top)
- **OBS Browser Source** - If streaming
- **Simple HTML + WebSocket** - For testing

### 3.2 Minimal MVP UI

```
┌─────────────────────────────────┐
│ Stage: 2-5 | HP: 78 | Lvl: 5   │
├─────────────────────────────────┤
│ 💡 Suggestion:                  │
│ "Good stage to push levels -    │
│  you usually do well when       │
│  hitting 6 before wolves"       │
├─────────────────────────────────┤
│ 📝 Your Notes:                  │
│ "Look for Sivir pairs"          │
│ "Don't greed carousel"          │
└─────────────────────────────────┘
```

---

## Implementation Order

### Week 1: Foundation
1. [ ] Set up Python project structure
2. [ ] Build log file watcher (watchdog library)
3. [ ] Create event parser for key events
4. [ ] Test with live game

### Week 2: Game State
1. [ ] Design game state data model
2. [ ] Build state reconstruction from events
3. [ ] Add WebSocket server
4. [ ] Create simple HTML test page

### Week 3: Personal Layer
1. [ ] Create rules engine
2. [ ] Add personal notes YAML system
3. [ ] Build suggestion generator
4. [ ] Wire suggestions to UI

### Week 4: Polish
1. [ ] Build proper overlay (Electron)
2. [ ] Add game history tracking
3. [ ] Improve rule matching
4. [ ] Test in ranked games

---

## Tech Stack

```
Backend:
├── Python 3.11+
├── watchdog          # File system monitoring
├── FastAPI           # HTTP/WebSocket server
├── pydantic          # Data validation
└── SQLite            # Game history storage

Frontend:
├── Electron          # Overlay window
├── React or Svelte   # UI framework
└── TailwindCSS       # Styling

Data:
├── YAML              # Personal notes/rules
├── JSON              # Game state
└── SQLite            # History
```

---

## Quick Start Prototype

To get something running ASAP, we can start with:

1. **Single Python script** that:
   - Watches `background.html.log`
   - Prints parsed events to console
   - Shows stage changes in real-time

2. **Test it** during one game to validate parsing

3. **Add WebSocket** to push to a browser page

4. **Iterate** based on what data is most useful

---

## Files to Create First

```
tft-coach-234/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration
│   │
│   ├── watcher/
│   │   ├── __init__.py
│   │   ├── log_watcher.py      # File monitoring
│   │   └── parser.py           # Event parsing
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── game_state.py       # State model
│   │   └── state_manager.py    # State updates
│   │
│   ├── coach/
│   │   ├── __init__.py
│   │   ├── rules.py            # Rule engine
│   │   └── suggestions.py      # Suggestion generator
│   │
│   └── server/
│       ├── __init__.py
│       └── websocket.py        # WebSocket server
│
├── data/
│   ├── personal_notes.yaml     # Your notes
│   ├── rules.yaml              # Custom rules
│   └── history.db              # Game history
│
├── overlay/
│   └── index.html              # Simple test UI
│
└── requirements.txt
```

---

## Success Metrics

**Prototype is successful if:**
1. Can see stage changes in real-time during a game
2. Can detect when augment armory opens
3. Can show a personal note based on current situation
4. Latency < 500ms from game event to overlay display

---

## Questions to Answer

1. **What situations do you want coaching for most?**
   - Augment selection?
   - Level timing?
   - Item prioritization?
   - Positioning?

2. **What are your personal "rules" that you want to codify?**
   - Specific augments you always/never take?
   - Level timings that work for you?
   - Champions you prioritize?

3. **How do you want to see the overlay?**
   - Second monitor?
   - In-game overlay?
   - Audio cues?
