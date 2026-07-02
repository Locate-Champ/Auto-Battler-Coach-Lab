# Project Research Summary

**Project:** Auto-Battler Coach Lab — Python Codebase Reliability Milestone
**Domain:** Brownfield Python 3.11+ codebase hardening (simulator, ML training pipeline, runtime API)
**Researched:** 2026-02-27
**Confidence:** HIGH

## Executive Summary

This milestone addresses 18 specific reliability concerns in an existing, production-grade codebase that spans a deterministic combat simulator (Python + Rust/PyO3 + Cython), a multi-stage ML training pipeline (XGBoost, PyTorch, pandera, PyArrow/Parquet), and a FastAPI runtime recommender. The research is grounded in direct code inspection rather than greenfield stack selection — all core technologies are already chosen and correct. The primary findings are: (1) 39 bare/broad exception handlers systematically hide real failures across all three layers; (2) silent degradation paths (Cython fallback, pickle fallback, missing pyarrow) make performance regressions invisible; (3) module-level global state in both the API server and the cloud batch runner creates non-reentrant, hard-to-test code; and (4) four monolithic files (5.9k, 5.3k, 2.1k, 2k LOC) present maintenance and determinism risk but require very careful split sequencing.

The recommended approach is layered, risk-ordered execution. Start with the highest-impact, lowest-risk changes: narrow exception handlers in the ML models layer first (training on bad data is the most dangerous failure mode), then add observable logging for all fallback paths, then add the DataLoader context manager. Only after those are stable should the team tackle global state elimination and the monolithic splits, which carry meaningful determinism and multiprocessing worker risks. The monolithic file splits are the highest-complexity work and should be the last phase, executed one sub-module at a time with a mandatory benchmark run after each structural change.

The key risk to the entire milestone is the determinism contract of `combat_engine.py`: any structural refactor that reorders method definitions or call paths can silently change the RNG sequence and produce non-reproducible simulations. A second systemic risk is the column-aliasing split between the JSONL dict path and the Rust Parquet Arrow path in feature engineering — schema validation added at the wrong layer will silently reject valid Rust-generated data. Both risks have clear mitigations (mandatory benchmark after every simulator change; validate after normalization, not before) and must be enforced as process gates, not just good intentions.

---

## Key Findings

### Recommended Stack

The existing stack (ruff, Pydantic v2, pytest, FastAPI, PyO3/Rust, Cython) is confirmed correct for this work. No major new runtime dependencies are warranted. The single most impactful configuration change is adding `"BLE", "B"` to `[lint] select` in `ruff.toml` — BLE001 catches `except Exception:` and E722 catches bare `except:`. This single ruff config change will surface all 39 known bad sites statically, making the exception-hardening phase mechanical rather than discovery-driven.

Three lightweight additions are justified for test/dev only: **pandera** (0.20+) for DataFrame/Arrow schema validation at `transform_batch()` entry points, **syrupy** (4.x) as a snapshot/golden-output test harness to lock behavior before every monolithic file split, and **rope** (1.14) for AST-safe programmatic class and function moves. None of these are runtime production dependencies.

**Core technologies:**
- ruff (0.9+, BLE+B rules added): Systematic detection of all 39 broad exception sites — the enabling tool for Phase 1
- Pydantic v2 (2.5.0+, `strict=True`): Row-level schema validation at API and evaluator boundaries — already installed
- pandera (0.20+): Column-level DataFrame/Arrow schema validation at `transform_batch()` — new dev/test dep
- syrupy (4.x): Snapshot testing to lock output before monolithic splits — new dev dep
- rope (1.14): AST-safe class/function moves during file splits — new dev dep, Python 3.11 compatible
- Python stdlib `logging`, `contextlib`: Structured fallback logging and context manager base — no new dep

### Expected Features

**Must have (table stakes) — v1, in order of risk:**
- Specific exception handling in the ML models layer (feature_engineering.py, data_loader.py, train_xgboost.py) — training on bad data is the most dangerous silent failure
- Observable fallbacks: `logging.WARNING` when Cython falls back to pure Python; `logging.WARNING` when pickle fallback activates — invisible ~5–10x and ~30x performance regressions
- Explicit dependency validation for pyarrow at DataLoader startup — missing pyarrow currently produces a silent empty iterator, training a model on zero rows
- Context manager for DataLoader (`__enter__`/`__exit__`) — prevents worker process leaks in notebooks and test runners
- Fail-fast for missing `combat_data.json` with an actionable error message — replaces internal traceback with a clear instruction
- Type-correct `check_compatibility()` return value — currently returns `None` where callers expect a boolean

