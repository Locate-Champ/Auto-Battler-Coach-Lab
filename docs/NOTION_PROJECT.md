# TFT Coach - AI-Powered Coaching Companion

> **Personal Project Portfolio** | Machine Learning + Real-Time Gaming Analytics
>
> *Built with Python, React, TypeScript, and Scikit-learn*

---

## Project Overview

| **Status** | **Active Development** |
|------------|------------------------|
| **Started** | January 22, 2026 |
| **Completion** | ~64% |
| **Tech Stack** | Python, React 18, TypeScript, FastAPI, WebSocket |
| **Dataset** | 163 personal TFT matches |

**TFT Coach** is an AI-powered personal coaching companion for Teamfight Tactics that provides:

- **ML-Powered Predictions** - Placement predictions based on personal match history
- **Real-Time Integration** - Live board state via MetaTFT/Overwolf
- **Stage-Aware Coaching** - Recommendations tailored to game phase
- **Meta Analysis** - Current meta compositions with tier ratings

### The Problem

TFT players struggle to improve because they lack personalized insights. Generic tier lists don't account for individual playstyles or tendencies.

### The Solution

TFT Coach analyzes YOUR games to identify YOUR strengths. It discovered I perform significantly better with late-game AP carries (70-100% top 4) compared to AD carries (0% top 4) - a pattern I never consciously noticed.

---

## Development Timeline

```
 JANUARY 2026 - 10 DAY SPRINT
 ════════════════════════════════════════════════════════════════════════

 Week 1: Foundation                      Week 2: Features & Polish
 ─────────────────────────────          ───────────────────────────────

     22   23   24   25   26   27   28   29   30   31
     ┃    ┃    ┃         ┃    ┃    ┃    ┃    ┃    ┃
     ▼    ▼    ▼         ▼    ▼    ▼    ▼    ▼    ▼
     ┌────┬────┬─────────┬────┬────┬────┬────┬────┐
     │████│████│░░░░░░░░░│████│████│████│████│████│
     │ P1 │ P2 │         │ P3 │ P4 │ P5 │ P6 │ P7 │
     └────┴────┴─────────┴────┴────┴────┴────┴────┘
       ▲    ▲              ▲    ▲    ▲    ▲    ▲
       │    │              │    │    │    │    │
       │    │              │    │    │    │    └── UI Polish
       │    │              │    │    │    └─────── Major Feature Release
       │    │              │    │    └──────────── Live Data Discovery
       │    │              │    └───────────────── Backend Complete
       │    │              └────────────────────── Data Pipeline
       │    └───────────────────────────────────── ML Models + First UI
       └────────────────────────────────────────── Project Init

 ────────────────────────────────────────────────────────────────────────
 LEGEND:  ████ = Active Development Day   ░░░░ = Planning/Research
```

### Milestone Breakdown

| Phase | Date | Milestone | Deliverables |
|-------|------|-----------|--------------|
| **P1** | Jan 22 | Project Initialization | Repository setup, knowledge base |
| **P2** | Jan 23-24 | ML Foundation | Placement prediction model, feature engineering, first React UI |
| **P3** | Jan 27 | Data Pipeline | 163-game dataset, log parser (11 event types), API endpoints |
| **P4** | Jan 28 | Backend Complete | WebSocket server, state manager, FastAPI REST API |
| **P5** | Jan 29 | Live Data Research | Redux Bridge discovery, board visualization, dual-board display |
| **P6** | Jan 30 | **Major Release** | Meta comps integration, UI consolidation, 15+ comps display |
| **P7** | Jan 31 | Polish | Trait icons, documentation, final cleanup |

---

## Progress Dashboard

```
 OVERALL COMPLETION
 ══════════════════════════════════════════════════════════════

 ████████████████████████████████████████░░░░░░░░░░░░░░░░░░░░░  64%

 ──────────────────────────────────────────────────────────────

 BY CATEGORY                                          PROGRESS
 ──────────────────────────────────────────────────────────────

 Core Infrastructure    ████████████████████████████████████████  100%  (8/8)
 React Frontend         ████████████████████████████████████████  100%  (14/14)
 Data & ML Models       █████████████████████████████████░░░░░░░   82%  (9/11)
 Live Integration       ████████████████████████░░░░░░░░░░░░░░░░   60%  (3/5)
 Advanced Features      ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   17%  (1/6)
```

### Completed Features

