# Phase 9: Simulator and Coach Exception Hardening - Research

**Researched:** 2026-02-28
**Domain:** Python exception handler narrowing, ruff BLE001, simulator determinism
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Fallback policy**
- Case-by-case: simulator/coach paths that are intentional degradation log and continue; data/training-adjacent paths crash on unexpected errors
- Intentional fallbacks: keep and log — narrow the except clause, add `_log.warning()`, preserve the fallback behavior
- Follow Phase 1 conventions where they fit (same `(ImportError, OSError)` for extensions, `_log.warning` for fallbacks), adapt where combat-engine determinism demands it
- Trivial root-cause fixes allowed: if the fix is obvious and small, fix it inline. Complex fixes get narrowed handler + follow-up note

**Exception granularity**
- Stdlib exceptions only — no custom exception hierarchy. Use `ValueError`, `TypeError`, `RuntimeError`, `KeyError` etc.
- Tuple catch style for related exceptions: `except (ValueError, KeyError) as e:` — matches Phase 1 pattern
- Most specific possible per site: Claude reads the code, determines what exceptions are actually possible, catches exactly those
- Exception chaining: `raise X from e` when wrapping in a different type, plain `raise` when the original is already descriptive

**Combat hot-path safety**
- Mid-combat exception = crash that game, log the error, continue with next game in batch
- Extra caution for `combat_engine.py` and `champion_abilities.py`: every change individually benchmarked
- Determinism benchmark runs after each combat-related file change: "benchmark is a hard gate after every simulator-core change"

**Logging standards**
- Fallback log level: WARNING for unexpected fallbacks, INFO for expected/known-limitation fallbacks
- Log message context: enough to diagnose without a debugger, consistent with Phase 1-2 patterns
- Add `_log = logging.getLogger(__name__)` to any module getting exception work if missing
- exc_info: use `exc_info=True` at debug level, clean descriptive messages at warning level

### Claude's Discretion
- Exact exception type selection per handler site
- Whether a specific bare except is "intentional fallback" or "bug masking" — Claude evaluates based on surrounding code
- Log message wording and context detail level
- Whether a root-cause fix is "trivial enough" to include vs defer

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXCP-03 | Simulator layer exceptions narrowed with determinism-safe fallback preservation | All 3 simulator sites identified and typed; benchmark protocol documented |
| EXCP-04 | Coach layer exceptions narrowed; intentional fallbacks converted to logged `except SpecificError` + `log.warning` | Both coach evaluator sites typed; existing `_log` confirmed present; test coverage confirmed |
</phase_requirements>

---

## Summary

Phase 9 is a small, surgical change across exactly 3 files and 5 exception handler sites. All 5 sites currently use `except Exception as e/exc:` which violates ruff's BLE001 rule. The change is narrowing only — no behavioral changes, no new fallback logic, no new features. Every site re-raises (none are silent swallowers), so the narrowing is purely about naming the specific exception types that can actually occur.

The two simulator/benchmark.py sites and one simulator/game/game.py site are all identical in nature: a dynamic import of a Rust extension (`tft_combat_engine`) that can fail with `ImportError` (module not found) or `OSError` (shared library load error). The two coach/scoring/evaluator.py sites wrap library calls: `joblib.load()` for model deserialization and `fe.transform()` for feature extraction. Both re-raise with richer context messages.

The critical constraint is the determinism benchmark. The `simulator/game/game.py:264` change touches the combat engine creation path and MUST be followed immediately by `python -m simulator.benchmark` before any further changes. The benchmark.py changes are lower risk (test utility, not production path), but the same discipline applies.

**Primary recommendation:** Single-plan implementation. Group A = simulator files (benchmark.py then game.py, benchmark after game.py). Group B = coach files (evaluator.py, pytest after). Ruff BLE001 scan as final gate.

---

## Standard Stack

### Core (already in use — no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `ruff` | configured in `ruff.toml` | BLE001 + B-rule linting gate | Already the project linter; BLE + B already in `select` |
| `logging` (stdlib) | stdlib | `_log = logging.getLogger(__name__)` | Project-wide convention from Phase 1-2 |
| `joblib` | existing dep | sklearn model serialization | Already imported in evaluator.py |
| `pickle` (stdlib) | stdlib | Deserialization error type | `pickle.UnpicklingError` is the joblib-specific failure type |

### No New Dependencies
This phase introduces zero new libraries. All exception types used are stdlib or already-imported.

---

## Architecture Patterns

### Pattern 1: Extension Import Narrowing (Sites 1, 2, 3)

All three simulator sites follow the exact same structure — a `try: from tft_combat_engine import X` that catches `except Exception`. The canonical replacement pattern established in Phase 1:

```python
# Source: Phase 1 established convention; matches models/feature_engineering.py:29, simulator/cloud_runner.py:110
try:
    from tft_combat_engine import RustCombatEngine
except (ImportError, OSError) as exc:
    raise RuntimeError(
        "Rust engine requested but tft_combat_engine is unavailable. "
        "Build/install simulator/core/rust_engine via maturin first."
    ) from exc
```

**Why `(ImportError, OSError)`:**
- `ImportError` — module not found or import-time error
- `OSError` — shared library (.so/.pyd) fails to load (wrong arch, missing libc, etc.)
- These are the only two exception types that `from X import Y` can raise for a missing/broken C extension
- `ModuleNotFoundError` is a subclass of `ImportError` — covered automatically

### Pattern 2: Library Call Narrowing with Re-raise (Sites 4, 5)

The coach evaluator sites wrap external library calls that re-raise with enriched context:

```python
# Site 4 — joblib.load() in SklearnEvaluator._load()
# Source: evaluator.py:117-120 (current code); joblib failure modes
try:
    model = joblib.load(self.model_path)
except (OSError, ValueError, pickle.UnpicklingError) as e:
    raise RuntimeError(f"Failed to load sklearn model from {self.model_path}: {e}") from e
```

```python
# Site 5 — fe.transform() in SklearnEvaluator.score()
# Source: evaluator.py:142-148 (current code); TFTFeatureEngineer failure modes
try:
    features = fe.transform(row)  # type: ignore[union-attr]
except (TypeError, ValueError, KeyError) as e:
    raise ValueError(
        f"Feature extraction failed: {e}. "
        f"GameState stage={state.stage}, board_size={len(state.board)}"
    ) from e
```

**Exception type rationale for Site 4 (joblib.load):**
- `OSError` — file not found, permission denied, disk I/O error
- `ValueError` — corrupt/incompatible pickle protocol
- `pickle.UnpicklingError` — malformed pickle data (subclass of `Exception`, not `ValueError`)
- NOT `TypeError` — joblib.load() doesn't raise TypeError on a valid path argument
- NOT `EOFError` — joblib wraps truncated-file errors as pickle errors, not bare EOFError

**Exception type rationale for Site 5 (fe.transform):**
- `TypeError` — wrong input type passed to transform
- `ValueError` — shape mismatch, missing column, out-of-range value
- `KeyError` — missing feature column in the input row dict
- NOT `RuntimeError` — transform doesn't use RuntimeError

### Pattern 3: noqa Preservation (validate_reference_data.py:37)

```python
# Source: simulator/data/validate_reference_data.py:37 — keep exactly as-is
try:
    payload = _load_json(path)
except Exception as exc:  # noqa: BLE001
    problems.append(f"Failed to load {path}: {exc}")
    continue
```

This is an intentional validation catch-all: the function collects all problems rather than crashing on first error. The `# noqa: BLE001` suppression is correct and must NOT be removed.

### Anti-Patterns to Avoid

- **Adding `_log` to benchmark.py or game.py**: Neither site is a fallback; both re-raise. No `_log` needed at these sites.
- **Removing the `# noqa: BLE001` from validate_reference_data.py**: This is intentional and must stay.
- **Using `except (ImportError, OSError, Exception)`**: Defeats the purpose — pick the specific types.
- **Changing error messages**: The existing messages are clear and diagnostic. Only change the `except` line.
- **Wrapping game.py change in other changes**: Game.py change must be isolated, followed immediately by benchmark.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exception type discovery | Manual guessing | Read the library source / stdlib docs | joblib wraps pickle; pickle.UnpicklingError is the canonical type |
| Determinism verification | Manual output comparison | `python -m simulator.benchmark` | Existing determinism suite with fixed seeds — defined pass criteria |
| BLE001 compliance check | Manual code review | `ruff check simulator/ coach/ --select BLE001` | Ruff knows all BLE001 sites; grep misses noqa-suppressed ones |

---

## Common Pitfalls

### Pitfall 1: Missing `pickle.UnpicklingError` in joblib.load() catch
**What goes wrong:** Catching only `(OSError, ValueError)` for `joblib.load()` leaves `pickle.UnpicklingError` (corrupt pickle data) uncaught, triggering BLE001 if the test suite injects a bad file.
**Why it happens:** `pickle.UnpicklingError` is a `pickle`-module exception, not a stdlib builtin — easy to forget.
**How to avoid:** `import pickle` at the top of evaluator.py (or at the site) and include `pickle.UnpicklingError` in the tuple.
**Warning signs:** Test that injects a truncated model file raises `pickle.UnpicklingError` uncaught.

