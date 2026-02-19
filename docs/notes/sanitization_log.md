# Sanitization Log

Date: 2026-02-19

## Removed tracked path groups
- `data/personal/*.csv`
- `data/api/raw/*`
- legacy versioned API dump directory under `data/api/` (fully removed)
- `data/local_game_data.json`
- `app/frontend/images/trait images/trait_icons_set16/*`

## Renamed tracked paths
- legacy scraper directory -> `scraper/`
- launcher script -> `app/START_AUTO_BATTLER_COACH.bat`
- local extraction script -> `scripts/extract_local_game_data.py`
- component outline doc -> `docs/AUTO_BATTLER_COACH_COMPONENT_OUTLINE.js`
- design spec doc -> `docs/design/AUTO_BATTLER_COACH_FIGMA_SPEC.md`
- integration plan doc -> `docs/integration/AUTO_BATTLER_DATA_INTEGRATION_PLAN.md`
- cloud plan doc -> `docs/plans/AUTO_BATTLER_CLOUD_SIMULATION_PLAN.md`
- combat timing research doc -> `docs/research/AUTO_BATTLER_COMBAT_TIMING_RESEARCH.md`
- knowledge summary doc -> `knowledge-base/AUTO_BATTLER_COACH_PROJECT_KNOWLEDGE.md`
- trait palette helper -> `app/frontend/images/set16_trait_palette.py`

Warning: Git history may still contain removed data until a history rewrite is performed.
