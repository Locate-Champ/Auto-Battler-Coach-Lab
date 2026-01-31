# TFT Coach 234 - Complete Project Overview

> **Purpose:** This document provides everything an AI/LLM needs to understand and rebuild this project in Notion or any other project management tool.

---

## 1. Project Structure

```
tft-coach-234/
├── app/                          # Main Python application
│   ├── main.py                   # Entry point - WebSocket + log watcher
│   ├── config.py                 # Configuration (paths, ports, etc.)
│   ├── api/
│   │   └── server.py             # FastAPI REST API + endpoints
│   ├── frontend/                 # TypeScript React + Vite + TailwindCSS (PRIMARY)
│   │   ├── package.json
│   │   ├── vite.config.ts        # Vite config with proxy
│   │   ├── tsconfig.json         # TypeScript configuration
│   │   ├── src/
│   │   │   ├── App.tsx           # Main React component
│   │   │   ├── main.tsx          # React entry point
│   │   │   └── index.css         # Tailwind styles
│   │   ├── hooks/                # React hooks
│   │   │   ├── useGameState.ts   # WebSocket connection
│   │   │   ├── useMetaComps.ts   # Meta comps fetching
│   │   │   ├── useEarlyComps.ts  # Early game comps
│   │   │   └── usePoolTracker.ts # Unit pool tracking
│   │   ├── utils/
│   │   │   └── transformBoardData.ts  # Champion name mappings
│   │   ├── images/               # 400+ champion/item images
│   │   ├── CoachingPanel.tsx     # Stage-specific tips
│   │   ├── CompsPanel.tsx        # Meta comps display
│   │   ├── LiveBoard.tsx         # WebSocket-connected board
│   │   ├── DualBoard.tsx         # Player + opponent boards
│   │   ├── MetaCompCard.tsx      # Comp tier display
│   │   └── ItemsBar.tsx          # Item category tabs
│   ├── redux_bridge/             # Live data extraction from MetaTFT
│   │   ├── inject.js             # Browser injection script
│   │   └── handler.py            # WebSocket handler
│   ├── server/
│   │   └── websocket.py          # WebSocket server for live updates
│   ├── state/
│   │   ├── game_state.py         # GameState data model
│   │   └── state_manager.py      # Event processing
│   └── watcher/
│       ├── log_watcher.py        # File system watcher (watchdog)
│       └── parser.py             # Log event parser (11+ event types)
│
├── src/                          # ML models and data processing
│   ├── metatft_parser.py         # MetaTFT log parser
│   ├── tft_diagnostic.py         # Data validation utilities
│   └── models/
│       ├── feature_engineering.py # Feature extraction
│       ├── placement_model.py     # ML placement prediction
│       └── recommender.py         # Recommendation engine
│
├── scripts/                      # Utility scripts
│   ├── fetch_early_comps.py      # Fetch early game comp data
│   ├── fetch_meta_data.py        # Fetch current meta data
│   ├── organize_api_data.py      # API data organization
│   └── sync_metatft.py           # MetaTFT data sync
│
├── data/                         # All data files
│   ├── personal/                 # Personal match history
│   │   └── tft_since_16_2_enhanced.csv  # 163 matches
│   ├── game_data/                # Set 16 reference data (JSONL)
│   │   ├── champions.jsonl
│   │   ├── traits.jsonl
│   │   ├── items.jsonl
│   │   └── augments.jsonl
│   ├── meta/                     # Current meta data
│   └── api/                      # API response caches
│
├── docs/                         # Documentation
├── archive/                      # Archived code
│   └── old_frontend/             # Previous JavaScript frontend
│
├── start.sh                      # Single command launcher
├── package.json                  # Root npm scripts
├── requirements.txt              # Python dependencies
└── CLAUDE.md                     # Main AI assistant guide
```

---

## 2. Project Objective

Build a TFT coaching companion that provides ML-powered placement predictions and actionable recommendations based on:
1. Historical match performance data (163 games analyzed)
2. Live board state integration via MetaTFT/Overwolf logs
3. Current meta data from community sources

**Primary Goal:** Predict placement outcomes and recommend optimal strategies aligned with the user's late-game AP/utility playstyle (70-100% top 4 rate with 5-cost carries like Fiddlesticks, Ornn, Ryze).

### Key Insights from Analysis (163 matches)
- **Overall top 4 rate:** 52%
- **AD carries:** 0% top 4 (AVOID)
- **Late-game AP/utility (5-cost carries):** 70-100% top 4
- **Optimal carries:** Fiddlesticks, Ornn, Ryze
- **Underperforming:** AD carries, Bilgewater synergies
- **Strength:** Longer games, higher levels = better outcomes

