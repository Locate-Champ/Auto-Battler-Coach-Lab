# CCG Plan Pre-Analysis — Phase 10
Generated: 2026-02-28

## Status
- Codex (codex-spark-5.3-medium-reasoning): SUCCESS | Implementation architect
- Gemini (gemini-3-flash-preview): FAILED | 429 rate limit exhausted after 3 retries

## Codex Analysis

### Proposed cloud_runner.py Split (SPLT-02)

**Create 3 underscore-prefixed sub-modules:**

1. `simulator/_cloud_runner_utils.py` (~250-400 LOC):
   - Constants: `WILSON_Z_95`, `AGENT_PROFILES`
   - Functions: `_pyarrow_available`, `_normalize_parquet_compression`, `_rust_extension_rebuild_hint`, `_extract_signature_parameter_names`, `_ensure_rust_parquet_method_support`, `_wilson_interval`, `_validate_reference_data_preflight`, `_compute_seed_end`, `_estimate_worker_cpu_share_pct`, `_sample_cpu_utilization_pct`, `_round_or_none`, `_build_cost_telemetry`, `_resolve_shard_range`, `_iter_task_batches`

2. `simulator/_cloud_runner_writer.py` (~500-650 LOC):
   - `StreamingWriter` class (all methods)

3. `simulator/_cloud_runner_core.py` (~700-850 LOC):
   - `BatchRunnerConfig`, `BatchAbort`
   - Worker state: `_worker_sim`, `_worker_parquet_validated`
   - `run_game`, `_worker_init`
   - `BatchRunner` class

**Facade (`simulator/cloud_runner.py`, ~450-650 LOC):**
- Keep: `_parse_agent_mix`, `_cli_flag_present`, `main`, `if __name__ == "__main__"`
- Re-export: `BatchRunner`, `BatchRunnerConfig`, `BatchAbort`, `StreamingWriter`
- Re-export private test-touched symbols: `_build_cost_telemetry`, `_ensure_rust_parquet_method_support`, `_extract_signature_parameter_names`
- Keep `inspect` imported at facade level (tests monkeypatch `cloud_runner.inspect.signature`)
- Add alias: `CloudRunner = BatchRunner` (to satisfy SC1 wording)

### Proposed feature_engineering.py Split (SPLT-01)

**Create 4 underscore-prefixed sub-modules:**

1. `models/_feature_engineering_config.py` (~180-260 LOC):
   - Constants: `EPSILON`, `STAR_SCALING_HP/AD`, `ATTACK_SPEED_CAP`, `BOARD_COLS`, `DEFAULT_STAGE_DIVISOR`, `REQUIRED_COLUMNS`, `_REQUIRED_COLUMN_GROUPS`, keyword tuples
   - Dataclasses: `FeatureConfig`, `TraitMetadata`
   - Helpers: `_normalize_token`, `_safe_float`, `_safe_int`, `_decode_maybe_json`

2. `models/_feature_engineering_loaders.py` (~420-600 LOC):
   - All `_load_*` methods as a mixin: `_load_reference_data`, `_build_fast_lookup_sets`, `_load_json`, `_load_champions`, `_load_traits`, `_normalize_item_effects`, `_classify_item_type`, `_load_items`, `_infer_augment_tier`, `_infer_augment_flags`, `_augment_data_candidates`, `_load_augments`, `_load_personal_reference`

3. `models/_feature_engineering_transform_row.py` (~750-900 LOC):
   - Canonical helpers: `_canonical_champion_id`, `_canonical_item_name`, `_canonical_trait_api`, `_normalize_trait_name`
   - Extraction: `_extract_augments`, `_extract_traits`, `_extract_units`, `_parse_unit`, `_position_row`
   - Single-row features: `_team_summary`, `_composition_features/names`, `_economy_features/names`, `_trait_features/names`, `_item_features/names`, `_augment_features/names`, `_matchup_features/names`, `_personal_features/names`
   - `_build_feature_names`, `transform`