**Should have (differentiators) — v1.x, after v1 validated:**
- Rust extension pre-flight check at import time — actionable rebuild hint on arch/interpreter mismatch
- Magic numbers extracted to `FeatureConfig` frozen dataclass — enables safe tuning with type safety and IDE support
- Specific exception handling in simulator and coach layers — second pass after the models layer is clean
- FastAPI lifespan model loading with startup failure gate — prevents `None` model serving; `@app.on_event("startup")` is deprecated since FastAPI 0.93

**Defer (v2+) — higher complexity, validate v1 fixes first:**
- Class-based `BatchRunner` with instance-scoped state (replaces `cloud_runner` module globals) — medium complexity, touches production batch pipeline
- Monolithic file splits: `champion_abilities.py` (5.9k LOC), `combat_engine.py` (5.3k LOC), `feature_engineering.py` (2.1k LOC), `cloud_runner.py` (2k LOC) — highest complexity, each requires determinism verification
- SklearnEvaluator feature extraction wired and tested — currently raises `NotImplementedError`; depends on schema validation and training schema alignment

**Anti-features (do not do):**
- Mass exception narrowing in a single pass without site-by-site audit — risks silently changing intentional fallback behavior
- Replace `logging` with structlog/loguru — cosmetic, not functional for this codebase
- Formal DI framework — manual constructor injection and `FastAPI.state` is the correct scope
- Add retries to all exception handlers — `ImportError` and `FileNotFoundError` are permanent failures; retries are meaningless

### Architecture Approach

Four monolithic files require splitting along natural boundaries already present in the code. The two simulator-core files (`combat_engine.py`, `champion_abilities.py`) are determinism-critical and use the **facade + re-export** pattern to preserve all external import paths without modification. The `champion_abilities.py` split uniquely requires the **mixin class** pattern because all 100+ handler methods share `self.engine` state — moving them to free functions would require pervasive argument threading. The two infrastructure files (`cloud_runner.py`, `feature_engineering.py`) are lower risk and use the **internal utility module** pattern (free functions → `_runner_utils.py`) and the **sub-module mixin** pattern (loader methods → `FeatureLoaderMixin`). All splits must maintain backward-compatible import paths; underscore-prefixed sub-modules are internal-only.

**Major components and target structure:**
1. `simulator/core/combat_engine.py` (facade, ~700 LOC) + `_combat_types.py` + `_hex_grid.py` + `_trait_manager.py` + `_augment_manager.py` + `_item_database.py` — CombatEngine class only in the main file; all types and managers in private sub-modules re-exported from the facade
2. `simulator/core/champion_abilities.py` (thin facade, ~200 LOC) + `_abilities_base.py` + `_abilities_systems.py` + `_abilities_cost1.py` through `_abilities_cost5.py` — mixin composition; `AbilitiesBase` must be extracted first before any cost-tier file
3. `simulator/cloud_runner.py` (~700 LOC) + `_runner_utils.py` (~470 LOC) + `_runner_writer.py` (~500 LOC) — free functions and `StreamingWriter` separated; module-level globals stay in `cloud_runner.py` until class-based refactor
4. `models/feature_engineering.py` (~700 LOC) + `_fe_config.py` + `_fe_loaders.py` + `_fe_transforms.py` — config constants, reference data loaders, and transform method groups separated into mixins

**Cross-file dependency order (non-negotiable):** `combat_engine.py` types must be extractable before `champion_abilities.py` split begins, because `champion_abilities.py` imports from `combat_engine.py`. The facade re-export in `combat_engine.py` means the deferred method-local imports in champion ability handlers continue to resolve correctly after the split.

### Critical Pitfalls

1. **Circular import resurrection during champion_abilities split** — `champion_abilities.py` uses 100+ deferred method-local `from .combat_engine import DamageType, HexGrid` imports specifically to avoid a circular import. Moving these to module-level in new sub-files will trigger `ImportError` at startup. Prevention: extract the shared types into `_combat_types.py` first (no circular dependency possible from there), or preserve deferred imports exactly as-is in every sub-file. Verification: `python -c "from simulator.core.champion_abilities import ChampionAbilities"` after each file creation.

2. **RNG-path drift from combat_engine structural changes** — The determinism contract depends on the exact RNG call sequence. Any reordering of method definitions or inlined helper calls during the split can silently break determinism without raising an error. Prevention: run `python -m simulator.benchmark` with a fixed seed after every logically distinct change to `combat_engine.py`, not once at phase completion. A failing benchmark is a hard stop — revert and bisect.

