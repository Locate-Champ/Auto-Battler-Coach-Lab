# AGENTS.md - AI Assistant Rules for TFT Coach

> Universal rules for any AI coding assistant (Claude Code, Codex, Copilot, Cursor, etc.) working on this codebase.
> This document is self-contained. Read it fully before making any changes.
> Last updated: 2026-02-12

---

## Completion Notification Rule

- Before sending any final response, run:
  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\notify-ntfy.ps1 -Title "Codex done" -Message "<one-line task summary>"
  ```
- If that command fails, mention the failure in the final response.

### ntfy Topic Configuration

Use the first available source:
1. `NTFY_TOPIC_URL` environment variable (full URL, e.g. `https://ntfy.sh/your-topic`)
2. `NTFY_TOPIC` environment variable (topic slug or full URL)
3. `.ntfy-topic` file in repo root (topic slug or full URL)

## Phase Completion Improvement Rule

- At the conclusion of any phase or implementation, every AI assistant must include a short **Next Improvements** section.
- That section must propose concrete opportunities to improve, innovate, or speed up the codebase.
- If no high-confidence opportunity is identified, explicitly state that and what data is needed to find one.

---

## Continuity Protocol (Autonomous Sessions)

> Applies to Codex, background agents, and any AI running without real-time user supervision.
> Interactive sessions (Claude Code, Copilot chat) may skip this protocol.

### Purpose

Long autonomous sessions lose context to compaction. This protocol ensures decisions, discoveries, and progress survive across turns and sessions by maintaining a structured continuity file.

### The Continuity File

Maintain a single file: `.agent/CONTINUITY.md`

- **Read `.agent/CONTINUITY.md` before acting** at the start of each autonomous turn.
- It is the canonical briefing. Do not rely on earlier chat/tool output unless reflected there.
- If the file does not exist, create it with the template below on first meaningful action.

### File Format

```markdown
# CONTINUITY - TFT Coach

## [PLANS]
<!-- Guide for the next contributor as much as checklist for you -->

## [DECISIONS]
<!-- All decisions made, with rationale -->

## [PROGRESS]
<!-- Course changes mid-implementation: why and implications -->

## [DISCOVERIES]
<!-- Optimizer behavior, performance tradeoffs, unexpected bugs, inverse semantics -->
<!-- Include short evidence snippets (test output is ideal) -->

## [OUTCOMES]
<!-- At completion: what was achieved, what remains, lessons learned -->
```

### Update Rules

Update `.agent/CONTINUITY.md` only when there is a **meaningful delta** in any section.

Every entry must include:
- An ISO timestamp (e.g., `2025-02-09T14:30Z`)
- A provenance tag: `[USER]`, `[CODE]`, `[TOOL]`, `[ASSUMPTION]`

Anti-drift rules:
- **Facts only.** No transcripts, no raw logs, no filler.
- If unknown, write `UNCONFIRMED` (never guess).
- If something changes, **supersede explicitly** (do not silently rewrite history).
- Keep the file bounded and high-signal. If sections bloat, compress older items into `[MILESTONE]` bullets.

### Definition of Done

A task is done when:

1. The requested change is implemented or the question is answered.
2. **Verification is provided** (all that apply):
   - `pytest` run (when test-covered code changed)
   - `python -m simulator.benchmark` (when combat engine changed) - determinism checks must pass
   - `python -m simulator.validate_output <dir>` (when simulator output format changed) - all 19 checks must pass
   - Frontend builds without errors (when frontend code changed)
   - Errors/warnings addressed, or explicitly listed as out-of-scope
3. Impact is explained (what changed, where, why).
4. Follow-ups are listed if anything was intentionally left out.
5. `.agent/CONTINUITY.md` is updated if the change materially affects goals, state, or decisions.
6. Completion notification sent (see Completion Notification Rule above).

### Relationship to MEMORY.md

- `.agent/CONTINUITY.md` tracks **session-level** context: current plans, in-flight decisions, active progress.
- `MEMORY.md` (in `.claude/projects/`) tracks **permanent** project knowledge: architecture, gotchas, lessons learned.
- When a discovery in CONTINUITY.md proves durable, promote it to MEMORY.md.
- Do not duplicate MEMORY.md content into CONTINUITY.md. Reference it instead.

