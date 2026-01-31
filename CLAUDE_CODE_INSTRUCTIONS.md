# TFT Coach - Instructions for Claude Code

## What This Project Is
A TFT coaching app that provides ML-powered placement predictions and real-time recommendations based on board composition. Built on 163 matches of personal data showing the user performs better with late-game AP carries (70% top 4) than AD carries (0% top 4).

## Quick Start

```bash
# Single command to run everything
npm start

# Or use the shell script
./start.sh

# Or manually
cd app/frontend && npm run dev:full
```

This starts:
- **API Server** on port 8000
- **WebSocket Server** on port 8765
- **Frontend UI** on port 5173

Open http://localhost:5173 in your browser.

## Project Structure

```
tft-coach-234/
├── app/                          # Main application
│   ├── main.py                   # Entry point - WebSocket + log watcher
│   ├── config.py                 # Configuration
│   ├── api/server.py             # FastAPI REST endpoints
│   ├── frontend/                 # TypeScript React UI (PRIMARY)
│   │   ├── src/App.tsx           # Main React component
│   │   ├── hooks/                # React hooks (useGameState, useMetaComps, etc.)
│   │   └── utils/                # Utilities (transformBoardData.ts)
│   ├── server/websocket.py       # WebSocket server
│   ├── state/                    # Game state management
│   └── watcher/                  # Log file monitoring
├── src/models/                   # ML models (placement, recommender)
├── data/                         # Data files
│   ├── personal/                 # Personal match history (163 games)
│   └── game_data/                # Set 16 reference data (JSONL)
├── scripts/                      # Utility scripts
└── archive/old_frontend/         # Archived JavaScript frontend
```

## The Data

**Match history:** `data/personal/tft_since_16_2_enhanced.csv` (163 games)
- Target variable: `placement` (1-8)
- Key features: `traits_active`, `final_board_units`, `level`, `gold_left`, `last_round`

**Performance aggregates (in `data/personal/`):**
- `carry_performance_corrected.csv` - which carries I win with
- `trait_performance_corrected.csv` - which traits I win with
- `item_performance_corrected.csv` - which items I win with

**Game reference data:** `data/game_data/*.jsonl` - champion stats, traits, items, augments

## Data Parsing Notes

The `traits_active` and `final_board_units` columns need parsing:
- Traits: `"Brawler:1 | Void:3"` → split on `|`, then on `:`
- Units: `"KogMaw_2*(Item1,Item2)"` → regex: `(\w+)_(\d)\*\(([^)]*)\)`

Parsing code exists in `src/tft_diagnostic.py`.

## Technology Stack

### Backend (Python 3.10+)
- **FastAPI** - REST API (port 8000)
- **WebSockets** - Real-time updates (port 8765)
- **Watchdog** - Log file monitoring
- **Scikit-learn** - ML models

### Frontend (Node.js 18+)
- **React 18** with TypeScript
- **Vite 7** with dev proxy
- **Tailwind CSS 4**

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | WebSocket server + log watcher |
| `app/api/server.py` | REST API endpoints |
| `app/frontend/src/App.tsx` | Main React UI |
| `app/frontend/hooks/useGameState.ts` | WebSocket connection hook |
| `src/models/placement_model.py` | ML placement prediction |
| `src/models/recommender.py` | Stage-aware recommendations |

## Current Capabilities

- ✅ ML placement prediction model
- ✅ Stage-aware recommendation engine
- ✅ WebSocket real-time updates
- ✅ React UI with hex board, traits panel, item suggestions
- ✅ Meta comps integration
- ✅ Live board state from MetaTFT logs

## Success Criteria

- Model beats 60% accuracy on top 4 vs bottom 4
- Feature importance confirms AP > AD (validates the data)
- Can explain WHY certain comps work for me
- Live data processing in <1 second

## Important Notes

1. **Single UI**: Only one frontend at `app/frontend/` (TypeScript/React). Old JS frontend is archived.
2. **Playstyle**: User excels with late-game AP/utility carries (Fiddlesticks, Ornn, Ryze).
3. **Small Dataset**: 163 games - prioritize interpretable models.
4. **MetaTFT**: Live data requires MetaTFT (Overwolf app) running.
5. **Vite Proxy**: Frontend proxies `/api` to 8000 and `/ws` to 8765.

---

*Last updated: 2026-01-31*
