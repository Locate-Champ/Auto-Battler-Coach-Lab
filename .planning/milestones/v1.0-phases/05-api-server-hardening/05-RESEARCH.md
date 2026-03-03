# Phase 5: API Server Hardening - Research

**Researched:** 2026-02-27
**Domain:** FastAPI lifespan, dependency injection, app.state, startup failure handling
**Confidence:** HIGH

## Summary

Phase 5 migrates `app/api/server.py` from the deprecated `@app.on_event("startup")` pattern to the modern `@asynccontextmanager` lifespan pattern, enforces hard startup failure if models fail to load, replaces module-level globals (`recommender`, `placement_model`) with `app.state` attributes, and introduces `Depends()`-based dependency injection via a new `app/api/deps.py` module. The frontend in `app/frontend/` consumes the API via standard HTTP fetch calls to `/api/*` endpoints -- the migration is purely internal (no URL, request, or response shape changes).

The current server is 330 lines with two module-level globals, one `@app.on_event("startup")` handler, and six endpoints that each do `if not recommender: raise HTTPException(503)`. The lifespan migration eliminates the deprecated decorator, the globals, and all the None-guard boilerplate in endpoints. The project already requires `fastapi>=0.100.0` and `uvicorn>=0.23.0`, both of which fully support the lifespan protocol. No new runtime dependencies are needed. Testing requires adding `httpx` as a test dependency (TestClient is based on httpx and needs it installed).

**Primary recommendation:** Implement in two plans: (1) lifespan + app.state + deps.py migration with startup failure gate, (2) global exception handler + test suite using TestClient with lifespan context manager.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Startup failure behavior:** Hard exit (sys.exit(1)) immediately if any model fails to load -- server never starts accepting requests. All models required. Failure reported via structured logging (logging.CRITICAL) plus stderr. On success: INFO log. Same failure behavior in dev and production.
- **State access pattern:** FastAPI dependency injection via Depends() functions with typed return annotations. All module-level mutable globals move to app.state. Separate app/api/deps.py module with flat functions: get_evaluator(), get_feature_engineer(), etc. One dependency per resource. Dependencies trust the lifespan guarantee -- no None-checks.
- **Shutdown cleanup:** Explicit model cleanup in lifespan finally block. No external connections to worry about. INFO log on shutdown.
- **Dev reload experience:** Models reload on every uvicorn --reload cycle. Same startup/shutdown behavior in dev and production.
- **Error response format:** Structured JSON: {"error": "model_error", "detail": "...", "status": 500}. Safe details only. Standard REST status codes. Global exception handler at app level.
- **Endpoint behavior during lifespan transition:** Trust lifespan contract. No defensive None-checks. No readiness probe. Runtime model errors stay running, return 500.
- **Dependency injection organization:** Dependencies in app/api/deps.py. Flat functions, not grouped classes. No validation in deps. One function per resource.
- **Existing endpoint contracts:** Invisible migration -- same URLs, same shapes. Zero breaking changes. Existing API tests migrated to dependency_overrides. Frontend must not be affected.