3. **Over-narrowing Rust/Cython extension except handlers breaks the fallback chain** — A `.so`/`.pyd` compiled for the wrong CPython version raises `OSError` (or `SystemError`), not `ImportError`. Replacing `except Exception` with `except ImportError` alone on Rust extension imports will let architecture-mismatch errors propagate uncaught and crash the process instead of falling back to Python. Prevention: use `except (ImportError, OSError)` for optional accelerators; reserve `except ImportError` alone for pure-Python optional dependencies.

4. **Global state removal breaks multiprocessing worker initialization** — On Windows (spawn start method, which is the default), each worker re-imports the module from scratch. Any globals set in the parent after spawn do not exist in workers. Moving `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED` to instance state without simultaneously updating pool `initargs` to pass the simulator by value leaves workers with `None`. Prevention: pass the simulator explicitly through `initargs`; verify with a real multiprocessing integration test (not a unit test that mocks the pool).

5. **Schema validation rejects valid Rust Parquet rows** — The JSONL dict path normalizes column aliases via `normalize_jsonish_fields()` before feature extraction; the Arrow path skips normalization for performance. Adding column name validation at the top of `transform_batch()` before normalization runs, or adding Arrow-path validation against normalized names, will silently reject all Rust-engine Parquet output. Prevention: validate after normalization in the dict path; for the Arrow path, validate against `snapshot_schema.JSONISH_COLUMNS` alias map, not against exact column names. Gate B dry-run with validation active is the only reliable end-to-end check.

---

## Implications for Roadmap

Based on the combined research, the work decomposes into four phases ordered by risk, dependency, and reversibility. The ordering principle is: fix the most dangerous silent failures first (training data correctness), then improve observability, then harden the API layer, then tackle the high-complexity structural work.

### Phase 1: Exception Hardening and Observable Fallbacks (Models Layer First)
**Rationale:** The ML training pipeline is the highest-risk layer. Silent failures here produce models trained on garbage data, which is catastrophically worse than a visible error. The models layer (feature_engineering.py, data_loader.py, train_xgboost.py) contains the pyarrow silent-empty-iterator bug and the Cython/pickle silent-fallback bugs. Fixing exception handling here first also means the files are clean before any split work touches them. ruff BLE/B rules must be enabled as the first action — this makes all remaining sites mechanical to find.
**Delivers:** All bare/broad excepts in models layer narrowed to specific types; all fallback paths observable via `logging.WARNING`; pyarrow and joblib validated at startup with actionable errors; DataLoader context manager preventing worker leaks; `check_compatibility()` returning a meaningful value.
**Addresses:** FEATURES.md v1 table stakes — dependency validation, specific exceptions, observable fallbacks, context manager, fail-fast data file errors, type-correct return values.
**Avoids:** Pitfall 3 (Rust/Cython over-narrowing — apply `(ImportError, OSError)` pattern from the start); Pitfall 5 (DataLoader `__exit__` exception masking — implement the try/except pattern in `close()`).
**Research flag:** Standard patterns — no additional phase research needed. All patterns are well-documented and confirmed with official sources.

### Phase 2: API Server Hardening and Startup Gate
**Rationale:** The FastAPI server has `@app.on_event("startup")` (deprecated since 0.93) and module-level globals that allow endpoints to serve `None` models if startup silently fails. This is a lower-risk fix than the models layer (a crashed server is visible; a wrong model is not), but it must come before the global state elimination phase because it establishes the correct `FastAPI.state` / `Depends()` pattern. The Rust extension pre-flight check and magic number extraction also belong here — both are low-cost improvements that make the system more observable before structural work begins.
**Delivers:** FastAPI server using `lifespan` context manager; model load failure raises before any endpoint becomes reachable; `app.state` replaces module globals; Rust extension pre-flight check with rebuild hint; `FeatureConfig` frozen dataclass replacing magic numbers.
**Addresses:** FEATURES.md v1.x differentiators — lifespan startup gate, Rust pre-flight, magic number extraction.
**Avoids:** Anti-pattern of leaving `@app.on_event("startup")` (will be removed in a future FastAPI version); Pitfall 3 pattern (Rust pre-flight uses `(ImportError, OSError)`).
**Research flag:** Standard patterns — FastAPI lifespan is official documented API; no deeper research needed.

