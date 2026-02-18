# AGENTS.md - AI Assistant Rules for TFT Coach

> Universal rules for any AI coding assistant (Claude Code, Codex, Copilot, Cursor, etc.) working on this codebase.
> This document is self-contained. Read it fully before making any changes.
> **Keep AGENTS.md and CLAUDE.md in sync** (they should contain the same rules).
> Last updated: 2026-02-18

---

## READ THIS FIRST (One Screen)

These are the rules that break the project if ignored:

1. **Minimal scope.** No drive-by refactors or “cleanups” unless explicitly asked.
2. **Determinism + schema gates.**
   - If you touch combat logic: run `python -m simulator.benchmark` and determinism checks must pass.
   - If you touch collector/output: run `python -m simulator.validate_output <dir>` and all 19 checks must pass.
3. **No data leakage.** Any training/validation split must be by `game_id` (never by row).
4. **Don’t guess data formats.** `combat_data.json` ability variables are lists `[0, 1★, 2★, 3★]`. Use `_star_val()` / `_get_var()` (never index manually).
5. **Legacy simulator is off-limits.** Don’t add new features to `simulator/Simulator/` (Set 4). Use `simulator/core/` and `simulator/game/`.
6. **Measure before scaling.** Benchmark small (10–1000 games) before big runs. Use end-to-end numbers from `cloud_runner`.
7. **No invented performance/cost claims.** Only report measured numbers from existing docs or fresh benchmarks you ran.
8. **Cloud simulation ≠ GPU.** The simulator is CPU-bound. For any EC2 simulation run:
   - Read `AWS_GATES_RUNBOOK.md` before touching the console.
   - Correct instance: `c8g.48xlarge` (192 ARM cores). Wrong instance: any `g*` GPU type.
   - Always verify the Rust engine is built (`python -c "import tft_combat_engine"`) before a large run.
   - Always run a ≤100-game smoke test before any run > 1,000 games.

9. **No secrets in chat.** Never request, accept, or use access tokens (GitHub PATs, AWS keys) in plaintext.
   - Use GitHub deploy keys (SSH) or instance roles instead.
   - If a secret is pasted, tell the user to revoke/rotate it and do not echo it back.

10. **Docs + continuity are part of the work.** Keep `docs/` consistent, and update `.agent/CONTINUITY.md` on meaningful deltas.
11. **Close the loop.** Before any “done” response: run the ntfy notification script and end with **Next Improvements**.

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

## Documentation Sync Rule

- After completing any batch of changes, scan `docs/INDEX.md` and the files it references.
- If any changed code, schema, config, or workflow invalidates or gaps existing documentation in `docs/`, update the affected doc(s) in the same task.
- If a doc update is needed but out of scope, add a `TODO(docs):` entry to `.agent/CONTINUITY.md` under `[PLANS]` with the file path and what changed.
- Do NOT create new doc files unless explicitly asked — only update existing ones.

## Autonomous Completion Checklist (One Screen)

Use this when running autonomously, or when the user asks to "do it end-to-end".

1. Re-read the request and restate concrete success criteria.
2. Read `.agent/CONTINUITY.md` before acting (autonomous sessions).
3. Implement the minimal-scope change (no drive-by refactors).
4. Verify based on what changed (or run `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify.ps1 -Mode changed` to auto-pick checks).
5. Update `.agent/CONTINUITY.md` on meaningful deltas.
6. Before the final response, run the ntfy notification (Completion Notification Rule).
7. End the response with a short **Next Improvements** section.

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
4. **Use type hints** on all new or changed Python function signatures. The codebase uses `from __future__ import annotations` and `from typing import ...` consistently.
5. **Use dataclasses** for data structures (not plain dicts or NamedTuples). The codebase uses `@dataclass` extensively.
6. **Verify name mappings** before touching champion/item/trait code. There are three champion name formats and the item API names are obfuscated (see Name Mapping section below).
7. **Test determinism** after any combat engine change. Run `python -m simulator.benchmark` and verify the determinism checks pass.
8. **Validate output** after any simulator change. Run `python -m simulator.validate_output <dir>` to confirm all 19 quality checks pass.
10. **Use Parquet** as the preferred output format. Install `pyarrow` before large runs. JSONL is a 6x larger fallback.
11. **Measure before scaling.** Always benchmark small (10-1000 games) before running large batches. Use end-to-end numbers from `cloud_runner`, not microbenchmark numbers.
12. **Use absolute file paths** in responses and references. Repo-root-relative paths like `simulator/core/combat_engine.py` are preferred over ambiguous `../` paths.
13. **Keep the existing section dividers** in large files. The codebase uses ASCII art comment headers like `# -- Section Name ----` to organize long files.
14. **Split training data by `game_id`**, never by row. Row-level splits leak future game state.
15. **Use gate-based progression** for any scale-up work: Gate A (1k) -> Gate B (50k) -> Gate C (250k) -> Gate D (1M), each with measurable pass criteria.
16. **Read `AWS_GATES_RUNBOOK.md` before any EC2 action.** It has the correct instance type,
    launch scripts, Rust build steps, and gate commands. Do not recommend or launch an instance
    without reading it first. If the user requests a GPU instance for simulation, flag the mismatch
    explicitly before proceeding.


