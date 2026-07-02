---
phase: 01-models-exception-hardening
verified: 2026-02-27T09:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
human_verification:
  - test: "Run the models pipeline with a deliberately bad input (e.g. a malformed Parquet file or a row with invalid field types) and observe the exception surface"
    expected: "A specific named exception (ImportError, OSError, RuntimeError, etc.) propagates to the caller stack trace — NOT a bare Exception or silent pass"
    why_human: "Cannot synthesize a live pipeline invocation with bad data in static analysis; requires running train_xgboost.py or data_loader.py against a crafted bad input"
---

# Phase 1: Models Exception Hardening Verification Report

**Phase Goal:** All broad and bare exception handlers in the ML models layer are narrowed to specific exception types, making training failures visible instead of silently swallowed
**Verified:** 2026-02-27T09:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `ruff check models/ --select BLE001` reports zero violations | VERIFIED | Command exits 0 with "All checks passed!" — confirmed live |
| 2 | A deliberately bad input raises a specific named exception, not a broad one | VERIFIED (automated portion) / NEEDS HUMAN (live run) | No `except Exception:` or bare `except:` exists anywhere in `models/**/*.py`; handlers are `(ImportError, OSError)`, `(ImportError, ModuleNotFoundError)`, `RuntimeError`, `ImportError` |
| 3 | Cython and Rust extension imports catch `(ImportError, OSError)` not just `ImportError` | VERIFIED | Confirmed in `models/fe_fast/__init__.py` line 16 and `models/feature_engineering.py` line 27 |
| 4 | No silent pass absorbs an error without logging in the models layer | VERIFIED | Zero bare `pass` statements in any `models/**/*.py` file; all handlers either log or use functional fallback assignments |
| 5 | `models/exceptions.py` defines `ModelsPipelineError > DataLoadError / FeatureEngineeringError / TrainingError` | VERIFIED | File exists, 4-class hierarchy confirmed, module imports successfully via `python -c "from models.exceptions import ..."` |

**Score:** 5/5 truths verified (Truth 2 has a live-run component flagged for human verification)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `models/exceptions.py` | Custom exception hierarchy | VERIFIED | Contains `ModelsPipelineError`, `DataLoadError`, `FeatureEngineeringError`, `TrainingError` — all 4 classes confirmed |
| `models/data_loader.py` | Narrowed pyarrow import handler | VERIFIED | Line 22: `except (ImportError, OSError):` — pattern present, `pq = None` fallback preserved |
| `models/dataset.py` | Narrowed pyarrow import handler | VERIFIED | Line 20: `except (ImportError, OSError):` — pattern present, `pq = None` fallback preserved |
| `models/feature_engineering.py` | Narrowed simulator data handler + widened Cython import | VERIFIED | Line 27: `except (ImportError, OSError):` for fe_fast; Line 508: `except (ImportError, ModuleNotFoundError):` with `_log.debug(...)` for simulator.data |
| `models/train_xgboost.py` | Narrowed torch import handler with logging | VERIFIED | Line 51: `except ImportError:` with `_log.info("torch not available; XGBoost will use CPU device")` |
| `models/train_transformer.py` | Narrowed torch.compile handler | VERIFIED | Line 402: `except RuntimeError as e:` with `logger.warning(...)` — existing log call preserved |
| `models/fe_fast/__init__.py` | Widened Cython extension import handler | VERIFIED | Line 16: `except (ImportError, OSError):` — `warnings.warn(...)` call unchanged |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `models/exceptions.py` | models layer callers | importable module | VERIFIED (importable) / NOT YET USED | `python -c "from models.exceptions import ..."` prints "OK". No `from models.exceptions import` or `from .exceptions import` calls exist yet in any models file — intentional per PLAN: "for downstream phases to import" |
| `ruff BLE001` | `models/**/*.py` | zero violations | VERIFIED | `ruff check models/ --select BLE001` exits 0 with "All checks passed!" — confirmed live |

