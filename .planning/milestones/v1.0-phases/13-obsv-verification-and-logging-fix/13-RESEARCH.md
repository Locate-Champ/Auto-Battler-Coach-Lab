# Phase 13: OBSV Verification & Logging Regression Fix - Research

**Researched:** 2026-03-02
**Domain:** Python stdlib logging, retroactive requirement verification, OBSV gap closure
**Confidence:** HIGH

## Summary

Phase 13 addresses three orphaned OBSV requirements identified by the v1.0 milestone audit. The audit found that Phase 2 (Observable Fallbacks) was executed successfully but never formally verified -- no VERIFICATION.md was created. Additionally, Phase 10's file splits introduced 4 new sub-modules that lack `_log` loggers and contain 22 `print()` calls, partially breaking OBSV-03 compliance.

This phase has two distinct work streams: (1) retroactive verification that OBSV-01 and OBSV-02 are actually satisfied in the current code, and (2) a logging regression fix for the Phase 10 sub-modules. Research confirms that OBSV-01 (Cython fallback) and OBSV-02 (pickle fallback) ARE implemented correctly in the current code -- the gap is procedural (missing VERIFICATION.md), not implementation. OBSV-03 has an actual regression requiring code changes.

A fifth sub-module (`_cloud_runner_writer.py`) also has 5 `print()` calls and no logger, but is NOT listed in the Phase 13 success criteria. The planner should decide whether to include it for completeness or leave it strictly out of scope.

**Primary recommendation:** Create a single plan with two waves: Wave 1 verifies OBSV-01/02 by inspecting current code and produces the Phase 02 VERIFICATION.md. Wave 2 adds `_log = logging.getLogger(__name__)` to the 4 sub-modules and converts all `print()` to `_log` calls, then produces the Phase 13 verification confirming all 3 OBSV requirements are satisfied.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OBSV-01 | Cython fe_fast fallback logs at WARNING level when pure Python path activates | Verified: `models/fe_fast/__init__.py` lines 22-25 already emit `_log.warning(...)` with ~2x estimate and build hint. Retroactive verification only -- no code changes needed. |
| OBSV-02 | DataLoader pickle fallback logs at WARNING level when disk I/O path activates (~30x slower) | Verified: `models/data_loader.py` lines 109-112 already emit `_log.warning(...)` with "~30x slower" estimate. Retroactive verification only -- no code changes needed. |
| OBSV-03 | All modules use `logging.getLogger(__name__)` instead of print() or silent pass | Regression: 4 Phase 10 sub-modules lack `_log` loggers. `_cloud_runner_core.py` has 19 `print()` calls, `_cloud_runner_utils.py` has 3 `print()` calls. `_feature_engineering_transform.py` and `_feature_engineering_batch.py` lack loggers (but have 0 print calls). Code changes required. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| logging (stdlib) | Python 3.x | Module-level loggers via `getLogger(__name__)` | Project convention established in Phase 2 |

### Supporting
No additional dependencies needed. This phase uses only Python stdlib `logging`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib logging | structlog/loguru | Explicitly out of scope per REQUIREMENTS.md |

**Installation:**
No installation needed. Pure stdlib.

## Architecture Patterns

### Established Logging Convention (from Phase 2)

The project has a well-established logging pattern documented in Phase 2 decisions:

```
Every Python module (except exceptions.py and fe_fast/setup.py):
1. import logging (in stdlib import section)
2. _log = logging.getLogger(__name__) (after ALL imports, before any code)
3. Use _log.info(), _log.warning(), etc. with lazy %s formatting
4. Entry-point scripts add logging.basicConfig() in __main__ block
5. Library modules NEVER add basicConfig
```

### Files Requiring Changes

