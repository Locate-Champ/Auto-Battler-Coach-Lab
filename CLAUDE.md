# CLAUDE
This file is canonical. CLAUDE.md is generated from it.

## Mission
Keep the repo focused, deterministic, and fast to navigate for both humans and agents.

## Stop First
1. Pick the right track before editing anything.
2. Make the smallest possible scoped change.
3. Run only the required verification for touched code.

## Track Map (Non-Negotiable)
- Runtime API recommender: `app/api/server.py` uses `src/models`.
- Training and evaluation pipeline: `models/`.
- Active simulator truth: `simulator/core` and `simulator/game`.
- Legacy simulator (quarantined): `simulator/Simulator`, `simulator/Concurrency`, `simulator/Evaluator`.

## Artifact Contract
- Tracked runtime artifacts under `outputs/coach/**` only.
- `results/`, `tmp/`, `live-logs/`, `models/checkpoints/**`, and non-coach `outputs/**` are generated and untracked.
- Runtime artifact resolver env vars:
  - `TFT_OUTPUTS_DIR`
  - `TFT_CHECKPOINT_DIR`
  - `TFT_ARTIFACT_ROOT`

## Scope and Safety Rules
1. No drive-by refactors.
2. No feature work in legacy simulator paths.
3. No secrets in chat or code.
4. No destructive git commands.
5. No commit unless explicitly requested.
6. If unexpected repo state appears, stop and ask.

## Verification Rules
Run only what applies to your touched paths.

- Combat engine or simulator combat behavior changed:
  - `python -m simulator.benchmark` (determinism must pass)
- Collector/output schema or output formatting changed:
  - `python -m simulator.validate_output <dir>` (19 checks pass)
- Coach/runtime scoring changed:
  - `python -m pytest tests/test_coach_archetype_library.py tests/test_coach_planner.py tests/test_no_hardcoded_artifact_paths.py`
- Track-boundary policy changes:
  - `python -m pytest tests/test_track_boundaries.py`
- General Python tests:
  - `python -m pytest`
- Frontend code changed:
  - `cd app/frontend && npm run build`

## Working Discipline
1. Keep commits small and single-purpose.
2. Verify staged files match intended scope before commit:
   - `git diff --cached --name-only`
   - `git status --porcelain`
3. Keep working tree clean between phase commits.

## Dual-Track Override Policy (Required)
If a PR touches both `src/models/**` and `models/**` with code/config changes, it must include:
- PR label: `allow-dual-track`
- PR body section: `Dual-Track Reason:`
- PR body section: `Exit Plan:`

Without all three, the PR fails policy checks.

## Continuity Rules
- Canonical continuity file: `.agent/CONTINUITY.md`.
- Keep it compact and high-signal; if it exceeds ~250 lines, archive and compact.
- Record only meaningful deltas with timestamp + provenance tags.

## Completion Rules
Before final response:
1. Run completion notification:
   - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\notify-ntfy.ps1 -Title "Codex done" -Message "<one-line summary>"`
2. End with `Next Improvements`.

## Canonical Docs
- Docs hub: `docs/INDEX.md`
- Architecture: `docs/REPO_ARCHITECTURE.md`
- Current simulator/model truth: `docs/CURRENT_MODEL_AND_SIMULATOR.md`
- AWS gates runbook: `docs/runbooks/aws_gates.md`

## Quick Commands
- Start app stack: `npm start`
- Simulator batch: `python -m simulator.cloud_runner --games 1000 --workers 11 --output results/batch`
- Validate output: `python -m simulator.validate_output results/batch`
- Benchmark/determinism: `python -m simulator.benchmark`
- Tests: `python -m pytest`
