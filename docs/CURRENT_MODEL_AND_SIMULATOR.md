# Current Model + Simulator (TFT Coach)

Last updated: 2026-02-16

This document describes what the repo currently implements for:

- The Set 16 full-game simulator (8-player lobbies + tick-based combat)
- The current ML stack (XGBoost baseline + cross-attention transformer)
- Why simulation is the highest-leverage tool for improving the coach right now

It is intended to be source-of-truth aligned with:

- `Current Simulation Setup.txt`
- `TFT_CLOUD_SIMULATION_PLAN.md`
- `models/` and `simulator/` code as implemented
- `coach implementation.md` (planning-with-a-critic direction)

## 0) Executive Summary (What We Have + Why It Matters)

We already have a deterministic Set 16 simulator that can generate large volumes of labeled decision-time snapshots (one row per alive player per PvP round) via `python -m simulator.cloud_runner`. That gives us two immediate wins:

- We can *score candidate decisions* (items, positioning, stabilization) with ground-truth combat outcomes from the same engine we train on.
- We can *train models* (baseline XGBoost and the transformer) on effectively unlimited, consistent data without needing full logged human trajectories.

In other words: simulation lets the coach be "smart" today via search + scoring, and it also feeds the ML pipeline that will eventually replace or accelerate parts of scoring.

## 1) Simulator (Current State)

### 1.1 Primary Runtime Mode: Batch Full-Game Simulation

The production data-generation path is:

```bash
python -m simulator.cloud_runner
```

This runs complete 8-player lobbies from early rounds through elimination, collects per-round snapshots, and writes chunked datasets:

- Preferred output: Parquet chunks (requires `pyarrow`)
- Fallback output: JSONL chunks

Concurrency is Python multiprocessing (not Ray).

### 1.2 Code Map (What Files Matter)

Core entry points and tools:

- `simulator/cloud_runner.py`: production batch runner (multiprocessing, chunked output, checkpoint/resume)
- `simulator/validate_output.py`: output quality gates (19 checks)
- `simulator/benchmark.py`: throughput + determinism checks
- `Current Simulation Setup.txt`: measured performance and coverage snapshot (used for planning)
- `TFT_CLOUD_SIMULATION_PLAN.md`: gate-based scale-up plan grounded in measured summaries

Game loop:

- `simulator/game/game.py`: 8-player orchestrator (round loop, matchmaking, augment rounds, carousel)
- `simulator/game/player.py`: player economy/leveling/board/bench state
- `simulator/game/shop.py`: shop roll/buy logic and pool depletion (plus sell returns)
- `simulator/game/constants.py`: game constants + name mappings
- `simulator/game/collector.py`: round snapshots -> ML rows + analytics

Combat engine:

- `simulator/core/combat_engine.py`: tick-based combat loop, targeting, movement, damage/mana, projectile timing
- `simulator/core/champion_abilities.py`: `_cast_*` handlers (per-champion ability logic)
- `simulator/core/item_effects.py`: item hooks (on-hit, passives, on-cast, etc)

### 1.3 High-Level Architecture

The simulator has two main subsystems:

1. Game loop (`simulator/game/`)
2. Combat engine (`simulator/core/`)

The game loop handles economy, shop, augments, carousel, matchmaking, and round flow. When a PvP round happens, boards are passed into the combat engine, which resolves deterministic combat at ~30 FPS for up to 60 seconds.

### 1.4 Game Loop Specs (8-Player Lobby)

Core constraints:

- Players per game: 8
- Board: 4 rows x 7 cols = 28 hexes
- Bench size: 9
- Shop size: 5
- Item bench size: 10
- Max items per unit: 3
- Max level: 10

Economy/progression highlights:

- Base income: 5 gold/round
- Interest: +1 per 10g, max +5
- Refresh cost: 2 gold
- XP buy cost: 4 gold for 4 XP
- Passive XP: +2 per round
- Streak gold and round-specific income are implemented (see `Current Simulation Setup.txt` for the full table).

Augments:

- Selection rounds: 4 (2-1), 11 (3-2), 18 (4-2)
- Active augment dataset: `data/api/processed/augments_set16.json` (283 augments loaded)

Round flow:

- Rounds 0-3: simplified PvE economy/item-drop phase (not full PvE combat sim)
- Round 4 onward: PvP loop
- Safety valve: stop if round > 60

