# CCG Post-Plan Critique — Phase 9
Generated: 2026-02-28T07:30:00Z

## Status
- Codex (gpt-5.3-codex): SUCCESS | Empirical exception testing + feasibility review
- Gemini: SKIPPED | Capacity exhausted in pre-plan phase

## Codex Analysis

### Finding 1: joblib.load() exception tuple too narrow (HIGH)
**Site:** `coach/scoring/evaluator.py:119`
**Proposed:** `except (OSError, ValueError, pickle.UnpicklingError) as e:`

Codex empirically reproduced joblib.load() with bad inputs:
| Input | Exception Type |
|-------|---------------|
| Missing file | FileNotFoundError (subclass of OSError — COVERED) |
| Non-pickle text | KeyError — MISSED |
| Empty file | EOFError — MISSED |
| Random bytes | ValueError — COVERED |
| Missing class module | ModuleNotFoundError — MISSED |
| Missing class attr | AttributeError — MISSED |

**Impact:** `default_evaluator()` at lines 215 and 229 catches `(OSError, ValueError, KeyError, RuntimeError)`. If `_load()` doesn't catch EOFError/AttributeError/ModuleNotFoundError, they leak unwrapped past the fallback chain.

**Recommendation:** Widen to `except (OSError, EOFError, ValueError, KeyError, AttributeError, ImportError, pickle.UnpicklingError) as e:` — or simplify to keep `except Exception as e:` with a `# noqa: BLE001` since this is an intentional catch-all-and-wrap pattern.

### Finding 2: fe.transform() missing AttributeError (MEDIUM)
**Site:** `coach/scoring/evaluator.py:144`
**Proposed:** `except (TypeError, ValueError, KeyError) as e:`

Codex tested: passing `None` or a `list` as `row` to `fe.transform()` raises `AttributeError` (not in the proposed tuple).

**Recommendation:** Add `AttributeError` → `except (TypeError, ValueError, KeyError, AttributeError) as e:`

### Finding 3: Import RuntimeError edge case (LOW)
**Sites:** benchmark.py:40, benchmark.py:320, game.py:264

If `tft_combat_engine` module init raises `RuntimeError` (e.g., failed C library init), `(ImportError, OSError)` won't catch it.

**Assessment:** This is a code bug, not an import failure. Letting it propagate as-is is correct — the user should see the actual RuntimeError from the C extension. No change needed. Phase 1 convention holds.

### Finding 4: Verification completeness (LOW)
Plan's verification section omits `ruff format --check .` which is required by CLAUDE.md for any Python file change. The final verification block does include it but task-level verify steps don't.

**Assessment:** Minor — the phase-level verification covers it. Executor will run CLAUDE.md checks regardless.

## Claude Synthesis

**Finding 1 is actionable.** The joblib.load() tuple should be widened. However, since all 5 sites re-raise with descriptive messages, the scope of the issue is limited to cases where the re-raise exception type doesn't match what downstream callers catch. The current plan's `RuntimeError` wrapping covers this — downstream catches `RuntimeError`. The real risk is if an exception type in the tuple causes the handler to NOT fire, letting the raw exception leak.

**Recommendation for executor:** Widen the joblib tuple to include `EOFError`, `KeyError`, `AttributeError`, and `ImportError`. This makes the tuple: `except (OSError, EOFError, ValueError, KeyError, AttributeError, ImportError, pickle.UnpicklingError) as e:`.

**Finding 2 is actionable.** Add `AttributeError` to the transform tuple.

**Findings 3 and 4 are non-actionable.** No plan changes needed.

## Confidence Assessment

| Task | Codex Rating | Claude Assessment |
|------|-------------|-------------------|
| Task 1 (simulator imports) | MEDIUM | HIGH — Phase 1 convention is proven, RuntimeError edge case is intentionally uncaught |
| Task 2 (coach evaluator) | LOW | MEDIUM — Codex found real gaps, but executor has discretion to widen tuples per CONTEXT.md |

**Overall:** Plan is sound. Executor should widen exception tuples for joblib.load() and fe.transform() based on Codex's empirical findings. No structural changes to the plan needed.

---
*Post-plan critique for Phase 9*