**Core Infrastructure** (8/8)
- [x] Python project structure and configuration
- [x] Log file watcher with watchdog
- [x] Event parser (11+ event types)
- [x] Game state data model
- [x] State reconstruction from events
- [x] WebSocket server with broadcasting
- [x] FastAPI REST endpoints
- [x] Windows/Unix compatibility

**React Frontend** (14/14)
- [x] React 18 + TypeScript + Vite + Tailwind CSS 4
- [x] HexBoard component (7x4 hex grid)
- [x] HexUnit with portraits, items, star levels
- [x] DualBoard for opponent tracking
- [x] Meta Comps panel with tier ratings
- [x] Coaching Panel with stage-specific tips
- [x] Pool Tracker for unit availability
- [x] Item category panels (6 types)
- [x] Trait icons with breakpoint styling
- [x] WebSocket connection with auto-reconnect
- [x] Expandable item builds display
- [x] Priority units display
- [x] Lobby tracker component
- [x] Figma design integration

**Data & ML Models** (9/11)
- [x] Personal match history loading
- [x] Feature engineering for traits/units
- [x] Carry identification with item analysis
- [x] Placement prediction models
- [x] Cross-validation (>60% accuracy)
- [x] Stage-aware recommender engine
- [x] Augment tier integration
- [x] Meta data scraper (tactics.tools)
- [x] 60+ meta compositions tracked
- [ ] Win prediction accuracy tuning
- [ ] Import more match data

**Live Game Integration** (3/5)
- [x] Redux Bridge for live data extraction
- [x] Real-time WebSocket sync
- [x] Health tracking display
- [ ] Full opponent board wiring
- [ ] Item component recognition

### Roadmap - Next Features

| Priority | Feature | Status | Complexity |
|----------|---------|--------|------------|
| 1 | Opponent Board Full Integration | In Progress | Medium |
| 2 | Positioning Recommendations | Not Started | High |
| 3 | Item-to-Unit Optimal Assignment | Not Started | Medium |
| 4 | Pivot Recommendations | Not Started | High |
| 5 | Econ Tracking & Optimization | Not Started | Medium |
| 6 | Database Persistence (SQLite) | Not Started | Low |

---

## Technology Architecture

```
                    ┌─────────────────────────────────────────────────────┐
                    │                   DATA SOURCES                       │
                    ├───────────────────────────────────────────────────────┤
                    │  MetaTFT Logs       Redux Store       Post-Game API  │
                    │  (Overwolf)         (inject.js)       (DigitalOcean) │
                    └────────┬───────────────┬───────────────────┬─────────┘
                             │               │                   │
                             ▼               ▼                   │
                    ┌────────────────────────────────────────────┐
                    │         Log Watcher + Parser               │
                    │         app/watcher/*.py                   │
                    └──────────────────┬─────────────────────────┘
                                       │
                                       ▼
                    ┌────────────────────────────────────────────┐
                    │            State Manager                   │
                    │         app/state/*.py                     │
                    └──────────────────┬─────────────────────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      ▼                                 ▼
              ┌───────────────┐                ┌───────────────┐
              │  WebSocket    │                │   REST API    │
              │  :8765/ws     │                │   :8000       │
              └───────┬───────┘                └───────┬───────┘
                      │                                │
                      └────────────────┬───────────────┘
                                       ▼
                    ┌─────────────────────────────────────────┐
                    │       TypeScript React Frontend         │
                    │         app/frontend/ (port 5173)       │
                    │     Vite proxy forwards /api and /ws    │
                    └─────────────────────────────────────────┘
```

### Tech Stack Details

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React 18, TypeScript | Modern reactive UI |
| **Styling** | Tailwind CSS 4 | Utility-first CSS |
| **Build** | Vite 7 | Fast dev server with HMR |
| **API** | FastAPI | Async REST endpoints |
| **Realtime** | WebSocket | Live game state updates |
| **Monitoring** | Watchdog | File system events |
| **ML** | Scikit-learn | Placement predictions |
| **Data** | Pandas, NumPy | Data processing |

### Port Configuration

| Service | Port | Protocol |
|---------|------|----------|
| Frontend UI | 5173 | HTTP |
| REST API | 8000 | HTTP |
| WebSocket | 8765 | WS |

---

## Key Insights from Data Analysis

### Personal Performance Analysis

Based on analysis of 163 personal TFT matches:

