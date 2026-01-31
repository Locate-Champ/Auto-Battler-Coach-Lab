# TFT Coach

A personal coaching companion for Teamfight Tactics (TFT) that provides ML-powered placement predictions and real-time recommendations.

## Features

- **ML Placement Prediction** - Predicts top 4 vs bottom 4 based on board composition
- **Real-time Board Integration** - Live board state via MetaTFT/Overwolf logs
- **Stage-aware Recommendations** - Coaching tips tailored to game phase
- **Meta Comps Display** - Current meta compositions with tier ratings
- **Personal Analytics** - Insights from 163 matches of personal data

## Quick Start

```bash
# Single command to run everything
npm start

# Or use the shell script
./start.sh
```

This starts:
- **Frontend UI** at http://localhost:5173
- **API Server** on port 8000
- **WebSocket Server** on port 8765

## Installation

### Prerequisites
- Python 3.10+
- Node.js 18+

### Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd app/frontend && npm install
```

## Project Structure

```
tft-coach-234/
├── app/
│   ├── main.py              # WebSocket server + log watcher
│   ├── api/server.py        # FastAPI REST endpoints
│   ├── frontend/            # TypeScript React UI
│   │   ├── src/App.tsx      # Main React component
│   │   └── hooks/           # useGameState, useMetaComps, etc.
│   ├── server/websocket.py  # Real-time updates
│   ├── state/               # Game state management
│   └── watcher/             # Log file monitoring
├── src/models/              # ML prediction & recommendations
├── data/
│   ├── personal/            # Match history (163 games)
│   └── game_data/           # Set 16 reference data
└── scripts/                 # Utility scripts
```

## Key Insights

Based on 163 matches analyzed:

| Metric | Value |
|--------|-------|
| Overall Top 4 Rate | 52% |
| AP Carries (5-cost) | 70-100% top 4 |
| AD Carries | 0% top 4 |
| Best Carries | Fiddlesticks, Ornn, Ryze |

**Takeaway:** Late-game AP/utility carries significantly outperform AD carries for this playstyle.

## Technology Stack

### Backend
- **FastAPI** - REST API
- **WebSockets** - Real-time updates
- **Watchdog** - Log file monitoring
- **Scikit-learn** - ML models

### Frontend
- **React 18** with TypeScript
- **Vite 7** with dev proxy
- **Tailwind CSS 4**

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Personal performance stats |
| `/api/meta-comps` | GET | Current meta compositions |
| `/api/early-comps` | GET | Early game compositions |
| `/api/recommend` | POST | Board recommendations |
| `/api/augments` | GET | Augment tier list |
| `/api/items` | GET | Item build/avoid lists |

## Development

```bash
# Frontend only (with mock data)
cd app/frontend && npm run dev

# Backend only
python -m app.main

# API server only
python -m app.api.server
```

## Requirements

Live data integration requires:
- **MetaTFT** (Overwolf app) running during TFT games
- Windows OS (for Overwolf log access)

## Documentation

- `CLAUDE.md` - AI assistant guide
- `DEVELOPMENT_CHECKLIST.md` - Task tracking
- `docs/` - Additional documentation

---

*TFT Set 16.3 | Last updated: 2026-01-31*