```
simulator/
  _cloud_runner_core.py    # 19 print() calls, no _log, no import logging
  _cloud_runner_utils.py   # 3 print() calls, no _log, no import logging
  _cloud_runner_writer.py  # 5 print() calls, no _log (NOT in success criteria)
models/
  _feature_engineering_transform.py  # 0 print() calls, no _log, no import logging
  _feature_engineering_batch.py      # 0 print() calls, no _log, no import logging
```

### Verification Document Pattern

Phase 02 VERIFICATION.md must be created following the format established by all other phases (01, 03-12). The existing `01-VERIFICATION.md` shows the canonical structure:
- YAML frontmatter with phase, verified date, status, score
- Observable Truths table mapping success criteria to evidence
- Required Artifacts table
- Key Link Verification
- Requirements Coverage table with SATISFIED/NOT SATISFIED per requirement
- Gaps Summary

### Print-to-Logger Mapping Pattern (from Phase 2 CONTEXT.md)

| print() Semantic | Logger Level | Notes |
|-----------------|-------------|-------|
| Progress/status prints | `_log.info()` | Game progress, seed info, completion messages |
| Disguised warnings (`print(f"Warning: ...")`) | `_log.warning()` | Reference validator warnings |
| Summary/finalization output | `_log.info()` | "Writing final results...", summary paths |
| Error context in warning | `_log.warning()` | S3 upload failures |

### Anti-Patterns to Avoid
- **f-strings in logging calls:** Use `_log.info("msg %s", var)` lazy formatting, NOT `_log.info(f"msg {var}")`
- **basicConfig in library modules:** `_cloud_runner_core.py`, `_cloud_runner_utils.py`, and `_cloud_runner_writer.py` are library modules -- NO basicConfig
- **Root logger configuration:** Never use `logging.warning()` directly, always use the module-level `_log` instance

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured logging | Custom log formatting | `logging.getLogger(__name__)` | Project convention from Phase 2 |
| Log level filtering | Custom print wrappers | stdlib logging level system | Consistent with rest of codebase |

**Key insight:** This phase is about consistency -- applying an already-proven pattern to files that were created during Phase 10 splits without inheriting the parent module's logging setup.

## Common Pitfalls

### Pitfall 1: Forgetting flush=True in progress print conversions
**What goes wrong:** `_cloud_runner_core.py` line 516 uses `print(..., flush=True)`. Logging auto-flushes by default via stream handlers, so `flush=True` should be dropped.
**Why it happens:** Mechanical copy-paste from print() to _log.info() without removing print-specific kwargs.
**How to avoid:** Strip all print-specific arguments (flush, end, sep, file) when converting.
**Warning signs:** `_log.info(..., flush=True)` would be a TypeError.

### Pitfall 2: Breaking multiprocessing worker log output
**What goes wrong:** `_cloud_runner_core.py` has `run_game()` and `_worker_init()` which execute in worker processes spawned via `multiprocessing.get_context("spawn").Pool()`. Loggers in worker processes may not inherit the parent's handler configuration.
**Why it happens:** The "spawn" context creates fresh processes without inheriting parent state.
**How to avoid:** The module-level `_log = logging.getLogger(__name__)` will still work in spawned processes -- logging module state is re-initialized from scratch. The parent process configures handlers; workers just emit to the logger hierarchy. Since `cloud_runner.py` facade already has `_log`, and the main `BatchRunner.run()` is the entry point that controls the pool, worker output routing is already handled by the caller's basicConfig.
**Warning signs:** Missing log output from worker processes during batch runs. This is acceptable because the print() calls in `run_game()` are also not visible from workers in the current code (stdout from worker processes is typically lost in pool.imap_unordered).

### Pitfall 3: Counting print() in the wrong files
**What goes wrong:** The success criteria specifically list 4 files. But `_cloud_runner_writer.py` also has 5 print() calls and no logger.
**Why it happens:** The audit specifically identified the 4 files from Phase 10 sub-module extraction, but the writer was also created in Phase 10.
**How to avoid:** The planner should explicitly decide: fix only the 4 files in success criteria, or include the writer for completeness. The writer IS mentioned in the audit's tech debt for Phase 10.
**Warning signs:** A "zero print() calls in all Phase 10 sub-modules" check would fail if the writer is excluded.

