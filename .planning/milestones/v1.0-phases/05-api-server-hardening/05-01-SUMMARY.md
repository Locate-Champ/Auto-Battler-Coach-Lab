---
phase: 05-api-server-hardening
plan: 01
subsystem: api
tags: [fastapi, lifespan, dependency-injection, testing, httpx]

requires:
  - phase: 04-type-contracts-and-schema-validation
    provides: validated data contracts for model inputs
provides:
  - FastAPI lifespan pattern with hard startup failure gate
  - Dependency injection via Depends() for all model-using endpoints
  - Global structured JSON exception handler
  - 9-test API server test suite with full mock isolation
affects: [api-endpoints, deployment, monitoring]

tech-stack:
  added: [httpx]
  patterns: [asynccontextmanager-lifespan, depends-injection, app-state, structured-error-json]

key-files:
  created:
    - app/api/deps.py
    - tests/test_api_server.py
  modified:
    - app/api/server.py
    - app/api/__init__.py
    - requirements.txt

key-decisions:
  - "No None-checks in deps.py — trusts lifespan guarantee (sys.exit prevents partial startup)"
  - "sys.exit(1) on any model load failure — hard gate, no degraded mode"
  - "Flat dependency functions (not class) — one function per resource in deps.py"
  - "Pydantic models kept in server.py — no file move, not in scope"
  - "No readiness probe endpoint — user explicitly decided against it"

patterns-established:
  - "Lifespan pattern: @asynccontextmanager with app.state assignment before yield, cleanup after yield"
  - "Dependency injection: Annotated[Type, Depends(getter)] in endpoint signatures"
  - "Exception handler: @app.exception_handler(Exception) returning {error, detail, status} JSON"
  - "Test pattern: TestClient context manager + dependency_overrides with finally cleanup"

requirements-completed: [GLBL-03, GLBL-04]

duration: 12min
completed: 2026-02-27
---

# Phase 05: API Server Hardening — Plan 01 Summary

**FastAPI lifespan migration with sys.exit(1) startup gate, Depends() injection for all model endpoints, and 9-test coverage suite**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-27
- **Completed:** 2026-02-27
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Migrated from deprecated @app.on_event("startup") to @asynccontextmanager lifespan
- All module-level globals replaced with app.state attributes, accessed via Depends() injection
- Hard sys.exit(1) gate on any model load failure — no endpoint ever serves None models
- Global exception handler returns structured JSON {error, detail, status} for unhandled exceptions
- 9-test suite covering lifespan, startup failure, DI, endpoint contracts, exception handler, static checks

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate server.py to lifespan + app.state + deps.py** - `53afbb4` (feat)
2. **Task 2: Add httpx dependency and create test suite** - `306f7b6` (test)

## Files Created/Modified
- `app/api/server.py` - FastAPI app with lifespan, CORS, global exception handler, all endpoints using Depends()
- `app/api/deps.py` - Dependency injection functions: get_recommender(), get_placement_model()
- `app/api/__init__.py` - Package init for app.api module
- `tests/test_api_server.py` - 9 tests: lifespan, startup failure, deps, contracts, exception handler, static check
- `requirements.txt` - Added httpx>=0.25.0

## Decisions Made
- No None-checks in deps.py — lifespan guarantee + sys.exit(1) makes them unreachable
- Flat functions in deps.py, not a class — simpler for 2 resources
- Mocked sys.exit in tests because TestClient runs lifespan in background thread
- Removed pytest import after switching from pytest.raises to mock-based sys.exit testing

## Deviations from Plan

### Auto-fixed Issues

**1. [Test fix] sys.exit testing approach changed**
- **Found during:** Task 2 (test suite creation)
- **Issue:** pytest.raises(SystemExit) doesn't catch sys.exit(1) in TestClient's background lifespan thread
- **Fix:** Mock sys.exit with side_effect=SystemExit(1), assert mock_exit.assert_called_once_with(1)
- **Files modified:** tests/test_api_server.py
- **Verification:** All 9 tests pass
- **Committed in:** 306f7b6

---

**Total deviations:** 1 auto-fixed (test approach)
**Impact on plan:** Necessary for correctness — same assertion (exit code 1), different mechanism.

## Issues Encountered
- Local Python env missing project dependencies (pandas, fastapi) — installed from requirements.txt

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- API server hardened with modern FastAPI patterns
- All endpoints maintain identical URLs and request/response shapes (invisible migration)
- Test infrastructure established for further API development

---
*Phase: 05-api-server-hardening*
*Completed: 2026-02-27*