---

## Project Overview

**TFT Coach** is a personal coaching app for Teamfight Tactics (TFT) Set 16 with three layers:

1. **Combat Simulator** (Python) - Deterministic, tick-based (30 FPS) full 8-player game simulator. 106 champions, 283 augments, 134 items, 53 traits. Benchmarked at ~2,717 games/hour/core.
2. **ML Prediction Pipeline** (Python) - XGBoost baseline + Transformer with cross-attention, trained on simulator output.
3. **Coaching Frontend** (TypeScript/React) - Real-time WebSocket UI with live board state from MetaTFT/Overwolf.

**Key user context:** The owner excels with late-game AP/utility carries (Fiddlesticks, Ornn, Ryze) at 70-100% top 4 rate, vs 0% with AD carries. Recommendations should favor this playstyle.

---

## DO's (Mandatory)

1. **Read before writing.** Always read existing code before proposing changes. Understand the patterns, imports, and conventions already in use.
2. **Use existing helpers.** The codebase has helper functions for common operations. Use `_star_val()`, `_get_var()`, `_resolve_item_name()`, etc. Do not rewrite them.
3. **Follow established naming.** Match the file's existing naming style. Python: `snake_case`. TypeScript: `camelCase`/`PascalCase`. Constants: `UPPER_SNAKE_CASE`.
4. **Use type hints** on all Python function signatures. The codebase uses `from __future__ import annotations` and `from typing import ...` consistently.
5. **Use dataclasses** for data structures (not plain dicts or NamedTuples). The codebase uses `@dataclass` extensively.
6. **Verify name mappings** before touching champion/item/trait code. There are three champion name formats and the item API names are obfuscated (see Name Mapping section below).
7. **Test determinism** after any combat engine change. Run `python -m simulator.benchmark` and verify the determinism checks pass.
8. **Validate output** after any simulator change. Run `python -m simulator.validate_output <dir>` to confirm all 19 quality checks pass.
9. **Use Parquet** as the preferred output format. Install `pyarrow` before large runs. JSONL is a 6x larger fallback.
10. **Measure before scaling.** Always benchmark small (10-1000 games) before running large batches. Use end-to-end numbers from `cloud_runner`, not microbenchmark numbers.
11. **Use absolute file paths** in responses and references.
12. **Keep the existing section dividers** in large files. The codebase uses ASCII art comment headers like `# -- Section Name ----` to organize long files.
13. **Split training data by `game_id`**, never by row. Row-level splits leak future game state.
14. **Use gate-based progression** for any scale-up work: Gate A (1k) -> Gate B (50k) -> Gate C (250k) -> Gate D (1M), each with measurable pass criteria.

## DON'Ts (Hard Rules)

1. **Do NOT over-engineer.** Only make changes that are directly requested. Do not add features, refactor surrounding code, add extra error handling, create helper abstractions for one-time operations, or make "improvements" beyond the task.
2. **Do NOT add docstrings, comments, or type annotations to code you didn't change.** Only modify the lines relevant to the task.
3. **Do NOT create new files unless absolutely necessary.** Prefer editing existing files. Do not create README files, documentation files, or utility modules unless explicitly asked.
4. **Do NOT use the legacy simulator code** at `simulator/Simulator/` for any new features. That is Set 4 code. The active simulator is `simulator/core/` and `simulator/game/`.
5. **Do NOT hardcode backend URLs in frontend code.** The Vite proxy handles routing (`/api` -> port 8000, `/ws` -> port 8765).
6. **Do NOT assume data formats.** `combat_data.json` ability variables are **lists** `[0, 1star, 2star, 3star]`, NOT dicts. Always use the `_star_val()` helper.
7. **Do NOT make up performance numbers or cost estimates.** Always derive them from measured benchmarks in `Current Simulation Setup.txt` or `TFT_CLOUD_SIMULATION_PLAN.md`.
8. **Do NOT commit unless explicitly asked.** Never auto-commit, auto-push, or create PRs without direct instruction.
9. **Do NOT use `git status -uall`** - it can cause memory issues on large repos.
10. **Do NOT add emojis** to code, comments, or documentation unless the user explicitly requests them.
11. **Do NOT introduce backwards-compatibility hacks** like renaming unused `_vars`, re-exporting dead types, or adding `// removed` comments. If something is unused, delete it completely.
12. **Do NOT skip validation steps** or bypass safety checks with flags like `--no-verify`. If a check fails, fix the root cause.
13. **Do NOT use relative imports** between the `simulator/game/` and `simulator/core/` packages. Use absolute imports with `sys.path` manipulation as the codebase already does.
14. **Do NOT add error handling for scenarios that cannot happen.** Trust internal code and framework guarantees. Only validate at system boundaries.
15. **Do NOT create feature flags or backwards-compatibility shims.** Just change the code directly.

