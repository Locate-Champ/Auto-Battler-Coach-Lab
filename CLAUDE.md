# TFT Coach - AI Assistant Guide

> Comprehensive documentation for AI assistants working on this codebase.

---

## Project Overview

**TFT Coach** is a personal coaching companion for Teamfight Tactics (TFT) that provides:
- ML-powered placement predictions based on 163 matches of personal data
- Real-time board state integration via MetaTFT/Overwolf logs
- Stage-aware recommendations aligned with the user's playstyle

**Key Insight:** The user performs significantly better with late-game AP/utility carries (70-100% top 4 rate) compared to AD carries (0% top 4). Recommendations should favor Fiddlesticks, Ornn, Ryze, and similar champions.

---

## Directory Structure

```
tft-coach-234/
├── app/                          # Main Python application
│   ├── main.py                   # Entry point - TFTCoach class
│   ├── config.py                 # Configuration (paths, ports, etc.)
│   ├── api/
│   │   └── server.py             # FastAPI REST endpoints (8 endpoints)
│   ├── frontend/                 # React UI (Vite + Tailwind)
│   │   ├── src/
│   │   │   ├── App.jsx           # Main React component
│   │   │   ├── api.js            # API client functions
│   │   │   └── components/       # React components
│   │   └── package.json
│   ├── redux_bridge/             # Live data extraction from MetaTFT
│   │   ├── inject.js             # Browser injection script
│   │   └── handler.py            # WebSocket handler for Redux data
│   ├── server/
│   │   └── websocket.py          # WebSocket server for live updates
│   ├── state/
│   │   ├── game_state.py         # GameState data model
│   │   └── state_manager.py      # Event processing and state updates
│   └── watcher/
│       ├── log_watcher.py        # File system watcher (watchdog)
│       └── parser.py             # Log event parser (11+ event types)
│
├── overlay/                      # TypeScript overlay (alternative UI)
│   ├── src/App.tsx
│   ├── hooks/useGameState.ts     # WebSocket hook with auto-reconnect
│   ├── utils/transformBoardData.ts
│   ├── LiveBoard.tsx
│   ├── DualBoard.tsx
│   └── CoachingPanel.tsx
│
├── src/                          # ML models and data processing
│   ├── metatft_parser.py         # MetaTFT log parser
│   ├── tft_diagnostic.py         # Data validation utilities
│   └── models/
│       ├── feature_engineering.py # Feature extraction from match data
│       ├── placement_model.py     # ML placement prediction
│       └── recommender.py         # Recommendation engine
│
├── scripts/                      # Utility scripts
│   ├── fetch_early_comps.py      # Fetch early game comp data
│   ├── fetch_meta_data.py        # Fetch current meta data
│   ├── organize_api_data.py      # API data organization
│   ├── pull_riot_matches.py      # Riot API match fetching
│   ├── sync_metatft.py           # MetaTFT data sync
│   ├── watch_logs.py             # Log file watcher
│   └── *.bat                     # Windows batch scripts
│
├── data/                         # All data files
│   ├── personal/                 # Personal match history
│   │   ├── tft_since_16_2_enhanced.csv  # 163 matches (PRIMARY)
│   │   ├── tft_matches_since_set16.csv  # Extended match data
│   │   ├── carry_performance_corrected.csv
│   │   ├── trait_performance_corrected.csv
│   │   └── item_performance_corrected.csv
│   ├── game_data/                # Set 16 reference data (JSONL)
│   │   ├── champions.jsonl
│   │   ├── traits.jsonl
│   │   ├── items.jsonl
│   │   └── augments.jsonl
│   ├── meta/                     # Current meta data
│   ├── api/                      # API response caches
│   │   └── tft_16.3/             # Set 16.3 API data
│   ├── manifest.json             # Data manifest
│   └── metadata.json             # Data source metadata
│
├── docs/                         # Documentation
│   ├── LIVE_DATA_PROGRESS.md     # Live data integration status
│   ├── LIVE_BOARD_DATA_GUIDE.md  # Data format documentation
│   ├── DATA_SCHEMAS.md           # Data schema definitions
│   ├── PROTOTYPE_PLAN.md         # Implementation plan
│   └── TFT_Coach_Figma_Spec.md   # UI design spec
│
├── knowledge-base/               # TFT strategy knowledge
│   └── sources/web-scrape/       # 55+ comp guides
│
├── archive/                      # Archived/reference materials
│   ├── prototypes/               # Legacy UI prototypes
│   │   ├── tft-coach.jsx         # Original React prototype
│   │   ├── tft-coach-preview.html
│   │   ├── ui_design/            # UI mockups and SVGs
│   │   └── web/                  # Static HTML dashboard
│   └── research/                 # Third-party reference code
│       ├── metatft_early_comps_js/
│       ├── tft_odds_js/
│       └── optimize_scripts/
│
├── requirements.txt              # Python dependencies
├── package.json                  # Root npm workspace config
├── DEVELOPMENT_CHECKLIST.md      # Task tracking (52% complete)
├── README.md                     # Project overview
└── CLAUDE.md                     # This file - AI assistant guide
```