### Success Criteria
1. Model achieves >60% accuracy on top 4 vs bottom 4 classification
2. Feature importance aligns with known performance patterns (AP > AD)
3. Recommendations avoid underperforming strategies
4. System can process live game state in <1 second

---

## 3. Configuration

### app/config.py
```python
@dataclass
class Config:
    # MetaTFT log directory (Windows path)
    metatft_log_dir: Path = Path(
        os.path.expandvars(r"%LOCALAPPDATA%\Overwolf\Log\Apps\MetaTFT")
    )

    # Key log files to watch
    log_files: list[str] = ["background.html.log", "win_chance.html.log"]

    # WebSocket server
    host: str = "127.0.0.1"
    port: int = 8765

    # Data directory
    data_dir: Path = Path(__file__).parent.parent / "data"
```

### Ports Summary
| Service | Port | Protocol |
|---------|------|----------|
| Frontend UI | 5173 | HTTP |
| REST API | 8000 | HTTP |
| WebSocket | 8765 | WS |

---

## 4. Data Schemas

### Match Data (tft_since_16_2_enhanced.csv) - 163 records
**Headers:**
```
match_id,game_datetime,game_length_sec,queue_id,game_version,placement,level,gold_left,last_round,time_eliminated,total_damage_to_players,players_eliminated,aug1,aug2,aug3,traits_active,final_board_units
```

**Key Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `match_id` | string | Riot match ID (NA1_XXXXXXXXXX) |
| `placement` | int | TARGET: 1-8 finish position |
| `level` | int | Final level (6-10) |
| `traits_active` | string | Pipe-delimited "Trait:Count" |
| `final_board_units` | string | "UnitName_StarLevel*(Item1,Item2,Item3)" |

### Carry Performance (carry_performance_corrected.csv) - 22 records
```
carry,cost,games,top4_rate,win_rate,avg_placement
Fiddlesticks,5,4,100.0,25.0,1.75
Ornn,5,7,100.0,28.57,2.14
```

### Game Data Files (JSONL)
| File | Records | Purpose |
|------|---------|---------|
| champions.jsonl | 101 | Champion base stats & abilities |
| augments.jsonl | 208 | Augment definitions |
| traits.jsonl | 53 | Trait breakpoints |
| items.jsonl | 444 | All items |

---

## 5. Main Scripts

### Entry Point: app/main.py
- `TFTCoach` class orchestrates:
  - `StateManager` - game state reconstruction
  - `LogWatcher` - MetaTFT log monitoring
  - `WebSocketServer` - real-time client updates
- CLI args: `--no-server`, `--port`

### Log Parser: app/watcher/parser.py
Event types detected:
- `STAGE_CHANGE` - "2-1", "3-4", etc.
- `XP_CHANGE` - "0/6 -> 2/6"
- `HEALTH_UPDATE` - player HP tracking
- `AUGMENT_ARMORY` - augment choices
- `WIN_CHANCE` - ~96% predictions
- `SCOUTING` - opponent board views
- `GAME_START` / `GAME_END`

### Game State: app/state/game_state.py
```python
@dataclass
class GameState:
    game_phase: GamePhase  # NOT_IN_GAME, LOADING, CAROUSEL, PVE, PVP, AUGMENT
    stage: str             # "2-1"
    player: PlayerState    # name, health, level, board_units, traits
    xp: str
    gold: int
    augments: list[str]
    opponents: dict[str, PlayerState]
    win_chance: Optional[int]
```

### API Server: app/api/server.py
FastAPI endpoints:
- `GET /api/stats` - personal carry/trait stats
- `GET /api/meta-comps` - MetaTFT meta compositions
- `GET /api/early-comps` - early game compositions
- `GET /api/comps/{stage}` - best comps for stage
- `GET /api/augments` - augment recommendations
- `POST /api/recommend` - board analysis + suggestions
- `GET /api/priority-units` - units to look for
- `GET /api/items` - build/avoid item suggestions

---

## 6. Frontend (React + TypeScript + Vite)

### package.json Dependencies
```json
{
  "dependencies": {
    "react": "^18.x",
    "react-dom": "^18.x"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.x",
    "tailwindcss": "^4.x",
    "typescript": "^5.x",
    "vite": "^7.x"
  }
}
```

