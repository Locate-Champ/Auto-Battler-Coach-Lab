# TFT Coach 234 - Complete Project Overview

> **Purpose:** This document provides everything an AI/LLM needs to understand and rebuild this project in Notion or any other project management tool.

---

## 1. Project Structure

```
tft-coach-234/
├── app/                          # Main Python application
│   ├── main.py                   # Entry point - TFTCoach class
│   ├── config.py                 # Configuration (paths, ports, etc.)
│   ├── run_app.py                # Alternative runner
│   ├── api/
│   │   └── server.py             # FastAPI REST API + endpoints
│   ├── frontend/                 # React + Vite + TailwindCSS UI
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── App.jsx           # Main React component
│   │   │   ├── api.js            # API client
│   │   │   └── components/       # UI components
│   │   │       ├── Header.jsx
│   │   │       ├── HexBoard.jsx      # Hex grid board display
│   │   │       ├── HexUnit.jsx
│   │   │       ├── TraitsPanel.jsx
│   │   │       ├── LobbyTracker.jsx
│   │   │       ├── ItemSuggestions.jsx
│   │   │       ├── ModelSuggestions.jsx
│   │   │       └── PriorityUnits.jsx
│   │   └── tailwind.config.js
│   ├── server/
│   │   └── websocket.py          # WebSocket server for real-time updates
│   ├── state/
│   │   ├── game_state.py         # GameState dataclass model
│   │   └── state_manager.py      # State update logic
│   └── watcher/
│       ├── log_watcher.py        # File system watcher (watchdog)
│       └── parser.py             # MetaTFT log parser with regex
│
├── src/                          # ML models and utilities
│   └── models/                   # Placement prediction, recommender
│
├── scripts/
│   ├── fetch_meta_data.py        # GitHub Actions data fetcher (placeholder)
│   ├── organize_api_data.py      # API data processor
│   └── kb/
│       └── build_manifest.py     # Knowledge base builder
│
├── data/                         # Organized data directory
│   ├── meta/                     # Meta statistics
│   │   ├── compositions.json     # Comp cluster data
│   │   ├── comp_stats.json       # Placement statistics
│   │   ├── comp_builds.json      # Build variations
│   │   ├── comp_options.json     # Augment/item options
│   │   ├── unit_items.json       # Best items per unit
│   │   └── percentiles.json      # Ranking data
│   ├── personal/                 # Personal game data
│   ├── api/
│   │   ├── raw/                  # Original API JSONs
│   │   └── processed/            # Parsed game data
│   └── game_data/
│
├── TFT 16.3 API Data/            # Source data files
│   ├── tft project files/        # CSV match data + JSONL game data
│   └── API Data/                 # Raw Meta TFT API JSONs
│
├── docs/                         # Documentation
│   ├── DATA_SCHEMAS.md           # Data format reference
│   ├── PROTOTYPE_PLAN.md         # Architecture + roadmap
│   ├── TFT_Coach_Figma_Spec.md   # UI design system
│   └── TFT_Coach_Component_Outline.js
│
├── metatft_logs/                 # Sample MetaTFT log files
├── overlay/                      # HTML overlay files
├── knowledge-base/               # KB manifests and sources
├── outputs/                      # Generated outputs
│
├── sync_metatft.py               # Auto-sync MetaTFT logs
├── watch_logs.py                 # Log watcher utility
├── tft-coach.jsx                 # Standalone React component
├── tft-coach-preview.html        # Interactive preview
│
├── requirements.txt              # Python dependencies
├── manifest.json                 # File manifest
├── metadata.json                 # Dataset metadata
├── .mcp.json                     # Figma MCP config
└── README.md                     # Project handoff docs
```

---

## 2. README.md (Full Contents)

### Project Objective
Build a TFT coaching companion that provides ML-powered placement predictions and actionable recommendations based on:
1. Historical match performance data (163 games analyzed)
2. Live board state integration via Riot API
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

## 3. Configuration Files

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

    @property
    def personal_notes_path(self) -> Path:
        return self.data_dir / "personal_notes.yaml"

    @property
    def rules_path(self) -> Path:
        return self.data_dir / "rules.yaml"

    @property
    def history_db_path(self) -> Path:
        return self.data_dir / "history.db"