---

## Technology Stack

### Backend (Python 3.10+)
- **FastAPI** - REST API server
- **WebSockets** - Real-time communication
- **Watchdog** - File system monitoring
- **Pandas/NumPy** - Data processing
- **Scikit-learn** - ML models (RandomForest, GradientBoosting)
- **PyYAML** - Configuration

### Frontend (Node.js 18+)
- **React 19** - UI framework
- **Vite 7** - Build tool
- **Tailwind CSS 4** - Styling
- **TypeScript** (overlay only)

---

## Architecture & Data Flow

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
│    app/watcher/parser.py (11 event types)│    │
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
        ▼                     ▼
┌─────────────────────────────────────────┐
│              React Frontend              │
│         app/frontend/src/App.jsx         │
└─────────────────────────────────────────┘
```

### Event Types Supported
- `STAGE_CHANGE` - Game stage transitions
- `XP_CHANGE` - Experience updates
- `HEALTH_UPDATE` - Player health changes
- `AUGMENT_ARMORY` - Augment selection windows
- `WIN_CHANCE` - Win probability updates
- `SCOUTING` - Opponent viewing
- `BOARD_UPDATE` - Board state changes
- `BENCH_UPDATE` - Bench state changes
- `ROSTER_UPDATE` - All 8 players info
- `GAME_START` / `GAME_END`

---

## Development Workflows

### Starting the Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start the main application (WebSocket + log watcher)
python -m app.main

# Or start just the API server
python -m app.api.server
```

### Starting the Frontend
```bash
cd app/frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

### Starting the Overlay (TypeScript)
```bash
cd overlay
npm install
npm run dev
# Opens at http://localhost:5174
```

### Running ML Models
```python
from src.models import FeatureEngineer, PlacementModel, TFTRecommender

# Load and prepare data
model = PlacementModel('.')
X, y, feature_names = model.prepare_data()

# Train model
model.train(X, y, model_type='gradient_boosting')

# Get recommendations
recommender = TFTRecommender('.')
recs = recommender.recommend_for_board(current_units, stage=3)
```

---

## Key Conventions

### Data Parsing
The `traits_active` and `final_board_units` columns need parsing:
```python
# Traits format: "Brawler:1 | Void:3"
traits = line.split(' | ')
for t in traits:
    name, count = t.split(':')