### 1.5 Batch Runner Behavior (cloud_runner)

`simulator/cloud_runner.py` is designed for long-running dataset generation:

- Chunked outputs (avoid OOM and allow partial results to be usable)
- Checkpoint/resume (`checkpoint.json`) so interrupted runs can continue
- Per-game isolation (errors are captured and written to `errors.json` rather than killing the whole run)
- Summary analytics written to `summary.json` (runtime, throughput, win/top4 stats, Wilson confidence intervals, etc)
- Optional reference-data preflight validation before running

Agent profiles supported (used to vary the distribution of generated states):

- `random`: optimized `fast_random_agent` for throughput
- `mixed`: `random/econ/slam = 50/30/20`
- `ladder`: `random/econ/slam = 20/45/35`
- Custom weighted mixes via `--agent-mix`

### 1.6 Combat Engine Specs

Core mechanics:

- Tick rate: 0.033s per tick (~30 FPS)
- Max combat time: 60.0 seconds
- Hex move time: 0.5s per hex (base)
- Attack speed hard cap: 5.0
- Star scaling:
  - HP: 1.0 / 1.8 / 3.24
  - AD: 1.0 / 1.5 / 2.25

Implemented systems include:

- Physical/magic/true damage with armor/MR mitigation
- Crit support
- DOT effects
- Burn / wound / sunder / shred application + expiry tracking
- Projectile tracking (timing data used when available)
- CC states: stunned, feared, taunted, rooted (plus casting/moving/etc)

### 1.7 Content Coverage (Champions / Items / Traits / Augments)

Champions:

- Rollable shop champions: 100
- Combat data entries: 106 (`simulator/data/combat_data.json`)
- The 6 "extra" combat-only / non-shop units:
  - `TFT16_AnnieTibbers`, `TFT16_Atakhan`, `TFT16_AzirSoldier`,
    `TFT16_FreljordProp`, `TFT16_MalzaharVoidling`, `TFT16_PiltoverInvention`

Abilities:

- `ChampionAbilities` has 103 `_cast_*` handlers
- Combat-data units with matching cast handlers: 102/106
- Missing handlers correspond to helper objects without normal cast behavior (soldiers/towers/etc)

Items:

- Item catalog size (`ALL_ITEMS`): 134
- Item hooks implemented (examples): `on_hit`, `on_attack`, `on_damage_dealt`, `on_damage_taken`, `on_ability_cast`, `passive`, `on_combat_start`
- Multiple item categories exist (components, completed, artifacts, radiant, emblems, etc). See `Current Simulation Setup.txt` for counts.

Traits:

- Trait definitions loaded: 53 (`simulator/data/traits.json`)
- Trait manager contains multiple trait-effect dictionaries, with a subset actively applied as stat traits and some special-case handling.

Augments:

- Active augment data loaded: 283
- Explicit hero augment logic: 4 (as of the 2026-02-07 snapshot)
- AugmentManager supports multiple categories (team stat, trait-conditional, champion-specific, hex effects, event-driven, item-conditional), but complex edge interactions remain a known fidelity risk.

### 1.8 Output: Training Rows + Analytics

The main output for ML is produced by `simulator/game/collector.py`:

- Collection timing: `on_round_start` is called after matchmaking and **before combat resolves**
- Each PvP round yields one row per alive player snapshot, plus the opponent snapshot for the matched combat

Each training row includes (representative, see `simulator/game/collector.py`):

- Identifiers: `game_id`, `round`, `player_id`
- Economy: `hp`, `gold`, `level`, `streak`, `win_streak`, `loss_streak`
- Board state: `units` (champion_id, star_level, items, position), `traits`, `augments`
- Opponent snapshot: `opponent_units`, `opponent_traits`, `opponent_hp`, `opponent_gold`, `opponent_level`, etc
- Combat outcome metadata for that round: `combat_result`, `damage_dealt`, `damage_taken`, `combat_time`, `survivors`
- Final label: `placement` (1-8)

This row format is what makes simulation so useful: it creates decision-time snapshots aligned with outcomes.

### 1.9 Determinism + Throughput (Measured)

The repo has a deterministic benchmark harness:

```bash
python -m simulator.benchmark
```