---

## Directory Structure

```
tft-coach-234/
├── simulator/                     # ACTIVE combat engine + game loop
│   ├── core/
│   │   ├── combat_engine.py       # 4690 lines - tick-based combat (30 FPS)
│   │   ├── champion_abilities.py  # 5124 lines - 99/100 champion handlers
│   │   └── item_effects.py        # 1245 lines - item hooks
│   ├── game/
│   │   ├── game.py                # 718 lines - 8-player game orchestrator
│   │   ├── player.py              # 644 lines - economy, leveling, board
│   │   ├── actions.py             # 530 lines - agents (random, econ, slam)
│   │   ├── constants.py           # 271 lines - game rules, NAME_TO_API mapping
│   │   ├── collector.py           # 162 lines - ML training data snapshots
│   │   ├── champion_pool.py       # Shared champion pool management
│   │   ├── shop.py                # Buy/sell/refresh logic
│   │   └── types.py               # ChampionInstance, Action, RoundResult
│   ├── cloud_runner.py            # 693 lines - production batch runner
│   ├── validate_output.py         # 19 quality checks on output
│   ├── aggregate_results.py       # Merge multiple batch runs
│   ├── benchmark.py               # Throughput + determinism tests
│   ├── data/
│   │   ├── combat_data.json       # 106 champion base stats
│   │   ├── traits.json            # 53 trait definitions
│   │   └── timing_constants.json  # Cast times, missile speeds
│   └── Simulator/                 # LEGACY Set 4 code - DO NOT USE
│
├── models/                        # ML prediction pipeline
│   ├── feature_engineering.py     # 46KB - 7 feature groups
│   ├── data_loader.py             # Streaming + bounded data loading
│   ├── dataset.py                 # PyTorch streaming dataset
│   ├── train_xgboost.py           # External memory XGBoost
│   ├── train_transformer.py       # Streaming transformer training
│   ├── embeddings.py              # Unit/item/position embeddings
│   ├── transformer.py             # Cross-attention architecture
│   ├── counterfactual.py          # Causal "what if" engine
│   ├── trajectory.py              # Game trajectory modeling
│   ├── uncertainty.py             # Bayesian MC Dropout
│   ├── information_theory.py      # Feature MI analysis
│   └── evaluate.py                # Evaluation suite
│
├── app/                           # Coaching application
│   ├── main.py                    # WebSocket server entry point (port 8765)
│   ├── api/server.py              # FastAPI REST endpoints (port 8000)
│   ├── frontend/                  # TypeScript React UI (port 5173)
│   │   ├── src/App.tsx            # Main layout (3-column)
│   │   ├── hooks/                 # useGameState, useMetaComps, usePoolTracker, etc.
│   │   ├── utils/transformBoardData.ts  # Champion name mappings
│   │   └── images/                # 400+ champion/item images
│   ├── state/                     # GameState model + state manager
│   ├── watcher/                   # Log file monitoring (watchdog)
│   └── redux_bridge/              # MetaTFT live data extraction
│
├── data/                          # All data files
│   ├── personal/                  # 163 match history CSV
│   ├── game_data/                 # Set 16 reference (JSONL)
│   └── api/processed/             # Augment data (283 augments)
│
├── tests/                         # Pytest test suite (11 files)
├── scripts/                       # Utility scripts
├── docs/                          # Documentation (architecture, integration, design)
├── archive/                       # Archived code (old frontend, session logs)
├── results/                       # Simulation output directories
│
├── CLAUDE.md                      # Detailed project guide
├── TFT_CODEX_INSTRUCTIONS.md      # ML pipeline spec (49KB, 6 phases)
├── TFT_CLOUD_SIMULATION_PLAN.md   # Scale-up playbook (gate-based)
├── Current Simulation Setup.txt   # Hardware + measured performance snapshot
├── Dockerfile.simulator           # Docker for batch runner
├── requirements.txt               # Backend Python deps
├── requirements-ml.txt            # ML deps (torch, xgboost)
└── requirements-simulator.txt     # Minimal simulator deps (pyarrow only)
```