```
 TOP 4 RATE BY CARRY TYPE
 ══════════════════════════════════════════════════════════════

 AP/Utility Carries
 Fiddlesticks   ████████████████████████████████████████ 100%
 Ornn           ████████████████████████████████████     90%
 Ryze           ██████████████████████████████           75%
 Lissandra      ████████████████████████████             70%

 AD Carries
 Jinx           ████████                                 20%
 Draven         ████                                     10%
 Samira         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0%

 ──────────────────────────────────────────────────────────────
 Overall Top 4 Rate: 52%
```

### Key Discovery

> **The user performs 70-100% top 4 with late-game AP/utility carries vs 0-20% with AD carries** - a pattern that was not consciously recognized before this analysis.

This insight fundamentally shapes how TFT Coach provides recommendations, always favoring compositions that align with the user's demonstrated strengths.

---

## Project Metrics

### Codebase Statistics

| Metric | Value |
|--------|-------|
| Total Commits | 68+ |
| Pull Requests Merged | 25+ |
| Active Dev Days | 10 |
| React Components | 21 |
| Python Modules | 10+ |
| API Endpoints | 8 |
| Event Types Parsed | 11 |
| Meta Comps Tracked | 60+ |

### Development Velocity

```
 COMMITS PER DEVELOPMENT PHASE
 ══════════════════════════════════════════════════════════════

 P1 (Init)           ██████                                     6
 P2 (ML/UI)          ██████████████                            14
 P3 (Data)           ████████████                              12
 P4 (Backend)        ████████                                   8
 P5 (Live Data)      ████████████████                          16
 P6 (Features)       ██████████████████                        18
 P7 (Polish)         ████████                                   8

 ──────────────────────────────────────────────────────────────
 Average: ~8 commits/day during active development
```

---

## Screenshots & Visuals

*Add screenshots here after importing to Notion*

| View | Description |
|------|-------------|
| Main Dashboard | HexBoard with live game state |
| Meta Comps Panel | Tier-rated compositions with unit portraits |
| Coaching Panel | Stage-specific advice sections |
| Dual Board | Player + opponent board comparison |
| Item Panels | Craftable, Artifact, Radiant, Emblem, Support categories |

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/forrestmiller34/tft-coach-234.git

# Install dependencies
pip install -r requirements.txt
cd app/frontend && npm install

# Start everything (single command)
npm start

# Open in browser
open http://localhost:5173
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| `CLAUDE.md` | AI assistant guide (comprehensive) |
| `docs/LIVE_DATA_PROGRESS.md` | Live integration status |
| `docs/DATA_SCHEMAS.md` | Data structure definitions |
| `docs/PROTOTYPE_PLAN.md` | Implementation roadmap |
| `DEVELOPMENT_CHECKLIST.md` | Task tracking (55 tasks) |

---

## Repository Structure

```
tft-coach-234/
├── app/                    # Main application
│   ├── main.py            # Entry point
│   ├── api/               # FastAPI server
│   ├── frontend/          # React TypeScript UI
│   │   ├── src/           # Source code
│   │   ├── hooks/         # React hooks
│   │   └── images/        # 400+ assets
│   ├── server/            # WebSocket server
│   ├── state/             # Game state management
│   └── watcher/           # Log monitoring
├── src/                   # ML models
│   └── models/            # Prediction & recommendation
├── data/                  # Datasets
│   ├── personal/          # Match history
│   ├── game_data/         # Set 16 reference
│   └── meta/              # Current meta
├── scripts/               # Utility scripts
├── docs/                  # Documentation
└── archive/               # Old implementations
```

---

## Future Vision

### Phase 2 Goals (February 2026)
- [ ] Full opponent tracking with composition analysis
- [ ] Positioning optimizer with heatmap visualization
- [ ] Item assignment recommendations ("Put Blue Buff on Ryze")
- [ ] Pivot detection and alternative composition suggestions

### Phase 3 Goals (March 2026)
- [ ] Electron app for true in-game overlay
- [ ] Database persistence with SQLite
- [ ] Multi-user support with profiles
- [ ] Riot API integration for automatic match import

### Long-term Vision
- [ ] Public release with anonymized model
- [ ] Community comp sharing
- [ ] Coaching marketplace integration
- [ ] Mobile companion app

---

## Contact & Links

| Resource | Link |
|----------|------|
| **Repository** | [github.com/forrestmiller34/tft-coach-234](https://github.com/forrestmiller34/tft-coach-234) |
| **Documentation** | See `docs/` folder |
| **Issues** | GitHub Issues |

---

*Last Updated: January 31, 2026*

*Built with passion for TFT and data-driven improvement*