### Pitfall 2: Benchmark not run after game.py change
**What goes wrong:** A subtly broken Rust-engine fallback path changes game initialization semantics, causing non-deterministic results that silently poison downstream analysis.
**Why it happens:** game.py is in the active simulator path (`simulator/game/game.py`), not a test utility.
**How to avoid:** Run `python -m simulator.benchmark` immediately after saving game.py changes, before any commit or further edits.
**Warning signs:** Benchmark exits non-zero OR reports `"deterministic": false`.

### Pitfall 3: Ruff BLE001 vs B-rule confusion
**What goes wrong:** Fixing only BLE001 sites while B-rule violations (B007, B905) are also in scope according to the ruff config — or vice versa, spending time on B-rules that are out of scope for EXCP-03/04.
**Why it happens:** `ruff.toml` enables both `BLE` and `B` in `select`. The phase requirements only cover BLE001 sites.
**How to avoid:** Use `ruff check simulator/ coach/ --select BLE001` as the primary gate. B-rule violations are noted in ccg-plan-input.md as out of scope for this phase.
**Warning signs:** Spending time fixing `zip-without-explicit-strict` or `unused-loop-control-variable`.

### Pitfall 4: Forgetting `pickle` import in evaluator.py
**What goes wrong:** `pickle.UnpicklingError` referenced without `import pickle` causes a `NameError` at runtime.
**Why it happens:** `pickle` is a stdlib module not currently imported in evaluator.py.
**How to avoid:** Add `import pickle` to the imports section of `coach/scoring/evaluator.py` before using `pickle.UnpicklingError`.

---

## Code Examples

Verified patterns from source inspection:

### Site 1 + 2: benchmark.py `_create_engine()` and `_create_rust_game_simulator()`
```python
# benchmark.py:38-44 (current) → narrowed
try:
    from tft_combat_engine import RustCombatEngine
except (ImportError, OSError) as exc:      # was: except Exception as exc:
    raise RuntimeError(
        "Rust engine requested but tft_combat_engine is unavailable. "
        "Build/install simulator/core/rust_engine via maturin first."
    ) from exc

# benchmark.py:318-324 (current) → narrowed
try:
    from tft_combat_engine import RustGameSimulator
except (ImportError, OSError) as exc:      # was: except Exception as exc:
    raise RuntimeError(
        "Rust full-game engine requested but RustGameSimulator is unavailable. "
        "Build/install simulator/core/rust_engine via maturin first."
    ) from exc
```

### Site 3: game.py `_create_combat_engine()`
```python
# game.py:262-268 (current) → narrowed
try:
    from tft_combat_engine import RustCombatEngine
except (ImportError, OSError) as exc:      # was: except Exception as exc:
    raise RuntimeError(
        "Rust engine selected but tft_combat_engine is unavailable. "
        "Build/install it via maturin first."
    ) from exc
```

### Site 4: evaluator.py `_load()` — joblib.load
```python
# Requires: import pickle  (add to imports)
# evaluator.py:117-120 (current) → narrowed
try:
    model = joblib.load(self.model_path)
except (OSError, ValueError, pickle.UnpicklingError) as e:   # was: except Exception as e:
    raise RuntimeError(f"Failed to load sklearn model from {self.model_path}: {e}") from e
```

### Site 5: evaluator.py `score()` — fe.transform
```python
# evaluator.py:142-148 (current) → narrowed
try:
    features = fe.transform(row)  # type: ignore[union-attr]
except (TypeError, ValueError, KeyError) as e:               # was: except Exception as e:
    raise ValueError(
        f"Feature extraction failed: {e}. "
        f"GameState stage={state.stage}, board_size={len(state.board)}"
    ) from e
```

### Ruff Verification Commands
```bash
# Primary gate — must report zero violations
ruff check simulator/ coach/ --select BLE001

# Broader check after changes
ruff check .
ruff format --check .

# Determinism gate after game.py change
python -m simulator.benchmark

# Grep guard — should return only the noqa line
grep -rn "except Exception\|except BaseException\|except:" simulator/ coach/ \
  | grep -v "noqa"
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml / pytest.ini (existing) |
| Quick run command | `pytest tests/test_coach_evaluator.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXCP-03 | Simulator sites accept `(ImportError, OSError)` — re-raise as RuntimeError | ruff lint + benchmark | `ruff check simulator/ --select BLE001` + `python -m simulator.benchmark` | N/A (lint gate) |
| EXCP-03 | game.py Rust path determinism preserved after handler narrowing | determinism | `python -m simulator.benchmark` | N/A (existing binary) |
| EXCP-04 | `joblib.load()` failure raises RuntimeError for OSError/ValueError/UnpicklingError | unit | `pytest tests/test_coach_evaluator.py -x -k "load"` | ✅ existing |
| EXCP-04 | `fe.transform()` failure raises ValueError for TypeError/ValueError/KeyError | unit | `pytest tests/test_coach_evaluator.py -x -k "feature"` | ✅ existing |

