# Auto-Battler Coach Prototype Plan

## Vision

Build a personal Auto-Battler Coaching overlay that:
1. **Piggybacks off MetaTFT logs** for real-time game data
2. **Adds your personal strategies** and success patterns
3. **Provides actionable advice** during games

---

## Architecture Overview

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                         Game Client                                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚
                           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    MetaTFT (Overwolf)                           â”‚
â”‚              Captures game events via GEP API                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ Writes logs
                           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              MetaTFT Log Files (.log)                           â”‚
â”‚   C:\Users\<USER>\AppData\Local\Overwolf\Log\Apps\MetaTFT\      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ File watching
                           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                 Log Watcher Service (Python)                    â”‚
â”‚  â€¢ Monitors log file changes                                    â”‚
â”‚  â€¢ Parses events into structured data                           â”‚
â”‚  â€¢ Maintains game state                                         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ WebSocket
                           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                   Coach Engine (Python)                         â”‚
â”‚  â€¢ Applies your personal rules/strategies                       â”‚
â”‚  â€¢ Generates coaching suggestions                               â”‚
â”‚  â€¢ Tracks patterns from your past games                         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ HTTP/WebSocket
                           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                   Overlay UI (Electron/Web)                     â”‚
â”‚  â€¢ Shows current game state                                     â”‚
â”‚  â€¢ Displays coaching suggestions                                â”‚
â”‚  â€¢ Your personal notes/reminders                                â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Phase 1: Core Infrastructure (MVP)

### 1.1 Log Watcher Service
**Goal:** Real-time parsing of MetaTFT logs

**Files to create:**
```
app/
â”œâ”€â”€ services/
â”‚   â””â”€â”€ log_watcher/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â”œâ”€â”€ watcher.py        # File system watcher
â”‚       â”œâ”€â”€ parser.py         # Log line parser
â”‚       â””â”€â”€ events.py         # Event type definitions
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
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ Stage: 2-5 | HP: 78 | Lvl: 5   â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ ðŸ’¡ Suggestion:                  â”‚
â”‚ "Good stage to push levels -    â”‚
â”‚  you usually do well when       â”‚
â”‚  hitting 6 before wolves"       â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ ðŸ“ Your Notes:                  â”‚
â”‚ "Look for Sivir pairs"          â”‚
â”‚ "Don't greed carousel"          â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
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
â”œâ”€â”€ Python 3.11+
â”œâ”€â”€ watchdog          # File system monitoring
â”œâ”€â”€ FastAPI           # HTTP/WebSocket server
â”œâ”€â”€ pydantic          # Data validation
â””â”€â”€ SQLite            # Game history storage

Frontend:
â”œâ”€â”€ Electron          # Overlay window
â”œâ”€â”€ React or Svelte   # UI framework
â””â”€â”€ TailwindCSS       # Styling

Data:
â”œâ”€â”€ YAML              # Personal notes/rules
â”œâ”€â”€ JSON              # Game state
â””â”€â”€ SQLite            # History
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
Auto-Battler-Coach-Lab/
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ __init__.py
â”‚   â”œâ”€â”€ main.py                 # Entry point
â”‚   â”œâ”€â”€ config.py               # Configuration
â”‚   â”‚
â”‚   â”œâ”€â”€ watcher/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ log_watcher.py      # File monitoring
â”‚   â”‚   â””â”€â”€ parser.py           # Event parsing
â”‚   â”‚
â”‚   â”œâ”€â”€ state/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ game_state.py       # State model
â”‚   â”‚   â””â”€â”€ state_manager.py    # State updates
â”‚   â”‚
â”‚   â”œâ”€â”€ coach/
â”‚   â”‚   â”œâ”€â”€ __init__.py
â”‚   â”‚   â”œâ”€â”€ rules.py            # Rule engine
â”‚   â”‚   â””â”€â”€ suggestions.py      # Suggestion generator
â”‚   â”‚
â”‚   â””â”€â”€ server/
â”‚       â”œâ”€â”€ __init__.py
â”‚       â””â”€â”€ websocket.py        # WebSocket server
â”‚
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ personal_notes.yaml     # Your notes
â”‚   â”œâ”€â”€ rules.yaml              # Custom rules
â”‚   â””â”€â”€ history.db              # Game history
â”‚
â”œâ”€â”€ overlay/
â”‚   â””â”€â”€ index.html              # Simple test UI
â”‚
â””â”€â”€ requirements.txt
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