### Pitfall 4: E402 violations from _log placement
**What goes wrong:** `_log = logging.getLogger(__name__)` placed before imports causes E402 (module-level import not at top of file).
**Why it happens:** Phase 1 decision [01-01] established: "_log assignments after all module-level imports to avoid E402 violations."
**How to avoid:** Always place `_log = ...` AFTER the last import statement.

### Pitfall 5: Converting print() with string formatting to wrong log format
**What goes wrong:** `print(f"Running {remaining} games across {cfg.num_workers} workers")` gets converted to `_log.info(f"Running {remaining} games...")` -- keeping the f-string instead of lazy formatting.
**Why it happens:** Mechanical conversion that preserves f-string syntax.
**How to avoid:** Convert every f-string print to `_log.info("Running %d games across %d workers", remaining, cfg.num_workers)`.

## Code Examples

Verified patterns from the project's own established conventions:

### Adding a logger to a sub-module (from models/fe_fast/__init__.py)
```python
# Source: models/fe_fast/__init__.py (Phase 2 output)
import logging

_log = logging.getLogger(__name__)
```

### Converting print() to _log.info() (from Phase 2 pattern)
```python
# Before (current _cloud_runner_core.py line 458-461):
print(
    f"Running {remaining} games across {cfg.num_workers} workers "
    f"(chunk_size={cfg.chunk_size})"
)

# After:
_log.info(
    "Running %d games across %d workers (chunk_size=%d)",
    remaining, cfg.num_workers, cfg.chunk_size,
)
```

### Converting disguised warning (from Phase 2 pattern)
```python
# Before (current _cloud_runner_utils.py line 147):
print(f"Warning: reference validator not found at {validator} (skipping)")

# After:
_log.warning("Reference validator not found at %s (skipping)", validator)
```

### Converting progress output with flush (from Phase 2 pattern)
```python
# Before (current _cloud_runner_core.py line 513-516):
print(
    f"  [{done}/{remaining}] {rate:.1f} games/sec, "
    f"ETA: {eta:.0f}s{cpu_str}{err_str}",
    flush=True,
)

# After (flush=True dropped -- logging auto-flushes):
_log.info(
    "  [%d/%d] %.1f games/sec, ETA: %.0fs%s%s",
    done, remaining, rate, eta, cpu_str, err_str,
)
```

## Detailed Print() Inventory

### simulator/_cloud_runner_core.py (19 print() calls)

| Line | Current | Target Level | Notes |
|------|---------|-------------|-------|
| 342 | `print(f"Resuming from checkpoint: {len(completed_seeds)} games already done")` | `_log.info` | Status |
| 344 | `print("No checkpoint found, starting fresh")` | `_log.info` | Status |
| 407 | `print("All games already completed!")` | `_log.info` | Status |
| 458-461 | `print(f"Running {remaining} games...")` | `_log.info` | Run banner |
| 466 | `print(f"Seeds: {seed_span}...")` | `_log.info` | Run banner |
| 468-471 | `print(f"Shard: {cfg.shard_index + 1}/...")` | `_log.info` | Run banner |
| 473-476 | `print(f"Pool chunksize: ...")` | `_log.info` | Run banner |
| 477 | `print(f"Agents: {agent_desc}")` | `_log.info` | Run banner |
| 478 | `print(f"Engine: {cfg.engine}")` | `_log.info` | Run banner |
| 479 | `print(f"Output: {cfg.output_dir}")` | `_log.info` | Run banner |
| 481 | `print(f"S3:     {cfg.s3_uri} (streaming upload)")` | `_log.info` | Run banner |
| 482 | `print()` | `_log.info("")` or remove | Blank separator |
| 513-516 | `print(f"  [{done}/{remaining}]...", flush=True)` | `_log.info` | Progress -- drop flush |
| 548-554 | `print("Rust rayon batch mode: ...")` | `_log.info` | Config info |
| 675 | `print(f"\nRun aborted early: {aborted_reason}")` | `_log.warning` | Abort is notable |
| 676 | `print(f"Processed {done}/{remaining} tasks before stop.")` | `_log.warning` | Abort context |
| 678-681 | `print(f"\nAll {remaining} games completed...")` | `_log.info` | Completion |
| 683 | `print(f"  {writer.num_errors} games failed...")` | `_log.warning` | Errors |
| 686 | `print("Writing final results...")` | `_log.info` | Status |

