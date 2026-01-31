# TFT Coach Development Checklist

> Last updated: 2026-01-31

---

## Phase 1: Core Infrastructure (COMPLETE)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Python project structure | ✅ Done | app/, src/, data/, archive/ |
| 1.2 | Log file watcher (watchdog) | ✅ Done | app/watcher/log_watcher.py |
| 1.3 | Event parser for key events | ✅ Done | 11+ regex patterns in parser.py |
| 1.4 | Game state data model | ✅ Done | app/state/game_state.py |
| 1.5 | State reconstruction from events | ✅ Done | app/state/state_manager.py |
| 1.6 | WebSocket server | ✅ Done | app/server/websocket.py |
| 1.7 | Fix WebSocket live updates | ✅ Done | Thread-safe broadcasting |
| 1.8 | FastAPI REST endpoints | ✅ Done | 8+ endpoints in api/server.py |

---

## Phase 2: Data & ML Models (MOSTLY COMPLETE)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Load personal match history | ✅ Done | 163 games analyzed |
| 2.2 | Parse traits into features | ✅ Done | feature_engineering.py |
| 2.3 | Parse units into features | ✅ Done | star levels, items, costs |
| 2.4 | Identify carry (most items) | ✅ Done | carry_performance_corrected.csv |
| 2.5 | Feature matrix for sklearn | ✅ Done | Clean pipeline |
| 2.6 | Placement prediction model | ✅ Done | RandomForest, GradientBoosting, Logistic |
| 2.7 | Model validation (>60% accuracy) | ✅ Done | Cross-validation implemented |
| 2.8 | TFT Recommender engine | ✅ Done | Stage-aware recommendations |
| 2.9 | Augment tier list integration | ✅ Done | metatft_augments.csv loaded |
| 2.10 | Import more match data | ❌ Todo | Still at 163 games - need more |
| 2.11 | Improve win % prediction accuracy | ⚠️ Partial | Models work, need tuning with more data |

---

## Phase 3: React Frontend (COMPLETE)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | React + Vite + Tailwind setup | ✅ Done | app/frontend/ (TypeScript) |
| 3.2 | Header component | ✅ Done | Live status, game count |
| 3.3 | HexBoard component | ✅ Done | 7x4 hex grid |
| 3.4 | HexUnit component | ✅ Done | Portrait, items, stars |
| 3.5 | TraitsPanel component | ✅ Done | Active traits with tiers |
| 3.6 | LobbyTracker component | ✅ Done | Opponent comp tracking |
| 3.7 | ItemSuggestions component | ✅ Done | BUILD/AVOID columns |
| 3.8 | ModelSuggestions component | ✅ Done | Top 4 recommended comps |
| 3.9 | PriorityUnits component | ✅ Done | Units to look for |
| 3.10 | Figma design integration | ✅ Done | TFTFlows styling |
| 3.11 | Connect to live WebSocket data | ✅ Done | useGameState hook with auto-reconnect |
| 3.12 | Meta comps panel | ✅ Done | MetaCompCard with tiers |
| 3.13 | Coaching panel | ✅ Done | Stage-specific coaching tips |
| 3.14 | Item category tabs | ✅ Done | Craftable, artifact, radiant panels |

---

## Phase 4: Live Game Integration (MOSTLY COMPLETE)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Parse board state from logs | ✅ Done | Redux bridge extracts live data |
| 4.2 | Health tracking live display | ✅ Done | Parser + UI connected |
| 4.3 | Opponent board tracking display | ⚠️ Partial | DualBoard component exists |
| 4.4 | Real-time board sync | ✅ Done | WebSocket updates working |
| 4.5 | Item component recognition | ⚠️ Partial | Basic item display, crafting suggestions todo |

---