### Phase 3: Global State Elimination (cloud_runner BatchRunner)
**Rationale:** This is a self-contained refactor with medium complexity and a specific multiprocessing risk. It must come after Phase 1 and 2 are validated because (a) it touches the production batch pipeline and (b) the correct pattern (constructor injection + initargs) is easier to implement confidently once the team has applied the same principle to the API server in Phase 2. The class-based design also prepares `cloud_runner.py` for the file split in Phase 4 — the globals must be eliminated before the file is split, or Pitfall 4 becomes unavoidable.
**Delivers:** `BatchRunner` class with `CloudRunnerState` dataclass replacing module-level globals; pool `initargs` passing simulator by value; integration test with real `multiprocessing.Pool`; simulator and coach layer bare-except hardening (second pass).
**Addresses:** FEATURES.md v2 differentiators — class-based runner, global state elimination.
**Avoids:** Pitfall 4 (global state + multiprocessing worker init) — this phase resolves it explicitly.
**Research flag:** Needs validation during implementation. The multiprocessing integration test must cover Windows spawn semantics specifically (the platform where fork semantics do not apply). This is non-trivial to verify without running the actual test.

### Phase 4: Monolithic File Splits
**Rationale:** The highest-complexity work, deferred until all exception handling is correct and all globals are eliminated in the files being split. The split order within this phase is fixed by the architecture research: infrastructure files first (cloud_runner, feature_engineering) because they have no determinism dependency, then simulator type extraction (combat_engine), then champion abilities (highest risk). Every step requires benchmark verification for simulator-core changes.
**Delivers:** All four monolithic files reduced to focused modules under 1k LOC each; all external import paths preserved via facade re-exports; behavior verified identical by benchmark + test suite.
**Addresses:** FEATURES.md v2 — monolithic file splits. Also unblocks SklearnEvaluator wiring (depends on clean feature_engineering structure).
**Avoids:** Pitfall 1 (circular import) — `_combat_types.py` extraction before any champion abilities work; Pitfall 2 (RNG drift) — benchmark after every simulator-core change; Pitfall 7 (Cython dispatch broken by feature_engineering split) — each sub-module declares its own conditional Cython import.
**Research flag:** This phase has the highest implementation risk and should use syrupy snapshot tests to lock behavior before each split. The champion_abilities mixin MRO and the `_abilities_systems.py` extraction (special cross-champion systems) require the most careful attention. Consider a mid-phase research checkpoint if the T-Hex/Galio/Tahm Kench cross-system interactions prove more tangled than the architecture research suggests.

### Phase Ordering Rationale

- **Models layer before API layer:** Training on bad data is worse than a visible server crash. Fixing the data pipeline first means the evaluation loop (Gate B → XGBoost train → evaluate) is reliable before any structural changes touch the files that feed it.
- **API server before global state:** The `lifespan`/`app.state` pattern in Phase 2 is a simpler instance of the same constructor-injection principle used in Phase 3 for the batch runner. Doing the simpler case first builds pattern familiarity and validates the approach before the more complex multiprocessing case.
- **Global state before file splits:** The cloud_runner globals must be eliminated (Phase 3) before the cloud_runner file is split (Phase 4), or the globals refactor and the split become a single tangled PR that is impossible to review or bisect.
- **Infrastructure splits before simulator splits:** `cloud_runner.py` and `feature_engineering.py` have no determinism dependency, so a mistake is cheap to fix. Simulator-core splits require a benchmark after every step — doing the easy work first lets the team establish split-and-verify discipline before the high-stakes `combat_engine.py` work.
- **`AbilitiesBase` before any cost-tier split:** This is a hard dependency, not a preference. Cost-tier mixin methods call `self._deal_damage()` and other helpers. If those helpers are not in `AbilitiesBase` when the first cost-tier mixin is extracted, the mixin's `self` lookup will fail with `AttributeError`.

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (Global State Elimination):** The multiprocessing integration test for Windows spawn semantics needs explicit design. The initializer function signature, pickling of the Rust simulator object, and the `initargs` tuple structure should be prototyped before the full `BatchRunner` class is committed.
- **Phase 4 (champion_abilities split, `_abilities_systems.py`):** The special cross-champion systems (Immortal, Soulbound, Ryze, T-Hex, Galio, Tahm Kench, Baron Nashor, Rift Herald) have cross-method call patterns that are not fully characterized in the architecture research. Before writing `_abilities_systems.py`, audit all method calls in these sections for any call that reaches into a cost-tier handler rather than into a base helper.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Exception Hardening):** All patterns are verified against official Python docs and ruff rules. The site-by-site audit is mechanical once ruff BLE/B rules are enabled.
- **Phase 2 (API Hardening):** FastAPI `lifespan` and `app.state` are official documented APIs. Patterns from STACK.md are directly copy-paste applicable.
- **Phase 4 (infrastructure splits — cloud_runner and feature_engineering):** Free-function extraction and mixin pattern for `FeatureLoaderMixin` are standard Python. No novel patterns required.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All core tools already in use and confirmed correct; new additions (pandera, syrupy, rope) verified against official docs; ruff BLE/B rules confirmed against ruff documentation |
| Features | HIGH | Grounded in direct codebase inspection of the 18 CONCERNS.md items; prioritization is derived from actual failure modes (silent empty training vs. maintainability), not opinion |
| Architecture | HIGH | Based on direct file inspection (5911, 5306, 2100, 2048 LOC files read); split boundaries follow existing comment structure in the code; all external import paths verified manually |
| Pitfalls | HIGH | All 7 critical pitfalls identified from actual code patterns in this repo, not from general Python advice; Pitfall 4 (Windows spawn multiprocessing) confirmed against Python 3.11+ docs |