## DON'Ts (Hard Rules)

1. **Do NOT over-engineer.** Only make changes that are directly requested. Do not add features, refactor surrounding code, add extra error handling, create helper abstractions for one-time operations, or make "improvements" beyond the task.
2. **Do NOT add docstrings, comments, or type annotations to code you didn't change.** Only modify the lines relevant to the task.
3. **Do NOT create new files unless absolutely necessary.** Prefer editing existing files. Do not create README files, documentation files, or utility modules unless explicitly asked.
4. **Do NOT use the legacy simulator code** at `simulator/Simulator/` for any new features. That is Set 4 code. The active simulator is `simulator/core/` and `simulator/game/`.
5. **Do NOT hardcode backend URLs in frontend code.** The Vite proxy handles routing (`/api` -> port 8000, `/ws` -> port 8765).
6. **Do NOT assume data formats.** `combat_data.json` ability variables are **lists** `[0, 1star, 2star, 3star]`, NOT dicts. Always use the `_star_val()` helper.
7. **Do NOT make up performance numbers or cost estimates.** Always derive them from measured benchmarks in `Current Simulation Setup.txt` or `TFT_CLOUD_SIMULATION_PLAN.md`.
8. **Do NOT commit unless explicitly asked.** Never auto-commit, auto-push, or create PRs without direct instruction.
9. **Do NOT request, accept, or use secrets in plaintext.** No GitHub PATs, no AWS keys, no copying tokens into SSM commands. Use deploy keys / instance roles. If a user posts a secret, instruct them to revoke/rotate it and redact it from any outputs.
10. **Do NOT use `git status -uall`** - it can cause memory issues on large repos.
11. **Do NOT add emojis** to code, comments, or documentation unless the user explicitly requests them.
12. **Do NOT introduce backwards-compatibility hacks** like renaming unused `_vars`, re-exporting dead types, or adding `// removed` comments. If something is unused, delete it completely.
13. **Do NOT skip validation steps** or bypass safety checks with flags like `--no-verify`. If a check fails, fix the root cause.
14. **Do NOT use relative imports** between the `simulator/game/` and `simulator/core/` packages. Use absolute imports with `sys.path` manipulation as the codebase already does.
15. **Do NOT add error handling for scenarios that cannot happen.** Trust internal code and framework guarantees. Only validate at system boundaries.
16. **Do NOT create feature flags or backwards-compatibility shims.** Just change the code directly.
17. **Do NOT launch a GPU instance (`g5`, `g6`, `g6e`, `p3`, etc.) for simulation runs.**
    GPU instances are for ML training only. Simulation is CPU-bound. The cost of the wrong
    instance is measured in hours and dollars, not seconds.
18. **Do NOT start a run > 1,000 games without first verifying:**
    - `import tft_combat_engine` succeeds (Rust engine is built)
    - A ≤100-game smoke run completes and shows expected throughput
    - `--engine rust_full` is explicitly set


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

## AWS Batch Simulation (Beginner Guide)

> Goal: Run `simulator.cloud_runner` on a large EC2 instance, store outputs in S3, and avoid SSH by using AWS Systems Manager (SSM) Session Manager.

### 1) Create an S3 Bucket (Results Storage)

AWS Console steps:

1. Go to **S3** -> **Buckets** -> **Create bucket**
2. Bucket name: something like `tft-sim-results-<yourname>`
3. Region: pick the same region you plan to run EC2 in
4. **Block Public Access**: leave ON (recommended)
5. **Bucket Versioning**: optional (usually OFF for large generated data; costs more if ON)
6. **Default encryption**: ON (SSE-S3 is fine)
7. Create bucket

Suggested prefix layout in the bucket:

- `tft-results/calib/` (throwaway tests)
- `tft-results/gates/` (Gate A/B/C)
- `tft-results/prod/` (gold datasets you trained on)

### 2) Create the EC2 IAM Role (So the Instance Can Upload to S3 + Use SSM)

AWS Console steps:

1. Go to **IAM** -> **Roles** -> **Create role**
2. Trusted entity:
   - Select **AWS service**
   - Use case: **EC2**
   - This creates the *trust policy* (it should include `sts:AssumeRole` + `ec2.amazonaws.com`)
3. Permissions:
   - Attach **AmazonSSMManagedInstanceCore** (so you can connect via Session Manager)
4. Create the role (example name: `tft-sim-ec2-role`)

Add the S3 permissions policy snippet (this is **NOT** the trust policy):

1. IAM -> Roles -> `tft-sim-ec2-role` -> **Permissions** tab
2. Click **Add permissions** -> **Create inline policy**
3. Choose the **JSON** tab, paste the S3 policy JSON, and edit:
   - `YOUR_BUCKET`
   - the prefix (for example `tft-results/*`)
4. Review + name it (example: `tft-results-s3-write`) -> Create

Example S3 write policy (edit bucket + prefix):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucketPrefix",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::YOUR_BUCKET"],
      "Condition": { "StringLike": { "s3:prefix": ["tft-results/*"] } }
    },
    {
      "Sid": "WriteObjects",
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:AbortMultipartUpload"],
      "Resource": ["arn:aws:s3:::YOUR_BUCKET/tft-results/*"]
    }
  ]
}
```

### 3) Add S3 Lifecycle Rules (Auto-Expire Old Runs)

This prevents storage creep. Use different rules per prefix (calib vs prod).

AWS Console steps:

1. S3 -> your bucket -> **Management** tab -> **Lifecycle rules** -> **Create lifecycle rule**
2. Rule name: `expire-calib-30d` (example)
3. Choose rule scope:
   - **Limit the scope of this rule using one or more filters**
   - Filter type: **Prefix**
   - Prefix: `tft-results/calib/`
4. Actions:
   - Optional: **Transition current versions of objects between storage classes**
     - Example: transition to **Standard-IA** after 7 days
   - **Expire current versions of objects**
     - Example: expire after 30 days
   - Recommended: **Abort incomplete multipart uploads**
     - Example: abort after 7 days
5. Create rule

Repeat for other prefixes with longer retention:

- `tft-results/gates/`: expire after 90-180 days (optional transition to IA after 14-30 days)
- `tft-results/prod/`: 6-12 months minimum; consider transitioning to Glacier tiers rather than expiring

### 4) Launch the EC2 Instance (Ubuntu + User Data)

AWS Console steps:

1. EC2 -> **Instances** -> **Launch instances**
2. AMI: Ubuntu 22.04 LTS (x86_64)
3. Instance type: pick the compute-optimized size you want (make sure your account has quota)
4. Key pair: optional if using SSM only (no SSH required)
5. Network settings:
   - Security group: you can run with **no inbound rules** when using Session Manager
6. Storage:
   - Use `gp3` and size it for your target output (Parquet is much smaller than JSONL)
7. Advanced details:
   - **IAM instance profile**: select `tft-sim-ec2-role`
   - **User data**: paste a cloud-init script that installs deps, builds the Rust extension, runs the simulator, and uploads to S3

If your AWS account can’t launch the big instance type:

1. Go to **Service Quotas** -> **Amazon Elastic Compute Cloud (Amazon EC2)**
2. Find quotas for **Running On-Demand vCPUs** (and the instance family you want)
3. Request an increase in the region you’re launching in

Example user-data (cloud-init) script (edit the CONFIG block):

```bash
#!/bin/bash
set -euo pipefail
exec > >(tee -a /var/log/tft-user-data.log) 2>&1