### simulator/_cloud_runner_utils.py (3 print() calls)

| Line | Current | Target Level | Notes |
|------|---------|-------------|-------|
| 147 | `print(f"Warning: reference validator not found at {validator} (skipping)")` | `_log.warning` | Disguised warning |
| 157 | `print(result.stdout.strip())` | `_log.info` | Subprocess output |
| 159 | `print(result.stderr.strip())` | `_log.warning` | Subprocess stderr |

### simulator/_cloud_runner_writer.py (5 print() calls -- NOT in success criteria)

| Line | Current | Target Level | Notes |
|------|---------|-------------|-------|
| 129 | `print(f"  [WARN] S3 upload failed for {filename}: ...")` | `_log.warning` | Disguised warning |
| 131 | `print(f"  [WARN] S3 upload failed for {filename}: ...")` | `_log.warning` | Disguised warning |
| 397 | `print(f"  Errors: {error_path}...")` | `_log.info` | Summary output |
| 405 | `print(f"  Summary: {summary_path}")` | `_log.info` | Summary output |
| 414 | `print(f"  S3: All files uploaded...")` | `_log.info` | Summary output |

### models/_feature_engineering_transform.py (0 print() calls)
- Needs only: `import logging` and `_log = logging.getLogger(__name__)`

### models/_feature_engineering_batch.py (0 print() calls)
- Needs only: `import logging` and `_log = logging.getLogger(__name__)`

## OBSV-01 / OBSV-02 Verification Evidence

### OBSV-01: Cython fe_fast fallback WARNING
**Current code** (`models/fe_fast/__init__.py` lines 7-25):
```python
import logging

_log = logging.getLogger(__name__)

try:
    from .fe_fast import (
        parse_units_column_fast,
        team_summary_fast,
    )
    CYTHON_AVAILABLE = True
except (ImportError, OSError):
    team_summary_fast = None
    parse_units_column_fast = None
    CYTHON_AVAILABLE = False
    _log.warning(
        "Cython fe_fast module not available; feature extraction will use pure-Python path "
        "(~2x slower). Build with: cd models/fe_fast && python setup.py build_ext --inplace"
    )
```
**Status:** SATISFIED. WARNING-level log with ~2x performance estimate and build instructions.

### OBSV-02: DataLoader pickle fallback WARNING
**Current code** (`models/data_loader.py` lines 108-112):
```python
except (pickle.PicklingError, TypeError) as exc:
    _log.warning(
        "FeatureEngineer pickle failed (%s); falling back to ~30x slower disk-based "
        "worker init (~30ms per worker vs ~1ms). Fix: ensure FeatureEngineer is "
        "picklable, or check __getstate__/__setstate__.",
        exc,
    )
```
**Status:** SATISFIED. WARNING-level log with "~30x slower" estimate and remediation hint.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Phase 2 completed without VERIFICATION.md | All other phases have VERIFICATION.md | Identified 2026-03-02 audit | Procedural gap only |
| Phase 10 splits copied code without loggers | Sub-modules need loggers added | Phase 10 (2026-02-28) | OBSV-03 regression |

## Open Questions