---

## Critical Name Mappings

### Champion Names (3 Formats)

| Context | Format | Example |
|---------|--------|---------|
| Pool key (lowercase) | `leblanc`, `kaisa` | Used in `constants.py` pool dicts |
| API name | `TFT16_Leblanc`, `TFT16_Kaisa` | Used in `combat_data.json`, collector output |
| Display name | `LeBlanc`, `Kai'Sa` | Used in UI, MetaTFT |

**Known gotchas:**
- `combat_data.json` uses `TFT16_Leblanc` (lowercase b), NOT `TFT16_LeBlanc`
- `combat_data.json` uses `TFT16_Kaisa` (lowercase s), NOT `TFT16_KaiSa`
- The mapping table is in `simulator/game/constants.py` as `NAME_TO_API`
- Frontend mappings are in `app/frontend/utils/transformBoardData.ts`

### Item API Names (Obfuscated)

Riot's internal API names differ from display names. Key examples:

| API Name | Display Name |
|----------|-------------|
| `TFT_Item_Leviathan` | Nashor's Tooth |
| `TFT_Item_MadredsBloodrazor` | Giant Slayer |
| `TFT_Item_NightHarvester` | Steadfast Heart |
| `TFT_Item_UnstableConcoction` | Hand of Justice |
| `TFT_Item_SpectralGauntlet` | Evenshroud |

### Trait Names

- Region traits use **display names**: `'Demacia'`, `'Void'`, `'Ionia'` (not API format)
- 5 pair synergies detected by champion API names (Ambessa+Kindred, Jarvan+Shyvana, etc.)

---

## Combat Data Format

**CRITICAL**: `combat_data.json` ability variables are **lists**, not dicts.

```json
{
  "TFT16_Fiddlesticks": {
    "hp": [650, 1170, 2106],
    "ad": [50, 75, 112.5],
    "ability": {
      "variables": {
        "Damage": [0, 200, 300, 450]
      }
    }
  }
}
```

- Index 0 is unused/base, indices 1-3 are star levels 1/2/3
- Always use `_star_val(var_data, star_level, default)` in `combat_engine.py`
- Always use `_get_var()` method in `champion_abilities.py`
- Both handlers support list AND dict formats for safety

---

## Simulator Architecture

### Combat Engine (`simulator/core/combat_engine.py`)

- **Tick rate**: 0.033s (~30 FPS)
- **Max combat**: 60 seconds
- **Board**: 4 rows x 7 cols = 28 hexes
- **Deterministic**: Same seed = same outcome, always
- **Star scaling**: HP (1.0/1.8/3.24), AD (1.0/1.5/2.25)
- **AS hard cap**: 5.0, Guinsoo's max 20 stacks
- **Mana on damage taken**: 1% pre-mit + 3% post-mit, capped at 42.5
- **CC types**: STUNNED, FEARED (random move), TAUNTED (forced target), ROOTED (no move)

### Champion Abilities (`simulator/core/champion_abilities.py`)

- **99/100** champions have `_cast_*` handlers
- Dynamic dispatch: `getattr(self, f"_cast_{api_name.replace('TFT16_', '').lower()}")`
- 6 combat-only units have no shop presence: AnnieTibbers, Atakhan, AzirSoldier, FreljordProp, MalzaharVoidling, PiltoverInvention

