# .agent/plans

This directory is the canonical in-repo location for agent plan files.

Canonical setting (enforced in CI):
- `.claude/settings.json` -> `"plansDirectory": "./.agent/plans"`

Plan file naming convention:
- `YYYY-MM-DD_<topic>.md`

Minimal plan template (copy/paste):

## Goal
(one sentence)

## Constraints
- In scope:
- Out of scope:

## Plan
1)
2)
3)

## Verification
- Commands to run:

## Stop conditions
- If any verification fails, stop and report.
