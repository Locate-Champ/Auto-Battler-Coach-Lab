# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Codebase Reliability & Cleanup

**Shipped:** 2026-03-03
**Phases:** 14 | **Plans:** 22 | **Execution time:** 2.27 hours

### What Was Built
- Exception hygiene: All 39 bare/broad handlers narrowed to specific types, enforced by ruff BLE+B static rules
- Observable fallbacks: WARNING-level logging for all Cython, pickle, and DataLoader degradation paths
- Dependency pre-flight: Hard ImportError for pyarrow, actionable FileNotFoundError for combat_data.json, Rust extension architecture check
- Resource safety: DataLoader context manager with automatic pool cleanup, wired in production training code
- API hardening: FastAPI lifespan pattern with startup failure gate, Depends() injection, structured error responses
- Modular architecture: 4 monolithic files (15.3k LOC total) split into 20+ focused sub-modules via mixin composition
- Global state elimination: BatchRunner class replacing cloud_runner module globals, spawn-safe multiprocessing
- Type contracts: BoardEvaluator ABC, check_compatibility() returning bool, schema validation for both dict and Arrow paths
- Configuration: NumericFeatureConfig frozen dataclass replacing 16 magic numbers
- SklearnEvaluator: Fully wired with TFTFeatureEngineer adapter for ML-based board scoring

### What Worked
- Risk-ordered execution (silent failures first, structural splits last) meant each phase built on clean foundations
- Mixin composition pattern for file splits preserved all backward-compatible imports with zero caller changes
- Benchmark-gated commits for combat engine and abilities splits caught zero regressions — the pattern works
- Wave-based parallel execution with autonomous subagents kept orchestrator context lean (~10-15%)
- Gap-closure phases (13-14) after milestone audit caught real integration gaps that individual phase verifiers missed
- Average 6.2 min/plan execution time — fast iteration cycles

### What Was Inefficient
- Phase 02 was executed without VERIFICATION.md, requiring Phase 13 to retroactively verify OBSV requirements
- Phase 10 file splits didn't propagate `_log` loggers to new sub-modules, requiring Phase 13 to fix the regression
- Phase 01 created models/exceptions.py "for downstream use" but no downstream phase ever imported it — 26 LOC of dead code until Phase 14 removed it
- REQUIREMENTS.md checkboxes drifted from actual status (3 requirements marked Pending when actually Complete) — stale documentation accumulated across phases 5-6
- ROADMAP.md progress table was stale for phases 2-9 until Phase 14 fixed it

### Patterns Established
- `_log = logging.getLogger(__name__)` in every module — no exceptions
- Mixin composition for file splits: facade re-exports + underscore-prefixed sub-modules
- TYPE_CHECKING imports for cross-module type hints to avoid circular imports
- `mp.get_context("spawn")` for cross-platform multiprocessing consistency
- Frozen dataclass for configuration (NumericFeatureConfig, BatchRunnerConfig)
- Milestone audit before completion to catch cross-phase integration gaps

### Key Lessons
1. Phase verifiers catch within-phase issues but miss cross-phase integration gaps (e.g., Phase 10 splits breaking Phase 2's OBSV-03). Milestone audits are essential.
2. "For downstream use" code should be deleted if no downstream phase actually imports it within the milestone — speculative abstractions become dead code.
3. Documentation checkboxes must be updated atomically with implementation — stale docs accumulate faster than expected across 14 phases.
4. Structural splits (combat_engine, champion_abilities) benefit enormously from benchmark gating after every individual extraction step — confidence compounds.
5. Spawn-safe multiprocessing (explicit initargs, spawn context) should be the default on all new Pool usage — Windows and Linux 3.14+ both require it.

### Cost Observations
- Model mix: ~70% sonnet (executors, verifiers), ~30% opus (orchestration, complex splits)
- Execution time: 2.27 hours across 22 plans (avg 6.2 min/plan)
- Notable: Structural splits (Phases 11-12) averaged 12.5 min/plan vs 4.5 min/plan for non-structural work — complexity correlates linearly with plan duration

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Execution Time | Phases | Key Change |
|-----------|---------------|--------|------------|
| v1.0 | 2.27 hrs | 14 | Risk-ordered execution, milestone audit, gap-closure phases |

### Cumulative Quality

| Milestone | Plans | Avg Duration | Requirements Satisfied |
|-----------|-------|-------------|----------------------|
| v1.0 | 22 | 6.2 min | 32/32 (100%) |

### Top Lessons (Verified Across Milestones)

1. Risk-ordered execution (fix foundations before structural changes) prevents compounding technical debt
2. Cross-phase integration audits catch gaps that per-phase verification misses
