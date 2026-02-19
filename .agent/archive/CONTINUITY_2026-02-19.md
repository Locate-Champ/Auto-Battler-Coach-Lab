# Archived continuity snapshot
Archived on: 2026-02-19
Reason: Phase 6B compaction to reduce repetition/context loss.

---

# CONTINUITY - TFT Coach

If this file exceeds ~250 lines, archive and compact again.

## [PLANS]
- 2026-02-18T22:18:28Z [USER] Execute two commits only: Commit A (guardrails + ignore hygiene + untracking) and Commit B (resolver + tests + continuity compaction).
- 2026-02-18T22:18:28Z [USER] Scope lock: no `src/` migration and no offline-builder path migration in this batch.
- 2026-02-18T22:18:28Z [CODE] TODO(docs): update `docs/REPO_ARCHITECTURE.md` and `docs/COACH_UPGRADE_INDEX.md` to document `TFT_OUTPUTS_DIR` / `TFT_CHECKPOINT_DIR` / `TFT_ARTIFACT_ROOT` runtime resolver precedence.

## [DECISIONS]
- 2026-02-18T22:18:28Z [USER] `outputs/coach/**` is the only tracked subset under `outputs/**`.
- 2026-02-18T22:18:28Z [USER] Runtime outputs precedence is `TFT_OUTPUTS_DIR` > `TFT_ARTIFACT_ROOT/outputs/coach` > `<repo>/outputs/coach`.
- 2026-02-18T22:18:28Z [USER] Runtime checkpoints precedence is `TFT_CHECKPOINT_DIR` > `TFT_ARTIFACT_ROOT/checkpoints` > `<repo>/models/checkpoints`.
- 2026-02-18T22:18:28Z [USER] `TFT_OUTPUTS_DIR` is a direct runtime directory; do not auto-append `/coach`.
- 2026-02-18T22:18:28Z [USER] `coach/scoring` must never hardcode `outputs/` or `models/checkpoints` paths.

## [PROGRESS]
- 2026-02-18T22:18:28Z [TOOL] Commit A completed as `6e4a51a` with `.claude/settings.json`, `.gitignore` allowlist rules, `outputs/coach/README.md`, and two-pass untracking (`results`, `tmp`, `live-logs`, `models/checkpoints`, non-coach `outputs`).
- 2026-02-18T22:18:28Z [TOOL] Commit A ignore checks passed: `.claude/settings.local.json` and generated dirs ignored; `outputs/coach/archetypes.json` not ignored; `.agent/CONTINUITY.md` not ignored.
- 2026-02-18T22:21:11Z [CODE] Commit B implementation completed in working tree: added `coach/artifacts.py`, rewired `coach/scoring/archetypes.py` + `coach/scoring/evaluator.py`, added `tests/test_coach_artifacts.py`, and added `tests/test_no_hardcoded_artifact_paths.py`.
- 2026-02-18T22:21:11Z [TOOL] Commit B verification passed: smoke import command succeeded and `python -m pytest tests/test_coach_archetype_library.py tests/test_coach_planner.py tests/test_no_hardcoded_artifact_paths.py tests/test_coach_artifacts.py` reported 21 passed.

## [DISCOVERIES]
- 2026-02-18T22:18:28Z [TOOL] `rg -n "metatft_" -S` showed `outputs/metatft_*` are generated outputs referenced by producer scripts, not runtime scoring readers.
- 2026-02-18T22:18:28Z [TOOL] `models/checkpoints/smoke/` does not exist; no smoke allowlist added.
- 2026-02-18T22:18:28Z [TOOL] Hardcoded runtime paths were found in `coach/scoring/archetypes.py` and `coach/scoring/evaluator.py` and are being removed via resolver wiring.

## [OUTCOMES]
- 2026-02-18T22:21:11Z [CODE] Two-commit prune + resolver batch completed per scope lock, with no `src/` migration and no offline-builder path migration.