```

### metadata.json
```json
{
  "source": "CommunityDragon cdragon/tft/en_us.json",
  "source_url": "https://raw.communitydragon.org/latest/cdragon/tft/en_us.json",
  "set_number": 16,
  "set_name": "Set16",
  "counts": {
    "champions_all": 116,
    "champions_shop": 101,
    "traits": 53,
    "items": 444,
    "augments": 208
  }
}
```

### manifest.json
```json
{
  "created_at_utc": "2026-01-21T20:13:54.605169Z",
  "files": [
    "README.txt", "ability_variables.jsonl", "augments.jsonl",
    "champion_traits.jsonl", "champions.jsonl", "item_components.jsonl",
    "items.jsonl", "metadata.json", "set16_all_records.jsonl",
    "set16_augments.jsonl", "set16_champions_all.jsonl",
    "set16_champions_shop.jsonl", "set16_items.jsonl",
    "set16_traits.jsonl", "trait_effects.jsonl", "traits.jsonl"
  ],
  "row_counts_from_csv": {
    "ability_variables": 609,
    "augments": 208,
    "champion_traits": 207,
    "champions": 101,
    "items": 444,
    "trait_effects": 113,
    "traits": 53
  }
}
```

### .mcp.json (Figma Integration)
```json
{
  "mcpServers": {
    "figma": {
      "type": "http",
      "url": "https://mcp.figma.com/mcp"
    }
  }
}
```

---

## 4. Data Schemas

### Match Data (tft_since_16_2_enhanced.csv) - 163 records
**Headers:**
```
match_id,game_datetime,game_length_sec,queue_id,game_version,placement,level,gold_left,last_round,time_eliminated,total_damage_to_players,players_eliminated,aug1,aug2,aug3,traits_active,final_board_units
```

**Sample Row:**
```
NA1_5470047531,1768959662960,2105.72,1100,Linux Version 16.1...,5,8,39,28,1708.66,71,0,,,,Brawler:1 | Void:3,"KogMaw_2*() | BelVeth_2*(TheDarkinBow,TitansResolve,RunaansHurricane) | ..."
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
Sett,5,3,100.0,0.0,2.67
```

### Augment Tierlist (metatft_augment_tierlist_16_3.csv)
```
name,tier,types,rarity
3 Threes,S,Econ,Gold
Band of Thieves II+,S,Items,Prismatic
Comeback Story,S,"Combat, Scaling",Prismatic
```

### Trait Performance (trait_performance_corrected.csv) - 54 traits
```python
{
    "trait": "Sorcerer",
    "games": 45,
    "top4_rate": 0.622,
    "win_rate": 0.133,
    "avg_placement": 4.12
}
```

### Item Performance (item_performance_corrected.csv) - 47 items
```python
{
    "item": "JeweledGauntlet",
    "games": 28,
    "top4_rate": 0.678,
    "avg_placement": 3.89
}
```

### Champion Data (champions.jsonl) - 101 champions
```python
{
    "apiName": "TFT16_Tristana",
    "name": "Tristana",
    "cost": 2,
    "role": "ADCaster",
    "traits_pipe": "Yordle|Gunslinger",
    "ability_name": "Buster Shot",
    "stat_armor": 20.0,
    "stat_attackSpeed": 0.75,
    "stat_damage": 55.0,
    "stat_hp": 550.0,
    "stat_mana": 50.0,
    "stat_range": 4.0
}
```

### Composition Data (compositions.json)
```json
{
  "cluster_id": 387,
  "tft_set": "TFTSet16",
  "compositions": {
    "387000": {
      "Cluster": 387000,
      "centroid": [0.0001, 0.0008, ...],
      // Unit vectors for comp identification
    }
  }
}
```

---

## 5. Main Scripts

### Entry Point: app/main.py
- `TFTCoach` class orchestrates:
  - `StateManager` - game state reconstruction
  - `LogWatcher` - MetaTFT log monitoring
  - `WebSocketServer` - real-time client updates
- CLI args: `--no-server`, `--port`
- Handles graceful shutdown on Ctrl+C

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
- `GET /api/comps/{stage}` - best comps for stage
- `GET /api/augments` - augment recommendations
- `POST /api/recommend` - board analysis + suggestions
- `GET /api/priority-units` - units to look for
- `GET /api/items` - build/avoid item suggestions

### Data Sync: sync_metatft.py
- Auto-discovers Overwolf/MetaTFT log directory
- Parses augment armory events
- Exports to CSV for analysis
- Watch mode: `--watch` flag for continuous sync

---

## 6. Frontend (React + Vite)

### package.json Dependencies
```json
{
  "dependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4.1.18",
    "@vitejs/plugin-react": "^5.1.1",
    "tailwindcss": "^4.1.18",
    "vite": "^7.2.4"
  }
}
```

### Main Components (App.jsx)
1. **Header** - Live/offline status
2. **TraitsPanel** - Active traits display
3. **LobbyTracker** - Comp contestation counter
4. **HexBoard** - Hex grid board visualization
5. **ItemSuggestions** - Build/avoid items
6. **ModelSuggestions** - ML-based recommendations
7. **PriorityUnits** - Units to prioritize

### Comp Archetypes Tracked
```javascript
const COMP_ARCHETYPES = [
  { id: 'harvester', name: 'Harvester/Fiddle', color: '#22c55e' },
  { id: 'soulbound', name: 'Soulbound', color: '#a855f7' },
  { id: 'blacksmith', name: 'Blacksmith', color: '#3b82f6' },
  { id: 'bruiser', name: 'Bruiser/Sett', color: '#f97316' },
  { id: 'void', name: 'Void', color: '#8b5cf6' },
  { id: 'honeymancy', name: 'Honeymancy', color: '#eab308' },
]
```

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
│   %LOCALAPPDATA%\Overwolf\Log\Apps\MetaTFT\                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ File watching (watchdog)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Log Watcher Service (Python)                    │
│  • Monitors log file changes                                    │
│  • Parses events into structured GameEvent                      │
│  • Updates StateManager                                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ GameState updates
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Coach Engine (Python)                         │
│  • PlacementModel - ML predictions                              │
│  • TFTRecommender - strategy suggestions                        │
│  • Personal stats from CSV data                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │ FastAPI + WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Overlay UI (React + Vite)                     │
│  • HexBoard - board visualization                               │
│  • TraitsPanel - active traits                                  │
│  • ModelSuggestions - ML recommendations                        │
│  • LobbyTracker - contestation tracking                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. Key Data Files Reference

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
| Meta | metatft_augment_tierlist_16_3.csv | - | Community tier rankings |
| Meta | compositions.json | - | Comp cluster data |

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
# "BelVeth_2*(TheDarkinBow,TitansResolve)" -> [("BelVeth", 2, ["TheDarkinBow", "TitansResolve"])]
```