## Phase 5: Advanced Features (PARTIAL)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 5.1 | Positioning recommendations | ❌ Todo | No logic exists |
| 5.2 | Who to itemize (unit prioritization) | ⚠️ Partial | PriorityUnits exists, needs item mapping |
| 5.3 | Item-to-unit optimal assignment | ❌ Todo | Which items go on which carry |
| 5.4 | Pivot recommendations | ❌ Todo | When to switch comps |
| 5.5 | Stage-specific advice | ✅ Done | CoachingPanel with stage tips |
| 5.6 | Econ tracking & suggestions | ❌ Todo | Gold/XP optimization |

---

## Phase 6: Automation & Scaling (NOT STARTED)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 6.1 | Auto-import MetaTFT data (GitHub Actions) | ❌ Todo | Every 30 min scheduled job |
| 6.2 | Database persistence (SQLite) | ❌ Todo | Config ready, not implemented |
| 6.3 | Multi-user support (friends) | ❌ Todo | Currently single-user |
| 6.4 | User profiles/preferences | ❌ Todo | Different playstyles |
| 6.5 | Riot API integration | ❌ Todo | For real-time board state |

---

## Phase 7: Polish & Publishing (NOT STARTED)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 7.1 | Scrub GitHub for publishing | ❌ Todo | Remove sensitive data |
| 7.2 | Add .env for secrets | ❌ Todo | API keys, paths |
| 7.3 | Write user documentation | ⚠️ Partial | README exists, needs setup guide |
| 7.4 | Add unit tests | ❌ Todo | No tests exist |
| 7.5 | Create release package | ❌ Todo | Installer/executable |
| 7.6 | Electron overlay app | ❌ Todo | In-game overlay (currently browser) |

---

## Quick Reference: What's Next?

### High Priority (Immediate Value)
1. **Add opponent board display** - DualBoard exists, needs wiring
2. **Positioning recommendations** - New feature
3. **Item-to-unit assignments** - "Put Blue Buff on Ryze"
4. **Import more match data** - 163 games is small sample

### Medium Priority (Better Experience)
5. **Auto-import MetaTFT data** - Stay current with meta
6. **Improve prediction accuracy** - More data + tuning
7. **Pivot recommendations** - When to switch comps
8. **Econ tracking** - Gold/XP optimization

### Lower Priority (Future)
9. **Multi-user support** - Optimize for friends
10. **Scrub for publishing** - Clean up repo
11. **Riot API integration** - Real-time board
12. **Electron overlay** - True in-game overlay

---

## Summary Stats

| Category | Done | Partial | Todo | Total |
|----------|------|---------|------|-------|
| Core Infrastructure | 8 | 0 | 0 | 8 |
| Data & ML Models | 9 | 1 | 1 | 11 |
| React Frontend | 14 | 0 | 0 | 14 |
| Live Game Integration | 3 | 2 | 0 | 5 |
| Advanced Features | 1 | 2 | 3 | 6 |
| Automation & Scaling | 0 | 0 | 5 | 5 |
| Polish & Publishing | 0 | 1 | 5 | 6 |
| **TOTAL** | **35** | **6** | **14** | **55** |

**Overall Progress: ~64% complete (35 done + 6 partial of 55 tasks)**

---

## Files Reference

### Key Implementation Files
- `app/main.py` - Entry point
- `app/watcher/parser.py` - Log parsing (11+ event types)
- `app/state/game_state.py` - Game state model
- `app/api/server.py` - REST API endpoints
- `app/frontend/src/App.tsx` - Main React app (TypeScript)
- `app/frontend/hooks/useGameState.ts` - WebSocket hook
- `app/frontend/hooks/useMetaComps.ts` - Meta comps hook
- `src/models/placement_model.py` - ML prediction
- `src/models/recommender.py` - Recommendations

### Key Data Files
- `data/personal/tft_since_16_2_enhanced.csv` - 163 matches
- `data/personal/carry_performance_corrected.csv` - Carry stats
- `data/personal/trait_performance_corrected.csv` - Trait stats
- `data/personal/item_performance_corrected.csv` - Item stats
- `data/game_data/*.jsonl` - Set 16 reference data
