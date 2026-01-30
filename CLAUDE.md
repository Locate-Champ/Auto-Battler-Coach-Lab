# TFT Coach - AI Assistant Guide

> Comprehensive documentation for AI assistants working on this codebase.

---

## Quick Start

**Single command to run the entire project:**

```bash
# Option 1: Using npm (recommended)
npm start

# Option 2: Using the shell script
./start.sh

# Option 3: Manual start
cd app/frontend && npm run dev:full
```

This starts all services:
- **API Server** on port 8000
- **WebSocket Server** on port 8765
- **Frontend UI** on port 5173

Open http://localhost:5173 in your browser.

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
├── app/                          # Main application
│   ├── main.py                   # Entry point - WebSocket + log watcher
│   ├── config.py                 # Configuration (paths, ports, etc.)
│   ├── api/
│   │   └── server.py             # FastAPI REST endpoints
│   ├── frontend/                 # TypeScript React UI (PRIMARY)
│   │   ├── src/
│   │   │   ├── App.tsx           # Main React component
│   │   │   ├── main.tsx          # React entry point
│   │   │   └── index.css         # Tailwind styles
│   │   ├── hooks/                # React hooks
│   │   │   ├── useGameState.ts   # WebSocket connection with auto-reconnect
│   │   │   ├── useMetaComps.ts   # Meta comps fetching
│   │   │   ├── useEarlyComps.ts  # Early game comps
│   │   │   └── usePoolTracker.ts # Unit pool tracking
│   │   ├── utils/
│   │   │   └── transformBoardData.ts  # Champion name mappings
│   │   ├── images/               # 400+ champion/item images
│   │   │   ├── champion images/
│   │   │   └── [item images]/
│   │   ├── CoachingPanel.tsx     # Stage-specific coaching tips
│   │   ├── CompsPanel.tsx        # Meta comps display
│   │   ├── LiveBoard.tsx         # WebSocket-connected board
│   │   ├── DualBoard.tsx         # Player + opponent boards
│   │   ├── MetaCompCard.tsx      # Comp tier display
│   │   ├── ItemsBar.tsx          # Item category tabs
│   │   ├── [item panels].tsx     # Craftable, artifact, radiant, etc.
│   │   ├── package.json          # Dependencies (React 18, Vite 7)
│   │   ├── vite.config.ts        # Vite config with proxy
│   │   └── tsconfig.json         # TypeScript configuration
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
│   └── sync_metatft.py           # MetaTFT data sync
│
├── data/                         # All data files
│   ├── personal/                 # Personal match history
│   │   └── tft_since_16_2_enhanced.csv  # 163 matches (PRIMARY)
│   ├── game_data/                # Set 16 reference data (JSONL)
│   │   ├── champions.jsonl
│   │   ├── traits.jsonl
│   │   ├── items.jsonl
│   │   └── augments.jsonl
│   ├── meta/                     # Current meta data
│   └── api/                      # API response caches
│
├── docs/                         # Documentation
├── archive/                      # Archived code and old implementations
│   └── old_frontend/             # Previous React/JS frontend (backup)
│
├── start.sh                      # Single command launcher (Linux/Mac)
├── package.json                  # Root npm scripts
├── requirements.txt              # Python dependencies
└── CLAUDE.md                     # This file
```

---

## Technology Stack

### Backend (Python 3.10+)
- **FastAPI** - REST API server (port 8000)
- **WebSockets** - Real-time communication (port 8765)
- **Watchdog** - File system monitoring
- **Pandas/NumPy** - Data processing
- **Scikit-learn** - ML models

### Frontend (Node.js 18+)
- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite 7** - Build tool with dev proxy
- **Tailwind CSS 4** - Styling

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
│        TypeScript React Frontend         │
│         app/frontend/ (port 5173)        │
│    Vite proxy forwards /api and /ws     │
└─────────────────────────────────────────┘
```

### Ports Summary
| Service | Port | Protocol |
|---------|------|----------|
| Frontend UI | 5173 | HTTP |
| REST API | 8000 | HTTP |
| WebSocket | 8765 | WS |

---

## Development Workflows

### Start Everything (Recommended)
```bash
npm start
# Or: ./start.sh
# Opens at http://localhost:5173
```

### Start Individual Services
```bash
# Frontend only (no backend)
cd app/frontend && npm run dev

# Backend API only
python -m app.api.server

# WebSocket server only
python -m app.main
```

