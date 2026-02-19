# CONTINUITY - TFT Coach

If this file exceeds ~250 lines, archive and compact again.

## [PLANS]
- 2026-02-19T01:40Z [CODE] Current state: Phase 3/4 guardrails are in place and Phase 6A now enforces the in-repo plans path in CI.
- Next steps (max 5):
  1) Keep plans under `.agent/plans/` using `YYYY-MM-DD_<topic>.md`.
  2) Run the Phase 6 verification command set before ending this batch.
  3) Keep this file compact and archive again if it grows past ~250 lines.

## [DECISIONS]
- 2026-02-19T01:40Z [CODE] LOCKED: outputs/coach/** is the only tracked subset under outputs/.
- 2026-02-19T01:40Z [CODE] LOCKED: runtime resolver precedence:
  - outputs: TFT_OUTPUTS_DIR > TFT_ARTIFACT_ROOT/outputs/coach > `<repo>/outputs/coach`
  - checkpoints: TFT_CHECKPOINT_DIR > TFT_ARTIFACT_ROOT/checkpoints > `<repo>/models/checkpoints`
- 2026-02-19T01:40Z [CODE] LOCKED: no hardcoded outputs/ or models/checkpoints paths in coach/scoring (enforced by tests).

## [PROGRESS]
- 2026-02-19T01:40Z [CODE] Phase 6A completed: in-repo plans path enforced + CI check added.
- 2026-02-19T01:40Z [CODE] Phase 6B completed: continuity archived + compacted.

## [DISCOVERIES]
- (keep this section empty unless something surprising happened)

## [OUTCOMES]
- 2026-02-19T01:40Z [CODE] Continuity is now compact, top-loaded, and policy-locked.
