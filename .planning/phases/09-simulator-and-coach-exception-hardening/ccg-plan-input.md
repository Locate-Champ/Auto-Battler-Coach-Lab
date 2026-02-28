# CCG Pre-Plan Analysis — Phase 9
Generated: 2026-02-28T07:15:00Z

## Status
- Codex (gpt-5.3-codex): SUCCESS | Implementation approach + task decomposition
- Gemini (gemini-3-flash-preview): FAILED | 429 capacity exhausted — skipped

## Codex Analysis

### Exception Sites Found (5 active + 1 noqa)

| # | File | Line | Current | Proposed Replacement | Risk |
|---|------|------|---------|---------------------|------|
| 1 | simulator/benchmark.py | 40 | `except Exception as exc:` | `except (ImportError, OSError) as exc:` | Low — re-raises, no behavior change |
| 2 | simulator/benchmark.py | 320 | `except Exception as exc:` | `except (ImportError, OSError) as exc:` | Low — same pattern as #1 |
| 3 | simulator/game/game.py | 264 | `except Exception as exc:` | `except (ImportError, OSError) as exc:` | Medium — combat engine creation, benchmark after |
| 4 | coach/scoring/evaluator.py | 119 | `except Exception as e:` | `except (OSError, EOFError, ValueError, TypeError, pickle.UnpicklingError) as e:` | Low — re-raises as RuntimeError |
| 5 | coach/scoring/evaluator.py | 144 | `except Exception as e:` | `except (TypeError, ValueError) as e:` | Low — re-raises as ValueError |
| N/A | simulator/data/validate_reference_data.py | 37 | `except Exception as exc:  # noqa: BLE001` | Keep as-is (intentional validation catch-all) | None |

### B-Rule Violations (2)
- B007 unused-loop-control-variable (1 site) — out of scope for EXCP-03/04
- B905 zip-without-explicit-strict (1 site) — out of scope for EXCP-03/04
- Could not reproduce locally; may be resolved or config-dependent

### Decomposition Recommendation
Single plan is sufficient — only 5 handler sites across 3 files. Two task groups within:
- **Group A (simulator)**: benchmark.py (2 sites) + game.py (1 site) — benchmark after each file
- **Group B (coach)**: evaluator.py (2 sites) — pytest after

### Verification Order
1. `ruff check simulator/ coach/ --select BLE001` (zero violations)
2. `python -m simulator.benchmark` (determinism passes after game.py change)
3. Focused coach scoring pytest targets
4. `rg -n "except Exception|except BaseException|except:" simulator/ coach/` (grep guard)

### Logger Status
- `coach/scoring/evaluator.py` already has `_log`
- `simulator/benchmark.py` does not need `_log` (re-raise sites, not fallbacks)
- `simulator/game/game.py` does not need `_log` (re-raise site, not fallback)

### Key Risk
- Site #3 (game.py:264) is in the combat engine creation path — benchmark is mandatory after this change
- The `validate_reference_data.py` noqa is intentional and should be preserved

## Gemini Analysis

Skipped — model unavailable (429 capacity exhausted)

## Claude Synthesis

**Scope is small and well-defined.** 5 exception handler sites across 3 files, all following the same pattern (extension import or library call, re-raised with specific error). No bare excepts found. No intentional fallbacks requiring log-and-continue — all sites re-raise.

**Single plan recommended.** The work is small enough for one plan with two task groups (simulator first for benchmark gating, then coach).

**Codex's missed-site catch is valuable.** `simulator/game/game.py:264` was not in the original scan — would have caused BLE001 failure if missed.

**joblib exception tuple** may be overly broad — `(OSError, EOFError, ValueError, TypeError, pickle.UnpicklingError)` covers many failure modes. Consider simplifying to `(OSError, ValueError)` since joblib primarily fails on file I/O or corrupt data. Claude should evaluate at implementation time.

---
*Pre-plan enrichment for Phase 9*