### Install Dependencies
```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd app/frontend && npm install
```

### Build for Production
```bash
npm run build
# Output in app/frontend/dist/
```

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | WebSocket server + log watcher entry point |
| `app/api/server.py` | FastAPI REST endpoints |
| `app/frontend/src/App.tsx` | Main React UI component |
| `app/frontend/hooks/useGameState.ts` | WebSocket connection hook |
| `app/frontend/hooks/useMetaComps.ts` | Meta comps data fetching |
| `app/frontend/CoachingPanel.tsx` | Stage-specific coaching tips |
| `app/frontend/MetaCompCard.tsx` | Meta comp display with tiers |
| `app/frontend/utils/transformBoardData.ts` | Champion name mappings |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Personal performance stats |
| `/api/meta-comps` | GET | MetaTFT meta compositions |
| `/api/early-comps` | GET | Early game compositions |
| `/api/comps/{stage}` | GET | Best comps for stage |
| `/api/augments` | GET | Augment recommendations |
| `/api/recommend` | POST | Board recommendations |
| `/api/analyze` | POST | Detailed board analysis |
| `/api/priority-units` | GET | Units to look for |
| `/api/items` | GET | Item build/avoid lists |
| `/api/lobby` | POST | Update lobby tracker |

---

## Frontend Hooks

### useGameState
WebSocket connection with auto-reconnect for live game data.
```typescript
const { state, isConnected, error, reconnect } = useGameState();
// state contains: board_units, bench_units, stage, player, etc.
```

### useMetaComps
Fetches meta compositions from the API.
```typescript
const { data, loading, error, refetch } = useMetaComps({ limit: 15 });
// data.comps contains tier, units, traits, stats
```

### usePoolTracker
Tracks unit pool state for all 8 players.
```typescript
const pool = usePoolTracker(gameState);
// pool.getRemaining('TFT16_Fiddlesticks') => 7
// pool.getAvailability('TFT16_Fiddlesticks') => 'high' | 'medium' | 'low'
```

---

## Key Conventions

### Champion Names
- API names: `TFT16_Ekko`, `TFT16_Lissandra`
- Display names: Strip `TFT16_` prefix
- Mappings in `app/frontend/utils/transformBoardData.ts`

### Data Parsing (CSV)
```python
# Traits format: "Brawler:1 | Void:3"
traits = line.split(' | ')
for t in traits:
    name, count = t.split(':')

# Units format: "KogMaw_2*(Item1,Item2)"
# Use regex: (\w+)_(\d)\*\(([^)]*)\)
```

### Adding New Components
1. Create `.tsx` file in `app/frontend/`
2. Import in `App.tsx`
3. Add to layout
4. Use hooks for data fetching

---

## Testing

### Quick Verification
```bash
# Start everything
npm start

# In another terminal, check API
curl http://127.0.0.1:8000/api/stats

# Check WebSocket (if wscat installed)
wscat -c ws://127.0.0.1:8765/ws
```

### Frontend Only
```bash
cd app/frontend && npm run dev
# Open http://localhost:5173
# Components work with demo/fallback data
```

---

## Notes for AI Assistants

1. **Single UI**: There is only ONE frontend at `app/frontend/`. It uses TypeScript and React 18. The old JavaScript frontend is archived at `archive/old_frontend/`.

2. **Playstyle Context**: User excels with late-game AP/utility carries (Fiddlesticks, Ornn, Ryze). Recommendations should favor this playstyle.

3. **Small Dataset**: Only 163 games - prioritize interpretable models. Be careful of overfitting.

4. **Vite Proxy**: The frontend uses Vite's proxy to forward `/api` to port 8000 and `/ws` to port 8765. Don't hardcode backend URLs in frontend code.

5. **Images**: 400+ champion/item images are in `app/frontend/images/`. Use these for visual displays.

6. **MetaTFT Dependency**: Live data requires MetaTFT (Overwolf app) to be running.

7. **Name Mappings**: Champion name mappings are in `app/frontend/utils/transformBoardData.ts`.

---

## Related Documentation

- `docs/LIVE_DATA_PROGRESS.md` - Live data integration status
- `docs/DATA_SCHEMAS.md` - Data schema definitions
- `docs/PROTOTYPE_PLAN.md` - Implementation plan
- `DEVELOPMENT_CHECKLIST.md` - Task tracking

---

*Last updated: 2026-01-30*
