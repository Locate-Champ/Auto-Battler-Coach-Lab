# Model Artifact Schema (Runtime Loading)

Last updated: 2026-02-14

This document defines how runtime coach code loads offline-produced artifacts (archetypes + evaluator).

## Archetype Artifact

Path (default):
- `outputs/coach/archetypes.json`

Producer:
- `python -m coach.offline.build_knowledge_base`
- `python -m coach.offline.build_archetypes`

Schema (top-level):
- `schema_version`: `int`
- `type`: `str` (example: `"coach_archetypes"`)
- `source`: `str` (input path or dataset id)
- `count`: `int`
- `archetypes`: `list[dict]`

Each archetype:
- `archetype_id`: `str`
- `name`: `str`
- `tier`: `str`
- `units`: `list[str]` (champion API ids)
- `traits`: `list[str]` (display trait names)
- `builds`: `list[dict]` (optional item signatures; see below)
- `stats`: `dict` (optional; example keys: `top4_rate`, `avg_placement`, `games_played`)

Optional `builds[*]` schema:
- `unit`: `str` (champion API id, e.g. `TFT16_Kaisa`)
- `unit_token`: `str` (optional; raw unit token from the source file)
- `items`: `list[str]` (runtime item ids; typically `TFT_Item_*` or set-specific `TFT16_Item_*`)
- `games`: `int|float|null` (optional weight)
- `avg_placement`: `float|null`
- `place_change`: `float|null`

Runtime loader:
- `coach/scoring/archetypes.py`

Compatibility checks (runtime):
- `schema_version` present and supported.
- `archetypes[*].units` are strings (API ids).

## Evaluator Artifact

Path (default):
- `outputs/coach/evaluator_linear.json`

Producer:
- `python -m coach.offline.train_evaluator`
- `python -m coach.offline.train_models`

Schema (top-level):
- `schema_version`: `int`
- `type`: `str` (example: `"linear_logistic_pairwise_diff"`)
- `features`: `list[str]` (ordered feature names)
- `weights`: `list[float]` (same length as `features`)
- `bias`: `float`
- training metadata (optional): `train_pairs`, `val_pairs`, `train_acc`, `val_acc`, `input_dir`

Runtime loader:
- `coach/scoring/evaluator.py`

Compatibility checks (runtime):
- `schema_version` present and supported.
- `features` exactly match the runtime feature extractor version (names + order).

## Versioning Rules

- Artifacts must include a `schema_version`.
- Any breaking change to runtime feature extraction or artifact structure requires bumping `schema_version`.
- Runtime must fail fast with a clear error message on incompatible artifacts (or fall back to a heuristic evaluator when allowed).