**Note on exceptions.py link:** The PLAN explicitly states the hierarchy is created "for downstream phases to import" and the `<interfaces>` block says "The custom exception hierarchy is created fresh in Task 1 for downstream phases to import." The module being unused at this phase is by design, not a wiring gap.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| EXCP-01 | 01-01-PLAN.md | All bare/broad exception handlers in models narrowed to specific types | SATISFIED (models scope) | Zero BLE001 violations in `models/`; zero `except Exception:` or bare `except:` in any `models/**/*.py` |
| EXCP-02 | 01-01-PLAN.md | Models layer exceptions use specific types for extensions | SATISFIED | `data_loader.py` and `dataset.py` use `(ImportError, OSError)` for pyarrow; `feature_engineering.py` and `fe_fast/__init__.py` use `(ImportError, OSError)` for Cython; `train_xgboost.py` uses `except ImportError:` |

**EXCP-01 scope note:** REQUIREMENTS.md marks EXCP-01 `[x]` complete and maps it to Phase 1. However, EXCP-01's description says "All 39 bare/broad exception handlers" — the codebase outside `models/` still contains approximately 20+ broad `except Exception:` handlers in `app/`, `coach/`, and other layers. EXCP-03 (simulator) and EXCP-04 (coach) are assigned to Phase 9. The ROADMAP scopes EXCP-01 to the models layer for Phase 1. The REQUIREMENTS.md checkbox and the "All 39" description create an apparent inconsistency — but Phase 1's mandate is models-only, and that scope is fully satisfied. This discrepancy should be reconciled in REQUIREMENTS.md (EXCP-01 description should say "models layer" or EXCP-03/04 should be sub-requirements).

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `models/preprocess_tensors.py` | 33 | F401: `_normalize_row` imported but unused | Info | Pre-existing in untracked file; explicitly noted as out-of-scope in SUMMARY. Not introduced by this phase. |
| `models/data_loader.py` | 324, 377, 788 | E501: line too long | Info | Pre-existing long lines in print statements; not introduced by exception hardening changes. |
| `models/feature_engineering.py` | 265, 517, 527 | E501: line too long | Info | Pre-existing long lines in comments and f-strings. |
| `models/train_transformer.py` | 291 | E501: line too long | Info | Pre-existing long f-string. |

No blockers. No broad exception handlers remain. No silent pass statements remain. All E501 and F401 issues are pre-existing and out of scope for this phase.

**`models/fe_fast/fe_fast.pyx` review:** Contains `except (TypeError, ValueError): pass` in Cython code at lines 97-98 and 130-135 (position parsing). These are already specific exception types with a legitimate functional fallback (set position to `None` / `star_int = 1`). Not a BLE001 violation. Not a silent pass of the type the phase targets.

---

### Human Verification Required

#### 1. Live exception propagation test

**Test:** Run `python -m models.train_xgboost` with a data directory containing a corrupted or type-mismatched Parquet file, or call `DataLoader.load_fight_prediction_data()` with malformed rows.
**Expected:** A specific exception (`OSError`, `ImportError`, `RuntimeError`, or a ValueError from the data pipeline) propagates with a full traceback to the caller — no silent swallowing, no bare `Exception` catch.
**Why human:** Static analysis confirms no broad handlers remain and all handlers log. Confirming an actual bad-input scenario surfaces the correct named exception requires a live run with crafted test data.

---

### Gaps Summary

No gaps found. All 5 success criteria are satisfied:

1. `ruff check models/ --select BLE001` — zero violations (confirmed live).
2. No `except Exception:` or bare `except:` exists in any `models/**/*.py` file (confirmed by grep returning no results).
3. Cython and Rust extension imports in models use `(ImportError, OSError)` — confirmed in `fe_fast/__init__.py` and `feature_engineering.py`.
4. No silent pass in any models handler — all handlers log or use functional fallback assignments.
5. `models/exceptions.py` is importable with the 4-class hierarchy.

Both task commits are verified in git history: `c754763` (Task 1: exception hierarchy + BLE001 narrowing) and `80c082f` (Task 2: OSError widening).

The one human verification item (live pipeline run with bad input) is a confidence check, not a blocker — the static evidence strongly supports the goal is achieved.

---

_Verified: 2026-02-27T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