4. `models/_feature_engineering_transform_batch.py` (~600-800 LOC):
   - `_validate_columns`, `transform_batch`, `_parse_units_column`, `_parse_traits_column`
   - `_augment_features_from_decoded`, `transform_arrow_batch`
   - All `_*_features_batch` methods
   - `feature_names` property

**Facade (`models/feature_engineering.py`, ~180-300 LOC):**
- Keep: `TFTFeatureEngineer.__init__`, `_DERIVED_ATTRS`, `__getstate__`, `__setstate__`
- Build class via mixins from loader/transform modules
- Re-export: `REQUIRED_COLUMNS`, `FeatureConfig`, `TraitMetadata`
- Add alias: `FeatureEngineer = TFTFeatureEngineer` (to satisfy SC2 wording)

### Technical Risks Identified

1. **Spawn multiprocessing breakage**: `run_game`/`_worker_init` must stay as top-level importable functions, not closures/wrappers — multiprocessing.Pool needs to pickle them
2. **Facade private-symbol compatibility**: Tests use private names on `simulator.cloud_runner` (e.g., `cloud_runner._build_cost_telemetry`); must re-export exact names
3. **`inspect` monkeypatch test**: `tests/test_benchmark_parity_helpers.py` monkeypatches `cloud_runner.inspect.signature`; facade must expose `inspect` module object
4. **Circular imports**: Enforce one-way deps: `core -> {utils, writer}`, `writer -> utils`, `facade -> {core,utils,writer}`
5. **Feature pickling path**: `TFTFeatureEngineer` has `__getstate__`/`__setstate__`; keep class defined in `models.feature_engineering` module to preserve pickle compatibility
6. **Feature order regression**: `_build_feature_names`, `transform`, `transform_batch`, `transform_arrow_batch` must remain byte-for-byte identical behavior

### Recommended Task Order

1. Split `cloud_runner` first (utils → writer → core → facade + re-exports)
2. Run targeted tests: `test_batch_runner.py`, `test_cloud_runner_cost_telemetry.py`, `test_benchmark_parity_helpers.py`
3. Split `feature_engineering` (config → loaders mixin → row-transform mixin → batch-transform mixin → facade class)
4. Run targeted tests: `test_feature_engineering.py`, `test_feature_config.py`, `test_coach_evaluator.py`
5. Full verification: `ruff check .`, `ruff format --check .`, `python -m pytest`

## Gemini Analysis
Skipped — model capacity exhausted (429 RESOURCE_EXHAUSTED after 3 retries)

Partial findings before failure:
- Confirmed `CloudRunner` does not exist in codebase; SC1 should reference `BatchRunner`
- Confirmed `FeatureEngineer` does not exist; SC2 should reference `TFTFeatureEngineer`

## Claude Synthesis

### Key Decisions
1. **SC1/SC2 naming bug**: The roadmap success criteria reference `CloudRunner` and `FeatureEngineer` which don't exist. The plan should add aliases (`CloudRunner = BatchRunner`, `FeatureEngineer = TFTFeatureEngineer`) in the facades to satisfy the criteria literally, while also ensuring the real class names continue to work.

2. **Mixin vs standalone modules**: For `feature_engineering.py`, the mixin approach (methods distributed across mixin classes that TFTFeatureEngineer inherits from) is cleaner than standalone functions because all these methods access `self.*` attributes. The alternative (passing self explicitly) would be more invasive.

3. **cloud_runner split is lower risk**: cloud_runner has clearer boundaries (standalone functions, separate classes). Split this first to establish the pattern before tackling the tighter-coupled feature_engineering.

4. **Worker function placement**: `run_game` and `_worker_init` must remain in a real module file (not dynamically composed) because multiprocessing.Pool pickles function references by module path.

5. **FeatureConfig already extracted**: `models/feature_config.py` already exists from Phase 6. The new `_feature_engineering_config.py` should contain only the constants/helpers NOT already in `feature_config.py`. Avoid duplication.

### Risk Mitigations
- Run targeted tests after each file split before proceeding to the next
- Verify pickle round-trip of TFTFeatureEngineer after split
- Verify `python -m simulator.cloud_runner --help` still works after split (CLI entry point)