### Item Effects (`simulator/core/item_effects.py`)

- Hook system: `on_hit`, `on_attack`, `on_damage_dealt`, `on_damage_taken`, `on_ability_cast`, `passive`, `on_combat_start`
- Radiant items inherit base effects via `_resolve_item_name()` (strips "Radiant" prefix)
- 28 base craftable (all), 22/36 artifacts, 8/8 Bilgewater, 15/17 Piltover modules

### Game Loop (`simulator/game/`)

- Full 8-player games with economy, shop, leveling, augments, carousel, matchmaking
- Agents: `fast_random_agent` (O(1)), `econ_agent` (saves gold), `slam_agent` (equips items)
- Agent mixing: `--agent-mix random:50,econ:30,slam:20`
- Training data: ~132 rows per game via `collector.py`

### Batch Runner (`simulator/cloud_runner.py`)

```bash
# Generate training data
python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch

# Validate output (19 checks)
python -m simulator.validate_output results/batch

# Benchmark throughput + determinism
python -m simulator.benchmark
```

- **Checkpoint/resume**: `--resume DIR` continues from `checkpoint.json`
- **Error handling**: Per-game try/except, errors logged to `errors.json`
- **Output**: Parquet chunks (preferred) or JSONL chunks + `summary.json`

---

## ML Pipeline

### Feature Engineering (7 groups, `models/feature_engineering.py`)

1. **Composition** (20 features): team cost, star levels, HP/AD pools
2. **Economy** (8 features): level, HP, gold, streak
3. **Traits** (53+ features): activation tiers, counts
4. **Items** (30 features): completed items, BiS, type counts
5. **Augments** (10 features): tier sum, types
6. **Matchup** (15 features): cost/star advantage vs opponent
7. **Personal** (optional): historical performance weights

### Training Data Schema (from collector)

```python
{
    "game_id": int,         # Split by this, NOT by row
    "round": int,
    "player_id": int,       # 0-7
    "level": int,           # 1-10
    "hp": int,              # 0-100
    "gold": int,
    "streak": int,
    "units": [...],         # Up to 14 (board + bench)
    "traits": {"Void": 3},
    "augments": [...],      # Up to 3
    "opponent_units": [...],
    "combat_result": 0|1|2, # Loss/Win/Draw
    "placement": 1-8        # On elimination/win
}
```

### Target Metrics

| Model | Fight Accuracy | Top4 Accuracy | Placement MAE |
|-------|---------------|---------------|---------------|
| XGBoost baseline | >65% | >70% | <1.5 |
| Transformer | >80% | >82% | <1.2 |

### Key ML Rules

- Use `label_mode=next_round` + game-hash split (no data leakage)
- External-memory XGBoost for datasets > RAM via `--external-memory`
- Streaming transformer via `models/dataset.py` for large datasets
- Device fallback: try CUDA -> MPS -> CPU

---

## Frontend

### Technology

- React 18 + TypeScript (strict mode) + Vite 7 + Tailwind CSS 4
- Single UI at `app/frontend/` (the old JS frontend is archived)

### Key Hooks

| Hook | Purpose |
|------|---------|
| `useGameState` | WebSocket connection with auto-reconnect (port 8765) |
| `useMetaComps` | Fetch meta compositions from `/api/meta-comps` |
| `usePoolTracker` | Track unit pool availability across 8 players |
| `useEarlyComps` | Fetch early game compositions |

### Vite Proxy (do NOT hardcode URLs)

```typescript
// vite.config.ts
server: {
  port: 5173,
  proxy: {
    '/api': { target: 'http://127.0.0.1:8000' },
    '/ws': { target: 'ws://127.0.0.1:8765', ws: true }
  }
}
```

### Component Pattern

```typescript
interface MyComponentProps {
  data: SomeType;
  onAction: (id: string) => void;
}

function MyComponent({ data, onAction }: MyComponentProps) {
  // Component logic
}

export default MyComponent;
```

---