Measured (2026-02-07, see `Current Simulation Setup.txt`):

- Engine load time: 0.008s
- 1v1 combat: 177.7 sims/sec
- Team combat (4v4): 63.3 sims/sec
- Full 8-player game: avg 1.325 sec/game (~2,717 games/hour/core)
- Determinism checks (1v1, 4v4, full game): PASS

End-to-end throughput planning should use `cloud_runner` measurements (collector + serialization + overhead). See `TFT_CLOUD_SIMULATION_PLAN.md` for the currently measured end-to-end numbers and the gate-based scale plan.

### 1.10 Storage + Scale Planning (Why Parquet Matters)

Observed (see `TFT_CLOUD_SIMULATION_PLAN.md`):

- Rows per game: ~132
- Storage per 1,000 games:
  - Parquet: ~12-15 MB
  - JSONL: ~73-75 MB

Practical implications:

- For anything beyond small iteration runs, Parquet is effectively required (install `pyarrow`).
- Gate-based progression reduces wasted compute:
  - Gate A: 1k games smoke + validator pass
  - Gate B: 50k baseline + model health
  - Gate C: 250k pre-prod + calibration
  - Gate D: 1M production

### 1.11 Known Fidelity Gaps (What To Keep In Mind)

Simulation is highly useful even if it's not perfect, but the coach must be honest about:

- Augment fidelity: 283 augments are loaded and categorized, but many specific effects/interactions are not guaranteed to match live TFT.
- PvE rounds: early PvE is simplified; it's primarily economy/item-drop plumbing.
- Ranged timing: missing or incomplete missile-speed timing data for some ranged champions impacts fine-grained accuracy.
- Some artifact items: not all artifact interactions are fully modeled (some are stats-only).

These matter most when you try to predict absolute win rates. They matter less when you use the simulator to *rank* options inside the same consistent environment (best item slam among candidates, best positioning among layouts, etc).

## 2) ML Models (Current State)

The ML code lives in `models/` and is designed to train from simulator outputs (parquet/jsonl chunks).

### 2.1 Data Loading + Anti-Leakage Splits

There are two core ways to load data:

- `models/data_loader.py`: build numpy feature matrices for XGBoost and analysis
- `models/dataset.py`: build structured tensors for the transformer (in-memory or streaming)

Key correctness rule:

- Splits must be by `game_id`, not by row, to prevent leakage across correlated samples.

The streaming dataset supports two fight label modes:

- `label_mode=current`: label is this row's `combat_result` (valid if the snapshot is pre-combat, which `collector.py` is designed to do)
- `label_mode=next_round` (**default in `models/train_transformer.py`**): label is next round's result for the same player (leak-safe temporal supervision)

### 2.2 XGBoost Baseline (What It Is)

The baseline is classical supervised learning over engineered features:

- Features: `models/feature_engineering.py` (currently 232 features)
- Trainer: `models/train_xgboost.py`
- Evaluator: `models/evaluate.py` (metrics + calibration + MI + CV)

Feature groups include:

- Composition (cost, stars, HP pool, DPS proxy, frontline/backline, carry proxy)
- Economy (level/hp/gold/streak/round/stage/interest)
- Traits (for each trait: count + active + tier)
- Items (counts, stats proxies, key item booleans)
- Augments (tier sum + encoded slots + coarse flags)
- Matchup (your-vs-opponent deltas and ratios)
- Optional personalization (personal carry/item priors if `performance_reference.json` exists)

Reference-data dependencies used by feature engineering (as implemented today):

- Champions/stats/traits: `simulator/data/combat_data.json`
- Trait definitions/breakpoints: `simulator/data/traits.json`
- Augment metadata: `data/api/processed/augments_set16.json`
- Item metadata (stats/tags/desc): `data/api/processed/items_set16.json`
- Simulator-native item aliases/stats are merged in when available (`simulator/data/set16_items.py`)
- Personal performance priors are loaded from:
  - `performance_reference.json` or `knowledge-base/performance_reference.json`
  - CSV fallback: `data/personal/carry_performance_corrected.csv`

### 2.3 Current Baseline Results (Repo Checkpoints)

The repo already contains leak-safe XGBoost checkpoints and reports:

- `models/checkpoints/baseline_run1000_v3_leaksafe/fight_training_report.json`
  - Fight accuracy: ~0.7036
  - Fight AUC: ~0.7793
- `models/checkpoints/baseline_run1000_v2_leaksafe/fight_training_report.json`
  - Fight accuracy: ~0.7131
  - Fight AUC: ~0.7869

These baselines are important because they validate "the simulator data has signal" and they set a quality bar before scaling to larger datasets.

### 2.4 Transformer: TFTTransformerV2 (What It Is)

The transformer is implemented in:

- `models/transformer.py` (TFTTransformerV2)
- `models/embeddings.py` (BoardEncoder and unit/global embeddings)
- `models/train_transformer.py` (training loop, streaming by default)

High-level structure:

- Encode each side (player + opponent) into:
  - Unit token sequence embeddings (`max_units` = 14)
  - A global context vector (traits + augments + normalized game-state scalars)
- Self-attention over each side's unit tokens
- Cross-attention: player queries attend over opponent tokens
- Pool both sequences via learned attention pooling
- Multi-task heads currently include:
  - `fight_win_prob`
  - `damage_dealt`
  - `survivors`
  - `combat_time`
  - `placement_distribution` (8-way logits)
  - `board_strength` proxy head

Training supports streaming datasets for large corpora and logs calibration metrics:

- AUC, Brier score, and Expected Calibration Error (ECE)

Transformer input schema (per batch, simplified):

- Per-side unit tokens (shape: `batch x 14 x ...`)
  - `*_champion_ids` (int ids)
  - `*_star_levels` (1-3)
  - `*_items` (3 item ids per unit)
  - `*_positions` (0-27 mapped + padding)
  - `*_costs` (1/2/3/4/5/7 cost bucket)
  - `*_mask` (valid unit slots)
- Per-side global context
  - `*_traits` (53-dim float vector)
  - `*_augments` (3 augment ids)
  - `*_game_state` (normalized scalars: level/hp/gold/streak/round/stage)

### 2.5 Uncertainty, Counterfactuals, and Trajectory Modules

Scaffolding exists to turn predictions into coach-friendly outputs:

- `models/uncertainty.py`: MC Dropout uncertainty (confidence buckets like `high_confidence` / `coin_flip`)
- `models/counterfactual.py`: simulator rollouts for "what-if" deltas with confidence intervals
- `models/trajectory.py`: Monte Carlo placement/top4 probability estimation over full-game transitions (hookable to a forward-sim engine)

These are not yet wired into the live coach runtime, but the code is present and aligned with the planned "planner + critic" approach.

## 3) How Simulation Benefits TFT Coach Right Now

This is the practical reason the simulator is so valuable: it improves coaching quality even before the ML stack is perfect.

### 3.0 What We Can Build Immediately (Even With Today's Models)

Concrete coaching features that are "simulation-native" (high leverage, low dependency on perfect ML):

- Item slam advisor:
  - Enumerate legal slams/assignments
  - Run short combat rollouts against the next opponent (or a small opponent set)
  - Return best delta + explanation
- Positioning advisor:
  - Generate a small set of layouts (templates + small perturbations)
  - Sim each layout vs the known opponent board(s)
  - Recommend the most robust layout (not just the best-case)
- Stabilize vs greed advisor:
  - Compare candidate roll/level/spend plans via short-horizon lookahead and immediate tempo sims
  - Quantify "HP risk" rather than vibes

### 3.1 Simulation Enables "Planning With A Critic" Today

The coach direction in `coach implementation.md` is:

1. Generate a small set of legal, sensible candidate actions.
2. Apply each action to get candidate next-states (deterministic executor).
3. Score each next-state using a weighted mix of:
   - Combat simulation (tempo / immediate strength)
   - Learned evaluator (board quality signal)
   - Archetype prior (what this board is trying to become)
   - Econ math (interest breakpoints, HP risk)
4. Recommend the top actions with an explanation.

The simulator is the only component that can reliably answer:

- "Does this item slam increase win probability right now?"
- "Does this positioning beat *this* opponent board?"
- "Does rolling for 1 upgrade now prevent an HP death spiral?"

You can ship item/position advice with high practical value using mostly simulation + deterministic action application.

### 3.2 Simulation Solves the Data Problem (Decision-Time Labels)

Human match history is usually:

- Sparse (few games)
- Biased (only one player's decisions, one meta, one rank band)
- Often missing intermediate decision-time context (shop rolls, bench transitions, item drops)

The simulator generates *decision-time snapshots* with clean labels at scale:

- Fight outcomes from known board states
- Placement labels at game end
- Opponent context included per round

This makes supervised training viable immediately, and it makes "what-if" analysis possible without guessing.

### 3.3 Determinism Makes Iteration Fast and Safe

Because the simulator is deterministic under fixed seeds and has a benchmark harness:

- You can change combat logic and immediately detect regressions.
- You can trust A/B comparisons between candidate actions (same random seeds).

This is critical when the coach will be making recommendations live: you need repeatable behavior, not "it depends on randomness."

### 3.4 Simulation Produces Explainable Numbers (Not Just Scores)

Coaching UI needs explanations that feel grounded:

- Win probability deltas
- Expected damage taken (HP delta)
- "This slam increases winrate vs next likely opponent from 41% -> 56%"

These are easy to compute from simulation rollouts and easy to communicate. ML-only explanations tend to be opaque unless you build a lot of interpretability tooling.

### 3.5 Simulation Helps Personalization Without Needing RL

The project has explicit personal context (AP/utility late-game carry comfort vs AD carry weakness). Simulation helps personalization in two ways:

- You can bias candidate generation and archetype priors toward lines that match the player's strengths.
- You can still validate the *tempo consequences* of those lines using the same combat engine.

That means the coach can be personalized without pretending we can learn a full optimal policy from limited human logs.

## 4) Recommended Workflows (Practical Commands)

### 4.1 Generate Data (Batch)

```bash
python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch --agent-profile mixed
python -m simulator.validate_output results/batch
# Large-output sampling mode (streaming validator, avoids loading full corpus)
python -m simulator.validate_output results/batch --sample-games 500 --sample-seed 42 --max-rows 200000
```

If you plan to scale past small runs, install `pyarrow` so you stay on Parquet rather than JSONL.

For large single-node CPU runs, prefer the rust-first path with Rayon batching and direct native parquet:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
python -m simulator.cloud_runner --engine rust_full --games 10000 --workers 1 \
  --output results/rust_full_batch --agent-profile mixed --require-parquet \
  --rust-full-native-parquet --rust-full-native-parquet-direct \
  --rust-full-rayon-batch-size 64 --rust-full-rayon-threads <PHYSICAL_CORES> \
  --parquet-compression snappy --parquet-use-dictionary --parquet-write-statistics
```

When Rayon batching is enabled, keep Python worker count low (often `1`) and tune `--rust-full-rayon-threads`/`--rust-full-rayon-batch-size` for best `summary.json` throughput.
If you need parquet layout tuning for very large datasets, you can also pass `--parquet-row-group-size <N>` and `--parquet-write-batch-size <N>` (Rust-native parquet paths).

When Rust extension APIs change, rebuild/install `tft_combat_engine` into the same CPython interpreter that runs your simulator commands:

```bash
PYTHON_EXE=$(python -c "import sys; print(sys.executable)")
python -m maturin build --release -m simulator/core/rust_engine/Cargo.toml --interpreter "$PYTHON_EXE"
python -m pip install --force-reinstall simulator/core/rust_engine/target/wheels/tft_combat_engine-*.whl
```

### 4.2 Benchmark Determinism

```bash
python -m simulator.benchmark
```

### 4.3 Train XGBoost Baselines

```bash
python -m models.train_xgboost --data results/batch --task fight --output models/checkpoints/run_fight
python -m models.train_xgboost --data results/batch --task top4 --output models/checkpoints/run_top4
```

For very large datasets, use external-memory mode:

```bash
python -m models.train_xgboost --data training_data/gate_b_50k --task fight --output models/checkpoints/gate_b_50k --external-memory
```

### 4.4 Train Transformer (Streaming Default)

```bash
python -m models.train_transformer --data results/batch --output models/checkpoints/transformer_smoke --epochs 1 --steps-per-epoch 2 --val-steps 1 --test-steps 1 --max-examples-per-split 256
```

For larger runs, keep the default `--label-mode next_round` (or set it explicitly) and use the gate-based data directories described in `TFT_CLOUD_SIMULATION_PLAN.md`.