---

## 11. GitHub Actions Workflows

Located in `.github/workflows/`:
- `deploy.yml` - Deployment automation
- `fetch-meta-data.yml` - Daily meta data refresh
- `lint.yml` - Code linting
- `test-coverage.yml` - Test coverage reports
- `auto-merge.yml` - PR auto-merge
- `secret-scan.yml` - Security scanning

---

## 12. Quick Start Commands

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the coach (with WebSocket server)
python -m app.main

# Run without server (CLI only)
python -m app.main --no-server

# Run API server separately
python -m app.api.server

# Sync MetaTFT logs
python sync_metatft.py

# Watch mode (continuous sync)
python sync_metatft.py --watch

# Frontend development
cd app/frontend
npm install
npm run dev
```

---

## 13. Model Building Objectives

### Phase 1: Placement Prediction
- **Target:** `placement` (1-8)
- **Features:** Trait counts, unit composition, game state, items, augments
- **Approach:** Random Forest / XGBoost for interpretability
- **Note:** Small dataset (163 games) - avoid overfitting

### Phase 2: Recommendation Engine
1. Optimal pivots when underperforming
2. Item prioritization based on board
3. Augment selection with personal performance

### Phase 3: Live Integration
- Riot API for real-time board state
- Contestation tracking
- Real-time placement projections

---

*Generated: 2026-01-28 | TFT Set 16.3*
