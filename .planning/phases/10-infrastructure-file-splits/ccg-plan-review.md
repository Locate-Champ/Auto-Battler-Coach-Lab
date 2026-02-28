# CCG Plan Post-Analysis — Phase 10
Generated: 2026-02-28

## Status
- Codex (codex-spark-5.3-medium-reasoning): SUCCESS | Technical feasibility reviewer
- Gemini (gemini-3-flash-preview): SUCCESS | Completeness reviewer

## Codex Analysis

**Confidence:** MEDIUM for both plans

### Findings (by severity)

1. **HIGH — Re-export completeness**: Facade re-export lists must include ALL private/tested symbols. Tests depend on `_build_cost_telemetry`, `_extract_signature_parameter_names`, `_ensure_rust_parquet_method_support`, `inspect`, `_worker_sim`, `_worker_parquet_validated`.
   - **Claude verdict:** ALREADY ADDRESSED — Plan 10-01 Task 2 action explicitly lists all these re-exports including `import inspect` at facade level.

2. **HIGH — CLI ownership**: `main()` placement in facade must be explicit to avoid LOC overrun.
   - **Claude verdict:** ALREADY ADDRESSED — Plan 10-01 Task 2 explicitly keeps `main()`, `_parse_agent_mix`, `_cli_flag_present` in facade (~590 LOC estimate).

3. **MEDIUM — Lifecycle method placement**: `__init__`, `__getstate__`, `__setstate__` must stay in facade class.
   - **Claude verdict:** ALREADY ADDRESSED — Plan 10-02 Task 2 explicitly states these stay in the facade TFTFeatureEngineer class.

4. **MEDIUM — Cython wiring across transform/batch split**: `_CYTHON_FE`/`_cy_*` imports in `_transform.py` but `_parse_units_column` in `_batch.py`. If batch uses `_cy_parse_units_column`, it needs its own Cython import.
   - **Claude verdict:** VALID CONCERN — needs attention during execution.

5. **MEDIUM — Additional CI/test files need updates**: `tests/test_track_boundaries.py:96` lists `simulator/cloud_runner.py` as active path. New sub-modules should be added. `scripts/verify.ps1:127` also references `cloud_runner.py`.
   - **Claude verdict:** VALID CONCERN — `test_track_boundaries.py` needs the 3 new sub-modules added to active_files list.

6. **LOW — Mutable global re-export stale binding**: `_worker_sim` and `_worker_parquet_validated` are mutated via `global` keyword in `run_game` and `_worker_init`. Re-exporting via `from _core import _worker_sim` creates a stale binding in the facade (the facade's name won't update when the core module mutates).
   - **Claude verdict:** LOW RISK — tests only check `hasattr(cloud_runner, '_worker_sim')`, not the value. Worker globals are process-local and only used inside worker processes via `_cloud_runner_core` directly.

7. **LOW — sys.path bootstrap**: `cloud_runner.py:36-38` has a sys.path hack for `snapshot_schema`. This must stay in facade or be moved to a module that runs at import time.
   - **Claude verdict:** ALREADY ADDRESSED — Plan 10-01 Task 2 keeps facade as the import entry point, so sys.path manipulation naturally stays there.

8. **LOW — ruff.toml per-file-ignores**: `ruff.toml:28` has `"simulator/cloud_runner.py" = ["E402"]`. After split, if sub-modules have E402 issues, they'd need similar entries.
   - **Claude verdict:** Minor — executor should check if new sub-modules trigger E402 and add entries if needed.

### LOC Estimates Assessment
- Plan 10-01: Realistic. Writer/core/utils all under 1k. Facade ~590 LOC with CLI.
- Plan 10-02: Realistic but tight. Transform module likely ~850-900 LOC (not ~750). Still under 1k.

## Gemini Analysis

### Findings

1. **Gap in Final Verification**: Neither plan includes a final `python -m pytest` step. Plans only run targeted tests. SC4 requires "full test suite passes."
   - **Claude verdict:** VALID — the plans' `<verification>` sections run targeted tests but the GSD executor should run full pytest as part of phase verification. This is handled by the standard GSD verification step, not the plan itself.

2. **Cython fast-path in batch module**: `_parse_units_column` moved to `_feature_engineering_batch.py` uses Cython fast-path when available. The Cython try/except is only in `_transform.py` per the plan. Batch module would silently fall back to pure Python.
   - **Claude verdict:** VALID CONCERN — agrees with Codex finding #4. Both Codex and Gemini independently flagged this.

3. **test_track_boundaries.py update needed**: File explicitly lists `simulator/cloud_runner.py` for legacy import checks. New `_cloud_runner_*.py` files should be added to active_files list.
   - **Claude verdict:** VALID — agrees with Codex finding #5. Both models independently flagged this.

4. **Cython import strategy**: Recommends importing from `models.fe_fast` in both transform and batch sub-modules to avoid duplication.
   - **Claude verdict:** Reasonable approach. Executor should place the Cython try/except in both modules that need it, or factor it into the config module.

### Overall Assessment
Plans are clear, well-structured, and provide good guidance for autonomous execution. Adjustments needed are minor.

## Claude Synthesis

### Confidence Rating
- **Plan 10-01 (cloud_runner split):** HIGH — All major concerns were already addressed in the plan. Minor additions needed for test_track_boundaries.py and ruff.toml.
- **Plan 10-02 (feature_engineering split):** HIGH with one caveat — Cython import placement needs explicit handling in `_batch.py` module. All other concerns already addressed.

### Actionable Items for Executor (3 items)

1. **Cython imports in batch module** (MEDIUM): When creating `models/_feature_engineering_batch.py`, include the same Cython try/except block as in `_transform.py` if `_parse_units_column` uses `_cy_parse_units_column`. Alternatively, place Cython imports in `_config.py` and import from there.

2. **test_track_boundaries.py** (LOW): Add the 3 new `simulator/_cloud_runner_*.py` files to the `active_files` list in `test_active_simulator_paths_do_not_import_legacy_packages()` at line 96. This is a minor addition that prevents CI false negatives.

3. **ruff.toml E402 check** (LOW): After split, verify if new sub-modules trigger E402 (import-not-at-top). If so, add per-file-ignores entries matching the existing `cloud_runner.py` pattern.

### Issues That Do NOT Need Action
- CLI ownership: already explicit in plan
- Re-export completeness: already comprehensive in plan
- Lifecycle method placement: already specified in plan
- sys.path bootstrap: naturally stays in facade
- Mutable global re-export: low risk, tests only check hasattr
- Full pytest: handled by GSD phase verification, not individual plan steps

### Overall Verdict
Plans are **ready for execution**. The Cython import placement is the only substantive finding — the executor should handle it during Task 1 of Plan 10-02. All other findings are either already addressed or minor additions.
