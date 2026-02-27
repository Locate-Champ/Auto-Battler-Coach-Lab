# Requirements: Codebase Reliability & Cleanup

**Defined:** 2026-02-27
**Core Value:** Stop silent failures — every error path must be explicit, every fallback must be logged

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Exception Handling

- [ ] **EXCP-01**: All 39 bare/broad exception handlers narrowed to specific exception types (per-site audit, not mass replacement)
- [ ] **EXCP-02**: Models layer exceptions (feature_engineering.py, data_loader.py, train_xgboost.py) use `except ImportError`, `except (ImportError, OSError)` for extensions, or other specific types
- [ ] **EXCP-03**: Simulator layer exceptions narrowed with determinism-safe fallback preservation
- [ ] **EXCP-04**: Coach layer exceptions narrowed; intentional fallbacks converted to logged `except SpecificError` + `log.warning`
- [ ] **EXCP-05**: Ruff rules `BLE` and `B` enabled in ruff.toml to statically detect future broad exceptions

### Observable Fallbacks

- [ ] **OBSV-01**: Cython fe_fast fallback logs at WARNING level when pure Python path activates
- [ ] **OBSV-02**: DataLoader pickle fallback logs at WARNING level when disk I/O path activates (~30x slower)
- [ ] **OBSV-03**: All modules use `logging.getLogger(__name__)` instead of print() or silent pass

### Dependency Validation

- [ ] **DEPV-01**: Missing pyarrow raises explicit error at DataLoader startup (not silent empty iterator)
- [ ] **DEPV-02**: Missing combat_data.json raises actionable error at import time with file path and resolution steps
- [ ] **DEPV-03**: Rust extension pre-flight check validates architecture and Python interpreter match at import time

### Resource Management

- [ ] **RSMG-01**: DataLoader implements `__enter__`/`__exit__` context manager for automatic pool cleanup
- [ ] **RSMG-02**: DataLoader `__exit__` handles cleanup exceptions without masking the original exception

### Type Contracts

- [ ] **TYPE-01**: `RuntimeEvaluator.check_compatibility()` returns bool (not None)
- [ ] **TYPE-02**: `BoardEvaluator` base class documents abstract contract clearly

### Schema Validation

- [ ] **SCHM-01**: `FeatureEngineer.transform_batch()` validates required column names at entry point
- [ ] **SCHM-02**: Schema validation accounts for both JSONL/dict path and Rust Parquet Arrow path (validate after normalization)

### Global State Elimination

- [ ] **GLBL-01**: cloud_runner.py module-level globals refactored to class-based BatchRunner with instance state
- [ ] **GLBL-02**: DataLoader worker state uses pool context manager with explicit initargs (not module-level global mutation)
- [ ] **GLBL-03**: FastAPI server migrated from deprecated `@app.on_event("startup")` to lifespan context manager
- [ ] **GLBL-04**: FastAPI model loading raises on startup failure (endpoints never serve None models)

### Configuration

- [ ] **CONF-01**: Magic numbers in feature_engineering.py extracted to frozen FeatureConfig dataclass with documented rationale
- [ ] **CONF-02**: Constants are importable and overridable for testing

### SklearnEvaluator

- [ ] **SKLR-01**: SklearnEvaluator feature extraction implemented (matches training schema from train_xgboost.py)
- [ ] **SKLR-02**: SklearnEvaluator integration tested with mock sklearn model

### Monolithic File Splits

- [ ] **SPLT-01**: `feature_engineering.py` (2.1k LOC) split into config, loaders, and transform sub-modules
- [ ] **SPLT-02**: `cloud_runner.py` (2k LOC) split into runner core, utilities, and writer sub-modules
- [ ] **SPLT-03**: `combat_engine.py` (5.3k LOC) split into facade + types, hex grid, trait manager, augment manager, item database sub-modules
- [ ] **SPLT-04**: `champion_abilities.py` (5.9k LOC) split into AbilitiesBase + systems + cost-tier mixin sub-modules
- [ ] **SPLT-05**: All splits maintain backward-compatible imports via facade re-exports
- [ ] **SPLT-06**: Determinism benchmark passes after each individual combat_engine/champion_abilities split step

### Cross-Engine Benchmark

- [ ] **BNCH-01**: Cross-engine parity tests batched for reduced CI overhead

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Extensibility

- **EXTD-01**: Champion ability handler registry for plugin-style dispatch (beyond the structural split)

## Out of Scope

| Feature | Reason |
|---------|--------|
| New gameplay mechanics or features | This is cleanup only — no behavioral changes |
| Third-party logging library (structlog/loguru) | Stdlib logging is sufficient; adds unnecessary dependency |
| Formal DI framework | Manual constructor injection solves the problem without new deps |
| Retry logic on permanent failures | ImportError/FileNotFoundError don't benefit from retries |
| Pydantic models for all internal structures | Over-validation; pandera at entry points is sufficient |
| SklearnEvaluator as ML inference service | Scope is wiring the existing pipeline, not building a service |
| Mobile or alternative frontends | Not relevant to reliability work |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXCP-01 | — | Pending |
| EXCP-02 | — | Pending |
| EXCP-03 | — | Pending |
| EXCP-04 | — | Pending |
| EXCP-05 | — | Pending |
| OBSV-01 | — | Pending |
| OBSV-02 | — | Pending |
| OBSV-03 | — | Pending |
| DEPV-01 | — | Pending |
| DEPV-02 | — | Pending |
| DEPV-03 | — | Pending |
| RSMG-01 | — | Pending |
| RSMG-02 | — | Pending |
| TYPE-01 | — | Pending |
| TYPE-02 | — | Pending |
| SCHM-01 | — | Pending |
| SCHM-02 | — | Pending |
| GLBL-01 | — | Pending |
| GLBL-02 | — | Pending |
| GLBL-03 | — | Pending |
| GLBL-04 | — | Pending |
| CONF-01 | — | Pending |
| CONF-02 | — | Pending |
| SKLR-01 | — | Pending |
| SKLR-02 | — | Pending |
| SPLT-01 | — | Pending |
| SPLT-02 | — | Pending |
| SPLT-03 | — | Pending |
| SPLT-04 | — | Pending |
| SPLT-05 | — | Pending |
| SPLT-06 | — | Pending |
| BNCH-01 | — | Pending |

**Coverage:**
- v1 requirements: 32 total
- Mapped to phases: 0
- Unmapped: 32 (pending roadmap creation)

---
*Requirements defined: 2026-02-27*
*Last updated: 2026-02-27 after initial definition*