# ---------------- CONFIG ----------------
REPO_URL="https://github.com/YOUR_GITHUB_USER_OR_ORG/tft-coach-234.git"
REPO_REF="main"  # branch/tag/sha

RUN_ID="aws_calib_10k_$(date +%Y%m%d_%H%M%S)"
TOTAL_GAMES=10000
WORKERS="$(nproc)"
ENGINE="rust_full"
AGENT_PROFILE="mixed"

S3_URI="s3://YOUR_BUCKET/tft-results/calib/${RUN_ID}/"
OUTDIR="/home/ubuntu/tft-coach-234/results/${RUN_ID}"
# ---------------------------------------

apt-get update
apt-get install -y git python3 python3-venv python3-pip python3-dev build-essential pkg-config libssl-dev curl awscli

# Install Rust toolchain (as ubuntu user)
sudo -u ubuntu -H bash -lc 'curl https://sh.rustup.rs -sSf | sh -s -- -y'

# Clone repo
sudo -u ubuntu -H bash -lc "cd /home/ubuntu; if [ ! -d tft-coach-234 ]; then git clone --filter=blob:none ${REPO_URL} tft-coach-234; fi"
sudo -u ubuntu -H bash -lc "cd /home/ubuntu/tft-coach-234; git fetch --all --tags; git checkout ${REPO_REF}"

# Python venv + minimal deps for simulator batch
sudo -u ubuntu -H bash -lc "cd /home/ubuntu/tft-coach-234; python3 -m venv .venv; source .venv/bin/activate; pip install -U pip"
sudo -u ubuntu -H bash -lc "cd /home/ubuntu/tft-coach-234; source .venv/bin/activate; pip install -r requirements-simulator.txt maturin"

# Build Rust extension into the venv
sudo -u ubuntu -H bash -lc "cd /home/ubuntu/tft-coach-234/simulator/core/rust_engine; source /home/ubuntu/tft-coach-234/.venv/bin/activate; maturin develop --release"

# Run
sudo -u ubuntu -H bash -lc "cd /home/ubuntu/tft-coach-234; source .venv/bin/activate; mkdir -p \"${OUTDIR}\"; \
  python -m simulator.cloud_runner --engine ${ENGINE} --games ${TOTAL_GAMES} --workers ${WORKERS} \
    --output \"${OUTDIR}\" --agent-profile ${AGENT_PROFILE} --require-parquet --progress-every 500"

# Upload results to S3 (uses instance role creds)
aws s3 sync "${OUTDIR}" "${S3_URI}" --only-show-errors
echo "Uploaded to ${S3_URI}"
```

Private GitHub repo note:

- Avoid putting a GitHub token directly into user-data (it can leak via logs/metadata).
- For private repos, prefer an SSH deploy key or fetch a source tarball from S3.

### 5) Connect Without SSH (Session Manager)

AWS Console steps:

1. EC2 -> Instances -> select your instance -> **Connect** -> **Session Manager**
2. Or: Systems Manager -> **Session Manager** -> **Start session**

If the instance doesn’t show up in Session Manager:

- Confirm the instance role includes `AmazonSSMManagedInstanceCore`
- Confirm the instance has outbound network access to SSM endpoints (default VPC + public internet works)
- Check agent status on the instance (Ubuntu is often preconfigured, but not always):
  - `systemctl status amazon-ssm-agent` (or `snap services amazon-ssm-agent`)

On the instance, tail user-data logs:

```bash
sudo tail -f /var/log/tft-user-data.log
```

### 6) Validate Upload Worked

AWS Console:

- S3 -> your bucket -> browse to `tft-results/...`

On the instance:

```bash
aws s3 ls s3://YOUR_BUCKET/tft-results/ --recursive | head
```

### 7) Scale Out (Optional): Shard Across Multiple Instances

If you run multiple smaller boxes, shard deterministically:

```bash
python -m simulator.cloud_runner --engine rust_full --games 1000000 --num-shards 10 --shard-index 0 --output results/shard_00 ...
python -m simulator.cloud_runner --engine rust_full --games 1000000 --num-shards 10 --shard-index 1 --output results/shard_01 ...
```

Each shard runs a disjoint contiguous seed range (so you can merge results later).

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

*Last updated: 2026-02-18*
