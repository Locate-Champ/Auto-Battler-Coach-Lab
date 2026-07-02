# Phase 4: Type Contracts and Schema Validation - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Make API contracts honest at three module boundaries: `check_compatibility()` returns a real bool (not None), `BoardEvaluator` documents its abstract contract so implementers know what to override, and `transform_batch()` validates its inputs before processing for both dict and Arrow paths. Validation runs after normalization, not before.

</domain>

<decisions>
## Implementation Decisions

### BoardEvaluator contract style
- Use Python ABC with `@abstractmethod` — enforced at instantiation time, discoverable via IDE
- Existing subclasses must continue working without changes (backward compatible)
- Claude's Discretion: whether to provide default implementations for some methods or make all abstract
- Claude's Discretion: type hint coverage on abstract methods (follow existing codebase conventions)

### Schema validation approach
- Manual column checks (set difference on column names) — no pandera dependency
- Column presence only — no dtype validation (type issues surface downstream naturally)
- This avoids the known risk with pandera Arrow Table validation differing from pandas DataFrames
- Claude's Discretion: whether to share a single schema definition across dict and Arrow paths, or keep them separate (investigate whether post-normalization shapes are identical)
- Claude's Discretion: where the schema definition lives (co-located vs separate module)

### Validation error detail level
- Collect all missing columns before raising — one error, one fix cycle
- ValueError message includes: missing columns, present columns, and full expected list
- Include which input path triggered it ("Missing columns in Arrow input" vs "Missing columns in dict input")
- Claude's Discretion: whether to include actionable fix hints (e.g., "Did you forget to run normalization first?") — follow existing error message style from Phases 1-3

### check_compatibility() edge cases
- Invalid input (None, wrong type) returns False — not an exception. "Not compatible" is the honest answer
- Add `-> bool` return type annotation to enforce the contract
- Fix all callers that don't check the return value — complete the contract end-to-end
- Claude's Discretion: whether to log at DEBUG/WARNING when returning False, following patterns from Phases 1-3

</decisions>

<specifics>
## Specific Ideas

- Error messages should follow the actionable pattern established in Phases 1-3 (pyarrow ImportError, combat_data FileNotFoundError, Rust pre-flight warnings)
- Schema validation must run after normalization, not before — this is a hard requirement from the roadmap to avoid rejecting valid Rust-generated Arrow data

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-type-contracts-and-schema-validation*
*Context gathered: 2026-02-27*