# Units format: "KogMaw_2*(Item1,Item2)"
# Use regex: (\w+)_(\d)\*\(([^)]*)\)
```

### Cell ID to Grid Position
```python
# Cell IDs: 1-28 (4 rows x 7 cols)
cell_num = int(cell_id.split("_")[1])  # "cell_8" -> 8
row = (cell_num - 1) // 7               # 8 -> row 1
col = (cell_num - 1) % 7                # 8 -> col 0
```

### Champion Names
- API names: `TFT16_Ekko`, `TFT16_Lissandra`
- Display names: Strip `TFT16_` prefix
- All Set 16 champions are mapped in `overlay/utils/transformBoardData.ts`

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Personal performance stats |
| `/api/comps/{stage}` | GET | Best comps for stage |
| `/api/augments` | GET | Augment recommendations |
| `/api/recommend` | POST | Board recommendations |
| `/api/analyze` | POST | Detailed board analysis |
| `/api/priority-units` | GET | Units to look for |
| `/api/items` | GET | Item build/avoid lists |
| `/api/lobby` | POST | Update lobby tracker |

---

## Current Progress (52% Complete)

### Completed
- Core infrastructure (log watcher, parser, state management)
- Data & ML models (feature engineering, placement prediction)
- React frontend (all 8 main components)
- Live data integration (parser events, state serialization)

### In Progress
- Connecting WebSocket to UI
- End-to-end testing with live game

### Not Started
- Positioning recommendations
- Item-to-unit optimal assignment
- Multi-user support
- Riot API integration
- Electron overlay

See `DEVELOPMENT_CHECKLIST.md` for detailed task tracking.

---

## Important Files to Understand

| File | Purpose |
|------|---------|
| `app/main.py` | Application entry point, orchestrates all components |
| `app/watcher/parser.py` | Log event extraction (11 regex patterns) |
| `app/state/state_manager.py` | Event processing and state updates |
| `app/api/server.py` | FastAPI REST endpoints |
| `app/frontend/src/App.jsx` | Main React UI component |
| `src/models/recommender.py` | Recommendation engine |
| `src/models/placement_model.py` | ML placement prediction |
| `docs/LIVE_DATA_PROGRESS.md` | Live data integration status |

---

## Data Files Reference

### Personal Data
| File | Records | Purpose |
|------|---------|---------|
| `data/personal/tft_since_16_2_enhanced.csv` | 163 | Match history (PRIMARY) |
| `data/personal/tft_matches_since_set16.csv` | - | Extended match data |
| `data/personal/carry_performance_corrected.csv` | 22 | Carry statistics |
| `data/personal/trait_performance_corrected.csv` | 54 | Trait statistics |
| `data/personal/item_performance_corrected.csv` | 47 | Item statistics |

### Game Data (Set 16)
| File | Records | Format |
|------|---------|--------|
| `data/game_data/champions.jsonl` | 101 | JSONL |
| `data/game_data/traits.jsonl` | 53 | JSONL |
| `data/game_data/items.jsonl` | 444 | JSONL |
| `data/game_data/augments.jsonl` | 208 | JSONL |

### API Data (Set 16.3)
| File | Description |
|------|-------------|
| `data/api/tft_16.3/comp_builds.json` | Composition build data |
| `data/api/tft_16.3/comps_data.json` | Composition metadata |
| `data/api/tft_16.3/unit_items_processed.json` | Item recommendations per unit |

---

## Live Data Extraction Methods

### 1. Log Parsing (Current - Events Only)
- Watches MetaTFT log files in `%LOCALAPPDATA%\Overwolf\Log\Apps\MetaTFT`
- Captures: stage, health, augments, scouting events
- Limitation: Board data appears as `[object Object]` in logs

### 2. Redux Bridge (Recommended - Full Board Data)
- Injects `app/redux_bridge/inject.js` into MetaTFT window
- Accesses Redux store at `state.game.board.board_pieces`
- Provides: Your board, bench, ALL 8 players' boards
- Requires: DevTools enabled in Overwolf

### 3. Post-Game API (Historical Analysis)
- Fetches from `metatft-matches-2.ams3.digitaloceanspaces.com/{UUID}.json`
- Contains: Round-by-round snapshots, all 8 boards, damage breakdown
- Limitation: Only available after game ends

---

## Common Tasks

### Add a New Event Type
1. Add enum value in `app/watcher/parser.py` → `EventType`
2. Add regex pattern in `LogParser.PATTERNS`
3. Add parse handler in `LogParser.parse_line()`
4. Add handler in `app/state/state_manager.py` → `process_event()`
5. Update `GameState.to_dict()` if serialization needed

### Add a New API Endpoint
1. Add Pydantic model if needed in `app/api/server.py`
2. Add route function with `@app.get()` or `@app.post()`
3. Add client function in `app/frontend/src/api.js`
4. Use in React components

### Add a New React Component
1. Create file in `app/frontend/src/components/`
2. Import in `App.jsx`
3. Add to layout grid
4. Connect to API via `useEffect` if needed

---

## Testing Checklist

### Backend
```bash
# Start backend
python -m app.main

# Check WebSocket
wscat -c ws://127.0.0.1:8765/ws

# Check API
curl http://127.0.0.1:8000/api/stats
```

### Frontend
```bash
cd app/frontend && npm run dev
# Open http://localhost:5173
# Verify components render with demo data
```

### Live Data
1. Start backend: `python -m app.main`
2. Start overlay: `cd overlay && npm run dev`
3. Enable Overwolf DevTools
4. Inject `app/redux_bridge/inject.js` into MetaTFT console
5. Start TFT game with MetaTFT running
6. Verify units appear on board

---

## Notes for AI Assistants

1. **Playstyle Context:** User excels with late-game AP/utility carries (Fiddlesticks, Ornn, Ryze). Recommendations should favor this playstyle.

2. **Small Dataset:** Only 163 games - prioritize interpretable models over complex ones. Be careful of overfitting.

3. **Windows-First:** This is a Windows desktop application. Paths use Windows conventions.

4. **MetaTFT Dependency:** Live data requires MetaTFT (Overwolf app) to be running.

5. **Two Frontends:** There's both a React frontend (`app/frontend/`) and a TypeScript overlay (`overlay/`). The React frontend is more complete.

6. **Data Parsing:** The `traits_active` and `final_board_units` columns contain concatenated strings. See `src/tft_diagnostic.py` for parsing utilities.

7. **Name Mappings:** 400+ mappings needed between Riot API internal names and display names. Check existing mappings before adding new ones.

---

## Related Documentation

- `README.md` - Project overview and quick start
- `DEVELOPMENT_CHECKLIST.md` - Detailed task tracking
- `CLAUDE_CODE_INSTRUCTIONS.md` - Original AI instructions
- `docs/LIVE_DATA_PROGRESS.md` - Live data integration status
- `docs/DATA_SCHEMAS.md` - Data schema definitions
- `docs/PROTOTYPE_PLAN.md` - Implementation plan

---

*Last updated: 2026-01-30*