## Python Coding Conventions

### Imports (order matters)

```python
# 1. Future annotations
from __future__ import annotations

# 2. Standard library
import json
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 3. Third-party
import numpy as np
import pandas as pd

# 4. Local (relative within package)
from .types import ChampionInstance, Action
from .constants import POOL_SIZES

# 5. Cross-package (absolute with sys.path)
from simulator.core.combat_engine import CombatEngine
```

### Type-Checking Imports (for circular dependencies)

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .combat_engine import CombatEngine, Unit
```

This pattern is used between `combat_engine.py`, `champion_abilities.py`, and `item_effects.py`.

### Module-Level Caching

```python
_COMBAT_DATA_CACHE: Dict[str, Any] = {}

def _load_combat_data(path: Path) -> dict:
    key = str(path)
    if key not in _COMBAT_DATA_CACHE:
        with open(path, 'r', encoding='utf-8') as f:
            _COMBAT_DATA_CACHE[key] = json.load(f)
    return _COMBAT_DATA_CACHE[key]
```

### Optional Dependencies

```python
def _pyarrow_available() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except Exception:
        return False
```

### Section Headers in Large Files

```python
# -- Economy -------------------------------------------------------------------
# -- Leveling ------------------------------------------------------------------
# -- Shop / Buying -------------------------------------------------------------
```

Keep these when editing large files. Do not remove or restyle them.

### Error Handling Style

```python
# Per-game isolation (batch runner pattern)
try:
    result = run_game(args)
    return {'status': 'ok', **result}
except Exception:
    return {'status': 'error', 'error': traceback.format_exc()}
```

### Logging (print-based, not logging module)

```python
print(f"[INFO] Processing {count} games...")
print(f"[ERROR] Failed to load data: {error}")
print(f"[SUCCESS] Saved to {output_path}")
```

---

## TypeScript Coding Conventions

### Strict Mode

- `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch` are all enabled
- Module: ESNext, bundler resolution, JSX: react-jsx

### Custom Hooks Pattern

```typescript
export function useMyHook(options: Options = {}): Result {
  const [data, setData] = useState<DataType | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // ... hook logic
  return { data, loading, error };
}
```

### Type Definitions

```typescript
// Use interfaces for component props
interface DualBoardProps {
  playerUnits: Unit[];
  opponentUnits: Unit[];
}

// Use type for unions
type ItemTab = 'Craftable' | 'Artifact' | 'Emblem' | 'Radiant';
```

---

## Git Conventions

### Commit Message Format

Follow conventional commits as seen in the git history:

```
feat(simulator): add run-control flags to cloud runner
feat(ml): add streaming transformer and external-memory xgboost support
fix: correct Model description to match actual simulator implementation
chore: Sync TFT data [automated]
chore(data): remove tokenized script and add checkpoints/results artifacts
test(simulator): update unit tests for revised state and mappings
audit(items): fix 10 recipe errors, add aliases, tank HP stats
docs: update SIMULATOR_AUDIT.md with completed audit results
```

### Scope Tags

`simulator`, `ml`, `data`, `frontend`, `items`, `economy`, `augments`, `xref`

### Rules

- Never commit without explicit user request
- Never force push
- Never use `-uall` with git status
- Never amend published commits
- Prefer specific file staging over `git add -A`

---

## Testing

### Framework

Pytest, with 11 test files in `tests/`.

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_validate_output.py

# With coverage
pytest --cov=models --cov-report=html
```

### Simulator Verification

```bash
# Determinism + throughput
python -m simulator.benchmark

# Output quality (19 checks)
python -m simulator.validate_output results/batch

# Reference data integrity
python -m simulator.data.validate_reference_data
```

### Key Test Patterns

- **Determinism**: Same seed must produce identical results across runs
- **Padding invariance**: Padded boards must produce same predictions as unpadded
- **Permutation invariance**: Shuffled unit order must not change model output
- **Strong vs weak**: Model must rank a 3-star carry board above 1-star 1-costs

---

## Performance Reference (Measured 2026-02-07)