### Claude's Discretion
No items marked for discretion -- all decisions locked.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GLBL-03 | FastAPI server migrated from deprecated `@app.on_event("startup")` to lifespan context manager | Lifespan pattern (Architecture Pattern 1), FastAPI >= 0.100.0 supports it, code examples verified from official docs |
| GLBL-04 | FastAPI model loading raises on startup failure (endpoints never serve None models) | Startup failure pattern (Architecture Pattern 2), uvicorn >= 0.23.0 exits non-zero on startup failure, lifespan exception-before-yield prevents server from accepting requests |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi | >=0.100.0 (already in requirements.txt) | Web framework with lifespan support | Official lifespan protocol, Depends() DI, exception handlers |
| uvicorn | >=0.23.0 (already in requirements.txt) | ASGI server | Handles lifespan protocol, exits non-zero on startup failure (PR #1278) |
| pydantic | >=2.5.0 (already in requirements.txt) | Request/response models | Already used for BoardState, Unit, etc. |

### Supporting (Test-only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.25.0 | HTTP client (TestClient dependency) | Required by `fastapi.testclient.TestClient` |
| pytest | >=7.4.3 (already in requirements.txt) | Test runner | Already in use for project tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| app.state + Depends() | Module-level dict (FastAPI docs example) | app.state is the official Starlette mechanism; module-level dict works but bypasses the framework's state management and survives reload incorrectly |
| Flat dep functions | Class-based AppState container | Class adds indirection; flat functions are simpler and match user decision |

**Installation (test dependency only):**
```bash
pip install httpx
```
No new runtime dependencies needed.

## Architecture Patterns

### Recommended File Structure
```
app/api/
  server.py        # FastAPI app creation, lifespan, CORS, exception handler, endpoints
  deps.py          # NEW: Depends() functions -- get_recommender(), get_placement_model()
```

### Pattern 1: Lifespan Context Manager with app.state
**What:** Replace `@app.on_event("startup")` with `@asynccontextmanager` lifespan that populates `app.state` and cleans up on shutdown.
**When to use:** Always -- this is the only non-deprecated approach.
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI

_log = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models at startup, clean up at shutdown."""
    _log.info("Loading models...")
    data_dir = Path(__file__).parent.parent.parent
    try:
        recommender = TFTRecommender(str(data_dir))
    except FileNotFoundError:
        _log.critical("Local runtime data missing -- cannot start server")
        sys.exit(1)

    placement_model = PlacementModel(str(data_dir))
    X, y, _ = placement_model.prepare_data()
    placement_model.train(X, y, model_type="gradient_boosting")

    # Populate app.state
    app.state.recommender = recommender
    app.state.placement_model = placement_model

    _log.info("All models loaded, server ready")
    yield
    # Shutdown cleanup
    del app.state.recommender
    del app.state.placement_model
    _log.info("Server shutdown complete, resources released")

app = FastAPI(title="Auto-Battler Coach API", version="1.0.0", lifespan=lifespan)
```

**Critical detail on startup failure:** When an exception is raised before `yield`, uvicorn logs "ERROR: Application startup failed. Exiting." and the process terminates without ever accepting requests. This satisfies GLBL-04. The `sys.exit(1)` in the user decision works -- uvicorn >= 0.23.0 properly propagates non-zero exit codes (fixed in PR #1278, merged Dec 2021). However, a bare `raise RuntimeError(...)` would also prevent startup equally well. The user explicitly chose `sys.exit(1)`, so use that.

**Important:** If `sys.exit(1)` is called, the code after yield (cleanup) does NOT run, and a `SystemExit` traceback will appear in stderr. This is acceptable per user decision (failure in dev and prod is the same). Wrapping the whole loading in try/except and calling `sys.exit(1)` in the except block is the cleanest approach -- log the CRITICAL message, then exit.

### Pattern 2: Dependency Injection via Request.app.state
**What:** Dependency functions in `deps.py` access `request.app.state` and return typed objects.
**When to use:** Every endpoint that needs a model.
**Example:**
```python
# Source: https://github.com/fastapi/fastapi/discussions/6627
# app/api/deps.py
from fastapi import Request
from src.models import PlacementModel, TFTRecommender

def get_recommender(request: Request) -> TFTRecommender:
    """Return the recommender from app.state. Trusts lifespan guarantee."""
    return request.app.state.recommender

def get_placement_model(request: Request) -> PlacementModel:
    """Return the placement model from app.state. Trusts lifespan guarantee."""
    return request.app.state.placement_model
```

**Endpoint usage:**
```python
from typing import Annotated
from fastapi import Depends

@app.get("/api/stats")
async def get_stats(recommender: Annotated[TFTRecommender, Depends(get_recommender)]):
    # No None-check needed -- lifespan guarantees it exists
    carry_stats = []
    for carry, stats in recommender.personal_carry_stats.items():
        ...
```

### Pattern 3: Global Exception Handler
**What:** Register a catch-all exception handler at app level for uniform JSON error responses.
**When to use:** Once, at app creation time.
**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/handling-errors/
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    _log.exception("Unhandled error in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": "An internal error occurred", "status": 500},
    )
```

### Pattern 4: TestClient with Lifespan Context Manager
**What:** Use `with TestClient(app) as client:` to trigger lifespan during tests.
**When to use:** All API tests.
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/testing-events/
from fastapi.testclient import TestClient

def test_root():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
```

**For tests that need to avoid loading real models, use dependency_overrides:**
```python
# Source: https://fastapi.tiangolo.com/advanced/testing-dependencies/
from unittest.mock import MagicMock

def test_stats_endpoint():
    mock_recommender = MagicMock()
    mock_recommender.personal_carry_stats = {}
    mock_recommender.personal_trait_stats = {}

    app.dependency_overrides[get_recommender] = lambda: mock_recommender
    try:
        with TestClient(app) as client:
            response = client.get("/api/stats")
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

### Anti-Patterns to Avoid
- **Module-level mutable globals:** `recommender = None` at module level survives `uvicorn --reload` incorrectly, creating stale state across reloads. Use `app.state` instead.
- **None-checks in endpoints:** `if not recommender: raise HTTPException(503)` is defensive boilerplate. The lifespan guarantees models are loaded before any endpoint is reachable. Remove all None-checks.
- **`@app.on_event("startup")`:** Deprecated. Cannot mix with lifespan -- "It's all lifespan or all events, not both."
- **Catching exceptions in lifespan then yielding anyway:** If model loading fails but you still yield, the server will start accepting requests with broken state. Never yield after a fatal error.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Application lifecycle management | Custom startup/shutdown hooks | `@asynccontextmanager` lifespan | Official pattern, integrates with uvicorn, TestClient, and the ASGI protocol |
| Dependency injection | Manual parameter passing or global dicts | `Depends()` + `request.app.state` | Framework-native, testable via `dependency_overrides`, type-safe |
| Error response formatting | Per-endpoint try/except blocks | `@app.exception_handler(Exception)` | Centralized, consistent, keeps endpoints clean |
| Test lifecycle | Manual setup/teardown | `with TestClient(app) as client:` | Triggers lifespan automatically, mirrors real server behavior |

**Key insight:** FastAPI's DI system (`Depends()`) combined with `app.state` is the framework's intended pattern for sharing startup-initialized resources. It eliminates globals, enables test isolation via `dependency_overrides`, and makes each endpoint's dependencies explicit in its signature.

## Common Pitfalls

### Pitfall 1: Mixing on_event and lifespan
**What goes wrong:** If you provide a `lifespan` parameter AND have `@app.on_event("startup")` decorators, the on_event handlers silently stop executing.
**Why it happens:** FastAPI documentation states: "If you provide a lifespan parameter, startup and shutdown event handlers will no longer be called."
**How to avoid:** Remove ALL `@app.on_event` decorators when adding lifespan. Search the entire codebase -- `app/server/websocket.py:297` also has one (different app instance, but audit anyway).
**Warning signs:** Startup tasks that "used to work" silently stop running.

### Pitfall 2: Yielding After Fatal Startup Error
**What goes wrong:** Server starts accepting requests with None/broken models.
**Why it happens:** Exception is caught in lifespan, but code still reaches `yield`.
**How to avoid:** Call `sys.exit(1)` (per user decision) or `raise` before yield. Never yield after a fatal error.
**Warning signs:** 503 responses from endpoints that used to work.

### Pitfall 3: sys.exit(1) Traceback in Logs
**What goes wrong:** `sys.exit(1)` raises `SystemExit` which produces a traceback in uvicorn's error output.
**Why it happens:** `sys.exit()` is implemented as an exception in Python.
**How to avoid:** This is expected behavior per user decision. Log the CRITICAL message with structured details BEFORE calling sys.exit(1) so the meaningful error is visible above the traceback.
**Warning signs:** Not a bug -- expected.

### Pitfall 4: TestClient Without Context Manager
**What goes wrong:** Lifespan events don't fire during tests. app.state is empty.
**Why it happens:** Only `with TestClient(app) as client:` triggers lifespan. Bare `client = TestClient(app)` followed by `client.get(...)` does not.
**How to avoid:** Always use the context manager form in tests.
**Warning signs:** `AttributeError: 'State' object has no attribute 'recommender'` in test output.

### Pitfall 5: Forgetting to Delete app.state in Shutdown
**What goes wrong:** Minor -- attributes linger but don't cause issues since the process is ending.
**Why it happens:** Oversight in the cleanup block after yield.
**How to avoid:** Explicitly `del app.state.recommender` etc. in the finally/post-yield block per user decision.
**Warning signs:** N/A -- cosmetic, but good practice.

### Pitfall 6: Stale State After Reload Without app.state
**What goes wrong:** Module-level globals persist across `uvicorn --reload` cycles because Python module cache retains them.
**Why it happens:** `uvicorn --reload` re-imports the module, but if the module is already in `sys.modules`, the globals may not reset cleanly.
**How to avoid:** Use `app.state` exclusively. The lifespan runs fresh on each reload, creating a new `app` instance with clean state.
**Warning signs:** Old model predictions after code changes during development.

## Code Examples

### Complete Lifespan Implementation
```python
# Source: Synthesized from https://fastapi.tiangolo.com/advanced/events/ + user decisions
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from src.models import PlacementModel, TFTRecommender

_log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _log.info("Loading Auto-Battler Coach models...")
    data_dir = Path(__file__).parent.parent.parent

    try:
        recommender = TFTRecommender(str(data_dir))
    except Exception:
        _log.critical("Failed to load recommender model", exc_info=True)
        sys.exit(1)

    try:
        placement_model = PlacementModel(str(data_dir))
        X, y, _ = placement_model.prepare_data()
        placement_model.train(X, y, model_type="gradient_boosting")
    except Exception:
        _log.critical("Failed to load/train placement model", exc_info=True)
        sys.exit(1)

    app.state.recommender = recommender
    app.state.placement_model = placement_model
    _log.info("All models loaded, server ready")

    yield

    del app.state.recommender
    del app.state.placement_model
    _log.info("Server shutdown complete, resources released")


app = FastAPI(title="Auto-Battler Coach API", version="1.0.0", lifespan=lifespan)
```

### Complete deps.py
```python
# Source: https://github.com/fastapi/fastapi/discussions/6627
from fastapi import Request

from src.models import PlacementModel, TFTRecommender


def get_recommender(request: Request) -> TFTRecommender:
    return request.app.state.recommender


def get_placement_model(request: Request) -> PlacementModel:
    return request.app.state.placement_model
```

### Endpoint Migration (before/after)
```python
# BEFORE (deprecated pattern with None-check):
@app.get("/api/stats")
async def get_stats():
    if not recommender:
        raise HTTPException(status_code=503, detail="Models not loaded")
    carry_stats = []
    for carry, stats in recommender.personal_carry_stats.items():
        ...

# AFTER (lifespan + Depends pattern):
from typing import Annotated
from fastapi import Depends
from app.api.deps import get_recommender

@app.get("/api/stats")
async def get_stats(recommender: Annotated[TFTRecommender, Depends(get_recommender)]):
    carry_stats = []
    for carry, stats in recommender.personal_carry_stats.items():
        ...
```

### Test With Dependency Override
```python
# Source: https://fastapi.tiangolo.com/advanced/testing-dependencies/
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.api.server import app
from app.api.deps import get_recommender

def test_stats_returns_empty_when_no_data():
    mock = MagicMock()
    mock.personal_carry_stats = {}
    mock.personal_trait_stats = {}

    app.dependency_overrides[get_recommender] = lambda: mock
    try:
        with TestClient(app) as client:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            assert resp.json()["carries"] == []
    finally:
        app.dependency_overrides.clear()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `@asynccontextmanager` lifespan | FastAPI 0.93+ (2023) | Deprecated decorator removed in favor of structured context manager |
| Module-level globals | `app.state` attributes | Always available in Starlette | Proper reload behavior, no stale state |
| None-checks in every endpoint | Lifespan guarantee + Depends() | Follows from lifespan pattern | Eliminates boilerplate, prevents serving None models |
| Per-endpoint try/except | `@app.exception_handler(Exception)` | Always available | Centralized error formatting |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Officially deprecated in FastAPI docs. Will not be called if lifespan is provided.

## Open Questions

1. **Exception specificity in lifespan try/except blocks**
   - What we know: User decided "all models required, any failure = exit". The current code catches `FileNotFoundError` specifically for the recommender.
   - What's unclear: Should we catch broad `Exception` in lifespan (per user's "any model fails" rule) or narrow exceptions? Broad `except Exception` in the lifespan startup is acceptable here because the action is always the same (log + exit) and we want to guarantee the server never starts with partial state.
   - Recommendation: Use `except Exception` with `exc_info=True` in logging. This aligns with user decision and Phase 1 patterns (broad catch is acceptable when the handler is log-and-exit, not log-and-continue).

2. **httpx test dependency**
   - What we know: `httpx` is not in requirements.txt. `TestClient` requires it.
   - What's unclear: Whether to add it to requirements.txt or a separate test requirements file.
   - Recommendation: Add `httpx>=0.25.0` to requirements.txt under the test tooling section (where `pytest` already lives).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 7.4.3 |
| Config file | pyproject.toml `[tool.pytest.ini_options]` section |
| Quick run command | `python -m pytest tests/test_api_server.py -x` |
| Full suite command | `python -m pytest` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GLBL-03 | No `@app.on_event("startup")` in codebase; lifespan used | grep + unit | `ruff check app/api/server.py && python -m pytest tests/test_api_server.py::test_lifespan_loads_models -x` | No -- Wave 0 |
| GLBL-03 | Lifespan context manager triggers startup/shutdown | integration | `python -m pytest tests/test_api_server.py::test_lifespan_startup_shutdown -x` | No -- Wave 0 |
| GLBL-04 | Server exits non-zero if model loading fails | unit | `python -m pytest tests/test_api_server.py::test_startup_failure_exits -x` | No -- Wave 0 |
| GLBL-04 | No endpoint ever serves None model | integration | `python -m pytest tests/test_api_server.py::test_endpoints_never_serve_none -x` | No -- Wave 0 |
| (impl) | app.state populated by lifespan, accessed via Depends | integration | `python -m pytest tests/test_api_server.py::test_deps_return_state -x` | No -- Wave 0 |
| (impl) | Global exception handler returns structured JSON | unit | `python -m pytest tests/test_api_server.py::test_global_exception_handler -x` | No -- Wave 0 |
| (impl) | Endpoint contracts unchanged (same URLs, same shapes) | integration | `python -m pytest tests/test_api_server.py::test_endpoint_contracts -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_api_server.py -x`
- **Per wave merge:** `python -m pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api_server.py` -- covers GLBL-03, GLBL-04, all endpoint contract verification
- [ ] `httpx>=0.25.0` added to requirements.txt -- TestClient dependency
- [ ] No conftest.py changes needed -- tests are self-contained with dependency_overrides

## Sources

### Primary (HIGH confidence)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) -- lifespan pattern, deprecation of on_event, code examples
- [FastAPI Testing Events](https://fastapi.tiangolo.com/advanced/testing-events/) -- TestClient with lifespan context manager
- [FastAPI Testing Dependencies](https://fastapi.tiangolo.com/advanced/testing-dependencies/) -- dependency_overrides pattern
- [FastAPI Error Handling](https://fastapi.tiangolo.com/tutorial/handling-errors/) -- global exception handler pattern
- [Starlette Lifespan](https://www.starlette.io/lifespan/) -- app.state, lifespan state mechanism

### Secondary (MEDIUM confidence)
- [FastAPI Discussion #6627](https://github.com/fastapi/fastapi/discussions/6627) -- accessing app.state from Depends via request.app.state
- [FastAPI Discussion #13878](https://github.com/fastapi/fastapi/discussions/13878) -- exception handling in lifespan startup, sys.exit behavior
- [Uvicorn Issue #780](https://github.com/Kludex/uvicorn/issues/780) -- exit code fix (PR #1278, merged Dec 2021)

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in requirements.txt, versions verified
- Architecture: HIGH -- patterns verified from official FastAPI and Starlette docs
- Pitfalls: HIGH -- confirmed via official docs and GitHub discussions with reproducible examples

**Research date:** 2026-02-27
**Valid until:** 2026-03-27 (stable domain -- FastAPI lifespan pattern is mature and unlikely to change)