**Overall confidence:** HIGH

### Gaps to Address

- **rope Python 3.11 support:** rope 1.14 syntax support up to Python 3.11 is confirmed by community usage but not by official rope release notes. If rope fails on any 3.11-specific syntax constructs in the codebase (match statements, Self type, etc.), fall back to manual extraction with the three-phase re-export pattern (Phase A extract + re-export, Phase B update callers, Phase C remove re-exports). The three-phase manual pattern is fully documented in STACK.md and is sufficient without rope.
- **`_abilities_systems.py` cross-method call audit:** The architecture research identifies the special systems section as high-risk but does not enumerate every cross-method call within it. Before Phase 4 Step 3.2, a targeted code audit of lines containing `self._cast_`, `self.engine.`, and `self._deal_damage()` within the special systems section is required to confirm no cost-tier handler methods are called from within a special system handler.
- **pandera Arrow Table validation path:** pandera's direct `DataFrameSchema.validate(arrow_table)` support via `pandas_engine` is documented but the exact column name behavior for Arrow Tables with schema-attached metadata may differ from pandas DataFrames. Verify with a small synthetic Arrow Table fixture before applying to the full `transform_arrow_batch()` path.
- **SklearnEvaluator schema alignment:** Phase 4 unblocks the SklearnEvaluator wiring (listed as v2+ work), but the training schema alignment — ensuring `GameState` columns match exactly what XGBoost was trained on — requires a schema contract document that does not yet exist. This is a planning gap, not a research gap: the schema must be captured from the training pipeline before the evaluator can be wired.

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `simulator/core/champion_abilities.py` (5911 LOC), `simulator/core/combat_engine.py` (5306 LOC), `models/feature_engineering.py` (2100 LOC), `simulator/cloud_runner.py` (2048 LOC), `models/data_loader.py`, `app/api/server.py`, `coach/scoring/evaluator.py`
- `.planning/codebase/CONCERNS.md` — 18-concern audit with specific file and line references (authoritative source for this milestone)
- ruff official docs — E722, BLE001, B rule families: https://docs.astral.sh/ruff/rules/
- FastAPI official docs — lifespan/app.state: https://fastapi.tiangolo.com/advanced/events/
- Pydantic v2 docs — `model_validate(strict=True)`, `Field(strict=True)`
- Python 3.11 stdlib docs — `multiprocessing.Pool` as context manager, spawn start method behavior on Windows

### Secondary (MEDIUM confidence)
- pandera docs — DataFrame/Arrow schema validation: https://pandera.readthedocs.io/ (verified with official docs; Arrow Table direct validation path needs a fixture-level validation before production use)
- rope GitHub — Move/extract refactoring for Python 3.11: https://github.com/python-rope/rope (community usage confirms 3.11 works; not in official release notes)
- FastAPI/fastapi GitHub Discussion #8968 — dependency injection without global state
- Python exception hierarchy for compiled extensions — CPython issue tracker, confirmed `OSError` on arch-mismatched `.pyd` files on Windows

### Tertiary (LOW confidence)
- syrupy snapshot testing patterns (WebSearch, multiple sources agree on current usage) — approach is sound but verify syrupy 4.x is compatible with the project's pytest 7.4.3+ version before adding to requirements-dev

---

*Research completed: 2026-02-27*
*Ready for roadmap: yes*
