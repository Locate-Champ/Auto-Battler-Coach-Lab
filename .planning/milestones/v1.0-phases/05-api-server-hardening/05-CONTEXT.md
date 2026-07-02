# Phase 5: API Server Hardening - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the FastAPI server lifecycle: migrate to the official lifespan context manager, enforce a startup failure gate so the server never serves with unloaded models, and replace all module-level globals in server.py with app.state attributes accessed via typed dependency injection. The frontend in app/frontend/ is an active API consumer — migration must be invisible to it.

</domain>

<decisions>
## Implementation Decisions

### Startup failure behavior
- Hard exit (sys.exit(1)) immediately if any model fails to load — server never starts accepting requests
- All models are required — if any model fails, the whole server exits. No partial serving with None models
- Failure reported via structured logging (logging.CRITICAL with model name and error) plus stderr
- On success: INFO log listing each model loaded and its source path ("All models loaded, server ready")
- Same failure behavior in dev and production — no relaxed dev mode

### State access pattern
- FastAPI dependency injection via Depends() functions with typed return annotations
- All module-level mutable globals in server.py move to app.state — clean slate, no stale state on reload
- Separate app/api/deps.py module with flat functions: get_evaluator(), get_feature_engineer(), etc.
- One dependency function per resource — endpoints declare exactly what they need
- Dependencies trust the lifespan guarantee — no None-checks or validation in dependency functions

### Shutdown cleanup
- Explicit model cleanup in lifespan finally block — release model objects, close any open file handles
- No external connections (DB, Redis, S3) to worry about — server only holds models in memory
- Immediate cleanup — uvicorn handles graceful request draining before lifespan cleanup runs
- INFO log on shutdown: "Server shutdown complete, resources released"

### Dev reload experience
- Models reload on every uvicorn --reload cycle — clean slate, no caching across reloads
- Default uvicorn file watch is fine — no custom exclude patterns needed
- Same startup/shutdown behavior in dev and production

### Error response format
- Structured JSON error responses: {"error": "model_error", "detail": "...", "status": 500}
- Safe details only — no stack traces, internal paths, or model filenames in responses
- Standard REST status codes: 400 bad input, 422 validation, 500 internal/model error, 503 unavailable
- Global exception handler registered at app level — endpoints stay clean, errors handled uniformly

### Endpoint behavior during lifespan transition
- Trust lifespan contract — if server is running, models are loaded. No defensive None-checks in endpoints
- Let uvicorn handle in-flight request draining during shutdown — no custom drain logic
- No readiness probe endpoint — startup gate ensures server only listens when ready
- Runtime model errors (bad input, not startup failure): stay running, return 500

### Dependency injection organization
- Dependencies live in app/api/deps.py (separate module)
- Flat functions, not grouped classes — get_evaluator(), get_feature_engineer()
- No validation in deps — trust lifespan guarantee
- One function per resource, not a bundled AppState

### Existing endpoint contracts
- Invisible migration — same URLs, same request/response shapes. Zero breaking changes
- Endpoint function signatures gain Depends() params (internal change, doesn't affect HTTP contract)
- Existing API tests migrated to use dependency_overrides pattern
- Frontend in app/frontend/ is an active consumer — must not be affected

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Key constraint: the frontend in app/frontend/ must not see any behavioral change from this migration.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-api-server-hardening*
*Context gathered: 2026-02-27*