### Sampling Rate
- **Per task commit:** `ruff check simulator/ coach/ --select BLE001` (after Group A); `pytest tests/test_coach_evaluator.py -x` (after Group B)
- **Per wave merge:** `python -m pytest`
- **Phase gate:** All of the above green + `python -m simulator.benchmark` passes

### Wave 0 Gaps

No new test files required. Existing `tests/test_coach_evaluator.py` covers SklearnEvaluator error paths. The ruff lint gate is the primary EXCP-03 verifier. The benchmark is the determinism gate.

If the existing `test_coach_evaluator.py` does not already have tests for `joblib.load()` failure (OSError) and `fe.transform()` failure (ValueError), Wave 0 should add:
- [ ] `test_sklearn_evaluator_load_oserror` — verify `(OSError, ValueError, pickle.UnpicklingError)` raises RuntimeError
- [ ] `test_sklearn_evaluator_transform_valueerror` — verify `(TypeError, ValueError, KeyError)` raises ValueError

*(Check existing test content to confirm whether these already exist before creating them.)*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `except Exception` (broad) | `except (ImportError, OSError)` for imports | Phase 1 (models layer) | BLE001 compliant; precise failure attribution |
| No ruff BLE rule enforcement | BLE + B in `ruff.toml select` | Phase 6 | Statically prevents future broad handlers |
| Silent exception swallowing | Explicit re-raise with `from e` | Phase 1+ | Exception chain preserved for debugging |

**Current state of the codebase:**
- `ruff.toml` already has `"BLE"` in `select` — BLE001 is already enforced everywhere EXCEPT the 5 active sites (which predate Phase 6 enabling)
- Phase 1 established the canonical `(ImportError, OSError)` pattern for extension imports — Phase 9 extends it to simulator/coach layers
- `coach/scoring/evaluator.py` already has `_log` defined — no logger setup needed

---

## Open Questions

1. **joblib.load() exception tuple — EOFError inclusion**
   - What we know: Codex proposed `(OSError, EOFError, ValueError, TypeError, pickle.UnpicklingError)`. Claude synthesis noted this may be too broad.
   - What's unclear: Does joblib re-wrap `EOFError` as a pickle error, or can it surface as bare `EOFError`?
   - Recommendation: Exclude `EOFError` initially. Use `(OSError, ValueError, pickle.UnpicklingError)`. If tests prove `EOFError` escapes, add it with a comment explaining why.

2. **fe.transform() — KeyError inclusion**
   - What we know: `TFTFeatureEngineer.transform()` operates on dicts; KeyError is plausible if a feature column is missing.
   - What's unclear: Does the actual implementation raise `KeyError` or convert it to `ValueError` internally?
   - Recommendation: Include `KeyError` for safety; it's a specific type and doesn't broaden the catch inappropriately.

3. **B-rule violations (B007, B905) found by Codex**
   - What we know: 2 B-rule violations exist in simulator/ or coach/ — Codex couldn't reproduce locally.
   - What's unclear: Which files/lines, and whether they're real or config-dependent.
   - Recommendation: Out of scope for EXCP-03/04. Check `ruff check simulator/ coach/ --select B` at end of phase to assess, but don't fix unless they block CI.

---

## Sources

### Primary (HIGH confidence)
- Direct source inspection of all 5 exception sites (benchmark.py:40, benchmark.py:320, game.py:264, evaluator.py:119, evaluator.py:144)
- `ruff.toml` — confirmed BLE + B already in `select`, BLE001 is the active rule
- `.planning/phases/09-simulator-and-coach-exception-hardening/ccg-plan-input.md` — Codex site-by-site analysis
- `.planning/phases/09-simulator-and-coach-exception-hardening/09-CONTEXT.md` — user decisions
- Phase 1 established conventions (visible in `models/feature_engineering.py:29`, `simulator/cloud_runner.py:110`)

### Secondary (MEDIUM confidence)
- Python stdlib documentation for `ImportError`, `OSError`, `pickle.UnpicklingError` exception hierarchy (well-established, matches training knowledge)
- joblib failure mode inference from pickle wrapping behavior (standard Python packaging pattern)

### Tertiary (LOW confidence — flagged)
- joblib `EOFError` behavior: excluded from recommendation pending code-level confirmation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; no new deps
- Architecture: HIGH — patterns verified against actual source code at all 5 sites
- Pitfalls: HIGH — derived from direct code reading (pickle import, benchmark gate, noqa preservation)
- Exception type selection: MEDIUM — stdlib types are clear; joblib internal wrapping behavior is inferred

**Research date:** 2026-02-28
**Valid until:** Stable — exception handling patterns don't change; valid indefinitely unless joblib major version changes