1. **Should `_cloud_runner_writer.py` be included in OBSV-03 fix scope?**
   - What we know: It has 5 print() calls and no logger, same pattern as the other 4 files. It was also created in Phase 10. The audit's tech debt section mentions "cloud_runner sub-modules" (plural) having print() issues.
   - What's unclear: The success criteria explicitly list only 4 files, not the writer.
   - Recommendation: Include it. The OBSV-03 requirement says "All modules use logging.getLogger(__name__)". Leaving one sub-module with print() while fixing the others would be inconsistent. The success criteria listing 4 files is likely an oversight since the writer was also split out in Phase 10.

2. **Should the Phase 02 VERIFICATION.md be written by Phase 13, or should it be a separate task?**
   - What we know: Success criterion 4 says "Phase 02 VERIFICATION.md exists and confirms OBSV-01, OBSV-02, OBSV-03 satisfied."
   - What's unclear: Whether this should be a retroactive Phase 02 verification or a Phase 13 artifact.
   - Recommendation: Create it as `02-VERIFICATION.md` in the Phase 02 directory. The verification is retroactive but the document belongs with Phase 02's artifacts. Phase 13's verification will reference it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | `pytest.ini` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OBSV-01 | Cython fallback emits WARNING log | manual-only | `python -c "import logging; logging.basicConfig(level=logging.WARNING); import models.fe_fast"` | N/A -- verification by code inspection + import test |
| OBSV-02 | Pickle fallback emits WARNING log | manual-only | Requires FeatureEngineer that fails pickle -- impractical to automate in < 30s | N/A -- verification by code inspection |
| OBSV-03 | All modules use _log, zero print() | unit | `grep -rn "print(" simulator/_cloud_runner_core.py simulator/_cloud_runner_utils.py models/_feature_engineering_transform.py models/_feature_engineering_batch.py` returns empty | N/A -- verification by grep + ruff |

**Justification for manual-only:** OBSV-01 and OBSV-02 are about the existence of specific log statements in specific except blocks. The most reliable verification is code inspection + import test, not a test that mocks the import failure. OBSV-03 is verifiable by grep (zero print calls) and grep (all files have _log).

### Sampling Rate
- **Per task commit:** `ruff check . && ruff format --check .`
- **Per wave merge:** `python -m pytest -x -q`
- **Phase gate:** Full suite green + grep verification of zero print() calls

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. No new test files needed. Verification is by code inspection, grep, and ruff.

## Sources

### Primary (HIGH confidence)
- `models/fe_fast/__init__.py` -- direct code inspection confirms OBSV-01 implementation
- `models/data_loader.py` -- direct code inspection confirms OBSV-02 implementation
- `simulator/_cloud_runner_core.py` -- direct code inspection reveals 19 print() calls, no _log
- `simulator/_cloud_runner_utils.py` -- direct code inspection reveals 3 print() calls, no _log
- `models/_feature_engineering_transform.py` -- direct code inspection reveals no _log
- `models/_feature_engineering_batch.py` -- direct code inspection reveals no _log
- `.planning/v1.0-MILESTONE-AUDIT.md` -- audit report identifying the 3 orphaned requirements
- `.planning/phases/02-observable-fallbacks/02-01-SUMMARY.md` -- Phase 2 Plan 1 execution record
- `.planning/phases/02-observable-fallbacks/02-02-SUMMARY.md` -- Phase 2 Plan 2 execution record
- `.planning/phases/02-observable-fallbacks/02-CONTEXT.md` -- Phase 2 logging decisions

### Secondary (MEDIUM confidence)
- `.planning/phases/01-models-exception-hardening/01-VERIFICATION.md` -- verification document format reference

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - stdlib logging only, established project convention
- Architecture: HIGH - pattern is already proven across 14+ modules in Phase 2
- Pitfalls: HIGH - all pitfalls identified from actual project history and code inspection

**Research date:** 2026-03-02
**Valid until:** 2026-04-02 (stable -- no external dependencies, pattern is internal to project)
