# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** Stop silent failures — every error path must be explicit, every fallback must be logged
**Current focus:** Phase 1: Models Exception Hardening

## Current Position

Phase: 1 of 12 (Models Exception Hardening)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-02-27 — Roadmap created, 32 requirements mapped across 12 phases

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: - min
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: none yet
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Models layer exceptions are highest priority — training on bad data is catastrophically worse than a visible error
- [Init]: Monolithic splits are last (Phases 10-12) — all exception handling must be correct before splits embed it
- [Init]: cloud_runner globals must be class-refactored (Phase 8) before cloud_runner is split (Phase 10)
- [Init]: Schema validation must run after normalization — validate after normalization, not before, to avoid rejecting valid Rust Arrow data
- [Init]: Benchmark is a hard gate after every simulator-core change — failing benchmark = stop and revert

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 8 risk: multiprocessing integration test must cover Windows spawn semantics (fork semantics do not apply on Windows)
- Phase 12 risk: _abilities_systems.py cross-method call audit required before writing the file — audit self._cast_, self.engine., and self._deal_damage() calls in the special systems section
- Phase 4 risk: pandera Arrow Table validation path behavior for Arrow Tables with schema metadata may differ from pandas DataFrames — verify with synthetic fixture before production use

## Session Continuity

Last session: 2026-02-27
Stopped at: Phase 1 context gathered — ready for /gsd:plan-phase 1
Resume file: .planning/phases/01-models-exception-hardening/01-CONTEXT.md
