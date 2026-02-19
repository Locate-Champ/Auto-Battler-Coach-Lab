# Auto-Battler Coach Lab Repo Handoff

Last updated: 2026-02-19 (America/New_York)

## Purpose
This file is the quick onboarding handoff for new contributors and coding agents.

## Read order
1. `AGENTS.md`
2. `docs/INDEX.md`
3. `docs/REPO_ARCHITECTURE.md`
4. `docs/CURRENT_MODEL_AND_SIMULATOR.md`
5. `docs/runbooks/aws_gates.md` (when doing cloud gate work)

## Current guardrails
- `AGENTS.md` is canonical; `CLAUDE.md` is generated from it.
- Track boundaries are enforced by `tests/test_track_boundaries.py`.
- Runtime artifact path rules are enforced by `tests/test_no_hardcoded_artifact_paths.py`.
- Tracked runtime artifacts are limited to `outputs/coach/**`.

## Local data policy
- Personal and raw runtime data is local-only under `data/local/**`.
- Asset packs/icons are local-only and must not be tracked.
- If local runtime data is missing, runtime code should fail with actionable error messages.

## Next improvements
- Keep `.agent/CONTINUITY.md` compact and archive aggressively.
- Add any additional guard checks under `scripts/ci/` rather than root-level docs.
- Continue reducing ambiguous cross-track references in docs.
