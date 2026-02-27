# Phase 6: Configuration Extraction and Ruff Gates - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract magic numeric constants from feature_engineering.py into a typed frozen FeatureConfig dataclass. Enable ruff BLE and B rule groups so broad exception handlers are caught statically. Legacy/quarantined paths are excluded from ruff enforcement.

</domain>

<decisions>
## Implementation Decisions

### Config structure
- Single flat frozen dataclass (not nested sub-configs)
- Lives in a dedicated config module (e.g., src/models/feature_config.py), not inline in feature_engineering.py
- All fields have default values matching the current magic numbers
- Per-field inline comments explaining the rationale for each default value

### Constant scope
- Only feature_engineering.py — no other files in scope
- Numeric constants only — no string or list constants
- Domain-meaningful magic numbers only — skip trivial values like 0, 1, 100 used for basic arithmetic
- Rename to consistent descriptive snake_case field names on the dataclass (may differ from original inline variable names)

### Ruff exception policy
- Enable BLE and B rule groups only — no additional rule groups (UP, SIM, etc.)
- Refactor all existing broad exception handlers to specific exception types — no noqa suppressions
- Exclude legacy/quarantined paths (simulator/Simulator/**, simulator/Concurrency/**, simulator/Evaluator/**) from ruff enforcement
- Rely on existing pre-commit hooks for enforcement — no new CI step needed

### Config override pattern
- Module-level DEFAULT_CONFIG = FeatureConfig() instance for production code to import directly
- Tests use dataclasses.replace(DEFAULT_CONFIG, field=new_value) for overrides
- Purely code-defined — no environment variable overrides
- Export only FeatureConfig class and DEFAULT_CONFIG — no re-exported individual constants

### Claude's Discretion
- Exact field names chosen based on what each constant represents in context
- Whether to add type annotations beyond basic int/float (e.g., NewType for domain clarity)
- Organization of ruff.toml changes (extend existing select vs replace)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. The success criteria from the roadmap are well-defined:
1. All magic numeric constants replaced by named fields on frozen FeatureConfig
2. FeatureConfig importable and instantiable in tests with overridden values
3. ruff.toml includes BLE, B in select list and ruff check . passes zero violations
4. A deliberately introduced except Exception: causes ruff check failure

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-configuration-extraction-and-ruff-gates*
*Context gathered: 2026-02-27*
