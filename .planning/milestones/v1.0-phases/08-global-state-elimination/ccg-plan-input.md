# CCG Pre-Plan Analysis — Phase 8

Generated: 2026-02-28

## Status
- Codex (gpt-5.3-codex): SUCCESS | planner
- Gemini (gemini-3.1-pro-preview): SUCCESS | writer

## Codex Analysis (Planner)

### Implementation Approach (6 ordered tasks)
1. **Characterization tests first** — lock current `run_batch`/worker behavior before refactoring
2. **BatchRunnerConfig + BatchRunner skeleton** — frozen dataclass + class with path selection
3. **Move main-process globals to instance state** — eliminate `_RUST_FULL_SIMULATOR` and `_RUST_PARQUET_API_VALIDATED` from main process; keep worker-local globals
4. **Port run_batch() into BatchRunner.run()** — update both CLI call sites (lines 1930, 1969)
5. **Enforce explicit spawn context** — `mp.get_context('spawn')` in cloud_runner and DataLoader
6. **Integration tests for spawn semantics** — real Pool tests covering SC1-SC4

### Key Dependencies
- Task 1 before 3-4 (behavioral parity signal)
- Task 2 before 3-4 (scaffolding needed)
- Task 3 before 4 (stable worker/state contracts)
- Task 5 parallel with 3-4 (independent file)
- Task 6 after 3-5

### Technical Risks Identified
1. **Rust simulator pickling** — pass constructor args, not object
2. **12-element tuple fragility** — freeze order, add shape tests
3. **StreamingWriter integration** — checkpointing/S3 deeply coupled to batch loop
4. **Existing tests coupled to old globals** — `test_benchmark_parity_helpers.py` references `_RUST_PARQUET_API_VALIDATED`
5. **Spawn-only behavior differences** — force spawn in tests

### Files to Modify/Create
- Modify: `simulator/cloud_runner.py`, `models/data_loader.py`
- Modify: `tests/test_data_loader.py`, `tests/test_benchmark_parity_helpers.py`
- Create: `tests/test_batch_runner.py`

### Underspecified Points
- Whether CI has `tft_combat_engine` available — rust_full tests may need skip guards
- No external consumers of `run_batch` found — clean removal is safe

## Gemini Analysis (Writer)

### Requirements Gaps
1. **Missing explicit `mp.get_context('spawn')` requirement in GLBL-02** — context docs emphasize it but requirement text doesn't mandate it
2. **Missing test requirements for non-parallel paths** — rayon and sequential paths also need verification after global elimination

### Ambiguities (CRITICAL)
1. **"No module-level global mutation" contradicts worker initializer pattern** — SC#3 literally forbids what the standard Python `Pool(initializer=...)` pattern requires. Worker-process globals set by initializer are process-local, not shared mutable state.
2. **"Receive simulator by value through initargs" is impossible** — PyO3 `RustGameSimulator` cannot be pickled. Must pass construction args and build in-worker.

### Suggested Rewording
- **SC#2**: "Worker processes spawned by BatchRunner receive configuration (e.g., combat_data_path) via initargs and construct their own isolated simulator instance locally, verified on Windows where spawn is the default."
- **SC#3**: "DataLoader uses `mp.get_context('spawn').Pool(...)` with explicit initargs to construct worker state, ensuring no main-process mutable globals are referenced by workers."

### Scope Creep Risks
1. **CLI extraction** — argparse logic refactoring belongs to Phase 10, not here
2. **Task tuple refactoring** — 12-element tuple → NamedTuple belongs to Phase 10

### Acceptance Criteria Quality
- SC#1: Good — clear and actionable
- SC#2: Flawed — "by value" impossible for PyO3 objects
- SC#3: Flawed — literal reading contradicts standard multiprocessing patterns
- SC#4: Good — clearly defined

### Additional Risks
- **Windows spawn recursion** — code outside `if __name__ == '__main__':` guard will execute in child processes
- **Rayon direct-to-disk drift** — "returns raw results" context decision conflicts with `rust_full_native_parquet_direct` path that writes via StreamingWriter internally

## Claude Synthesis

### Agreements
Both models agree on:
- **Task ordering**: Config/skeleton first → global elimination → CLI update → spawn context → tests
- **Rust simulator not picklable**: Pass construction args, build in-worker
- **StreamingWriter must stay internal to BatchRunner**: The "returns raw results" decision applies to caller API, not internal orchestration
- **Worker-local globals are correct**: Only main-process globals are the target
- **12-element tuple must be frozen this phase**: Refactoring deferred to Phase 10

### Resolved Conflicts
1. **SC#2 wording**: Gemini's suggested rewording is correct — "by value" is technically impossible for PyO3. The intent is clear (workers don't inherit parent globals) but the wording should guide the planner to use construction-args-via-initargs pattern.
2. **SC#3 wording**: Gemini correctly identifies that "no module-level global mutation" is too broad. The intent is "no main-process mutable globals referenced by workers." Worker-local globals set by initializer are standard and correct.

### Actionable Insights for Planning
1. **Plan should explicitly separate main-process globals from worker-process globals** — the two global types have different treatment
2. **Characterization tests before refactoring** (Codex recommendation) — this is high-value given the 3 execution paths
3. **All 3 execution paths need post-refactor verification** (Gemini gap) — not just the parallel Pool path
4. **Existing test `test_benchmark_parity_helpers.py` references old globals** — must be updated
5. **CI availability of `tft_combat_engine`** — plan should include skip guards for Rust-dependent tests
6. **`if __name__ == '__main__':` guard is critical** — must be preserved during CLI rewrite

---
*CCG pre-plan analysis complete. Proceeding to GSD planning.*