### Main Components (App.tsx)
1. **Header** - Live/offline status
2. **TraitsPanel** - Active traits display
3. **LobbyTracker** - Comp contestation counter
4. **HexBoard** - Hex grid board visualization
5. **ItemsBar** - Item category tabs
6. **CoachingPanel** - Stage-specific tips
7. **MetaCompCard** - Meta comp with tiers

### React Hooks
- `useGameState` - WebSocket connection with auto-reconnect
- `useMetaComps` - Meta compositions fetching
- `useEarlyComps` - Early game comps
- `usePoolTracker` - Unit pool state tracking

---

## 7. Dependencies

### requirements.txt (Python)
```
# Web server
fastapi>=0.100.0
uvicorn>=0.23.0
websockets>=12.0

# Data processing
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
pydantic>=2.5.0

# Log watching
watchdog>=3.0.0

# Config/storage
pyyaml>=6.0.1
aiosqlite>=0.19.0
python-dateutil>=2.8.2
```

---

## 8. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
├─────────────────────────────────────────────────────────────┤
│  MetaTFT Logs          Redux Store           Post-Game API  │
│  (Overwolf)            (inject.js)           (DigitalOcean) │
└──────┬───────────────────┬─────────────────────┬────────────┘
       │                   │                     │
       ▼                   ▼                     │
┌──────────────────────────────────────────┐    │
│           Log Watcher + Parser            │    │
│    app/watcher/log_watcher.py            │    │
│    app/watcher/parser.py                 │    │
└──────────────────┬───────────────────────┘    │
                   │                            │
                   ▼                            │
┌──────────────────────────────────────────┐    │
│           State Manager                   │    │
│    app/state/state_manager.py            │    │
│    app/state/game_state.py               │◄───┘
└──────────────────┬───────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐     ┌───────────────┐
│  WebSocket    │     │   REST API    │
│  :8765/ws     │     │   :8000       │
└───────┬───────┘     └───────┬───────┘
        │                     │
        └──────────┬──────────┘
                   ▼
┌─────────────────────────────────────────┐
│      TypeScript React Frontend           │
│       app/frontend/ (port 5173)          │
│   Vite proxy forwards /api and /ws      │
└─────────────────────────────────────────┘
```

---

## 9. Quick Start Commands

```bash
# Single command to run everything
npm start
# Or: ./start.sh

# Frontend only
cd app/frontend && npm run dev

# Backend only
python -m app.main

# API server only
python -m app.api.server

# Install dependencies
pip install -r requirements.txt
cd app/frontend && npm install
```

---

## 10. Parsing Utilities

### Parse Traits String
```python
def parse_traits(trait_str):
    if pd.isna(trait_str):
        return {}
    return dict(re.findall(r'(\w+):(\d+)', trait_str))
# "Brawler:1 | Void:3" -> {"Brawler": "1", "Void": "3"}
```

### Parse Units String
```python
def parse_units(unit_str):
    if pd.isna(unit_str):
        return []
    pattern = r'(\w+)_(\d)\*\(([^)]*)\)'
    return [(name, int(stars), items.split(',') if items else [])
            for name, stars, items in re.findall(pattern, unit_str)]
# "KogMaw_2*()" -> [("KogMaw", 2, [])]
```

---

## 11. Key Data Files Reference

| Category | File | Records | Purpose |
|----------|------|---------|---------|
| Personal | tft_since_16_2_enhanced.csv | 163 | Match history with full data |
| Personal | carry_performance_corrected.csv | 22 | Carry unit stats |
| Personal | trait_performance_corrected.csv | 54 | Trait synergy stats |
| Personal | item_performance_corrected.csv | 47 | Item build stats |
| Game Data | champions.jsonl | 101 | Champion base stats |
| Game Data | augments.jsonl | 208 | Augment definitions |
| Game Data | traits.jsonl | 53 | Trait breakpoints |
| Game Data | items.jsonl | 444 | All items |

---

## 12. Model Building Objectives

### Phase 1: Placement Prediction (COMPLETE)
- **Target:** `placement` (1-8)
- **Features:** Trait counts, unit composition, game state, items, augments
- **Approach:** Random Forest / XGBoost for interpretability
- **Note:** Small dataset (163 games) - avoid overfitting

### Phase 2: Recommendation Engine (COMPLETE)
1. Optimal pivots when underperforming
2. Item prioritization based on board
3. Augment selection with personal performance

### Phase 3: Live Integration (IN PROGRESS)
- MetaTFT/Overwolf for real-time board state
- Contestation tracking
- Real-time placement projections

---

*Generated: 2026-01-31 | TFT Set 16.3*
