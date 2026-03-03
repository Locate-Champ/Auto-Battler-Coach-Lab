# CCG Research Input Analysis — Phase 08
Generated: 2026-02-27

## Status
- Codex (gpt-5.3-codex): TIMED OUT | >5min | architect — was still reading files when killed
- Gemini (gemini-3-pro-preview): SUCCESS | ~2min | writer

## Codex Analysis
Skipped — model timed out during file exploration phase. No analysis produced.

## Gemini Analysis

### Requirements Gap Analysis
1. **Semantic gap in GLBL-02**: The requirement says "no module-level global mutation after pool creation" but the context doc prescribes worker-local globals set by initializer. Resolution: main process must be global-free; worker processes may use initializer-bound worker-local globals.
2. **DataLoader already uses initargs**: `_init_fe_worker_pickled`/`_init_fe_worker` with initargs is already in place. The actual gap is adding `mp.get_context('spawn').Pool(...)` for cross-platform consistency.
3. **Caller updates are unstated**: Removing `run_batch()` is a breaking change. Gate scripts and CLI entry points must be identified and updated.

### Project Trajectory (Phase 10 Prep)
- BatchRunner must be a pure orchestration layer decoupled from StreamingWriter
- BatchRunner.run() should yield/return simulation dicts; caller feeds into StreamingWriter
- This clear boundary makes Phase 10's file split trivial

### Ambiguities Identified
1. **Rust rayon direct-to-disk conflict**: "Returns raw results" vs `--rust-full-native-parquet-direct` which writes directly to disk. BatchRunner must orchestrate this path without breaking the paradigm — caller needs to know a chunk file was produced.
2. **"Pass simulator by value"**: RustGameSimulator (Rust extension) likely isn't picklable. "By value" probably means passing init args (combat_data_path) and constructing in the worker initializer.
3. **StreamingWriter scope**: Must stay in cloud_runner.py (Phase 10 handles extraction).

### Risk Assessment
1. **HIGH**: Windows spawn picklability — all Pool args must be picklable. Rust extension objects may not be.
2. **MEDIUM**: `_RUST_PARQUET_API_VALIDATED` module-level set must become instance state on BatchRunner.
3. **HIGH**: Removing `run_batch()` breaks all callers — need comprehensive grep for import sites.

## Claude Synthesis

### Key Takeaways for Researcher
1. **DataLoader change is minimal**: Already uses initargs. Main fix is `mp.get_context('spawn')` and removing the module-level `_worker_fe` global in favor of a cleaner worker-local pattern.
2. **cloud_runner.py is the hard problem**: Two module-level mutable globals (`_RUST_FULL_SIMULATOR`, `_RUST_PARQUET_API_VALIDATED`) plus a 500-line `run_batch()` function with 30+ parameters must become a BatchRunner class with BatchRunnerConfig dataclass.
3. **Rust picklability is the critical unknown**: Researcher must determine early whether RustGameSimulator/RustCombatEngine can be pickled. If not, the worker init pattern must pass construction args, not the object itself.
4. **Three execution paths need mapping**: rayon batch (in-process, no pool), sequential (no pool), parallel (multiprocessing.Pool). Each handles `_RUST_FULL_SIMULATOR` differently today.
5. **StreamingWriter stays composed, not inherited**: BatchRunner should receive or create a StreamingWriter but not subclass it. Phase 10 will extract it.
6. **run_batch() callers beyond CLI**: Need to search gate scripts and test files for direct `run_batch()` imports.