| Metric | Value |
|--------|-------|
| Engine load time | 0.008s |
| 1v1 combat | 177.7 sims/sec |
| 4v4 team combat | 63.3 sims/sec |
| Full 8-player game | 1.325 sec/game (2,717 games/hour/core) |
| End-to-end batch (11 workers) | 4.13 games/sec (14,868 games/hour) |
| Rows per game | ~132 |
| Storage per 1K games | ~12 MB (Parquet), ~73 MB (JSONL) |

### Scale-Up Estimates

| Games | Est. Rows | Parquet Size | Time (11 workers) |
|-------|-----------|-------------|-------------------|
| 1,000 | 132K | ~12 MB | ~4 min |
| 50,000 | 6.6M | ~600 MB | ~3.4 hours |
| 250,000 | 33M | ~3 GB | ~17 hours |
| 1,000,000 | 132M | ~12-20 GB | ~67 hours |

---

## Known Issues & Gaps

| Issue | Status | Notes |
|-------|--------|-------|
| Augment combat effects | Largest gap | 283 augments selected, ~0 have combat effects |
| 36 ranged champions | Missing | No missile speeds in timing data |
| 42 obfuscated trait vars | Data issue | Hex hash names in `traits.json` |
| Some artifact items | Stats-only | Fishbones, CappaJuice, EternalPact lack combat effects |
| Wukong ability handler | Bug | `defender=None` possible, pre-existing |
| Legacy `simulator/Simulator/` | Stale | Set 4 trait logic, do not use |

---

## Quick Reference Commands

```bash
# Start everything (frontend + backend)
npm start

# Simulator batch run
python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch

# Validate output
python -m simulator.validate_output results/batch

# Benchmark
python -m simulator.benchmark

# Docker build + run
docker build -f Dockerfile.simulator -t tft-sim .
docker run tft-sim --games 1000 --workers 8

# Frontend only
cd app/frontend && npm run dev

# Backend only
python -m app.api.server

# Run tests
pytest
```

---

## Key Documentation Files

| File | Size | Purpose |
|------|------|---------|
| `CLAUDE.md` | 16KB | Detailed project guide with architecture diagrams |
| `TFT_CODEX_INSTRUCTIONS.md` | 49KB | ML pipeline spec (6 phases, target metrics, schemas) |
| `TFT_CLOUD_SIMULATION_PLAN.md` | 18KB | Gate-based scale-up playbook (50k -> 250k -> 1M) |
| `Current Simulation Setup.txt` | 5KB | Measured hardware + performance snapshot |
| `docs/INDEX.md` | - | Documentation navigation hub |

Read these files before starting work that touches their domains.

---

## Trait Coverage Summary (48/48 accounted for)

- **33 traits**: TraitManager stat effects (pre-combat buffs + combat-time markers)
- **13 traits**: Handled in `champion_abilities.py` (champion-specific passives)
- **2 traits**: Non-combat (Chronokeeper XP, Targon no-stat)
- Region traits use display names: `'Demacia'`, `'Void'`, `'Ionia'`
- Complex traits (Zaun/Noxus/Ionia) have setup markers but limited combat-time logic

---

## Champion Pool (Set 16)

| Cost | Champions | Copies Each |
|------|-----------|-------------|
| 1 | 14 | 30 |
| 2 | 19 | 25 |
| 3 | 18 | 18 |
| 4 | 25 | 10 |
| 5 | 18 | 9 |
| 7 | 6 | 9 (shares 5-cost odds) |

**100 rollable** + **6 combat-only** (summons, not in shop pool)

---

## Heuristic Agents

| Agent | Strategy | Use Case |
|-------|----------|----------|
| `fast_random_agent` | O(1) random actions | Baseline, smoke tests |
| `econ_agent` | Saves for interest (50g floor), levels to 8 | Realistic economy play |
| `slam_agent` | Equips items immediately, buys everything | Aggressive item usage |
| `MixedLobbyAgent` | Different agent per player | Diverse training data |

Profiles: `random`, `mixed` (50/30/20), `ladder` (20/45/35), or custom `--agent-mix`

---

*Last updated: 2026-02-12*
