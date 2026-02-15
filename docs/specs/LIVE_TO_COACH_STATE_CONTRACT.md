# LiveState -> CoachState Contract

Last updated: 2026-02-13

This document defines the contract between the live runtime state (`app/state`) and the coach-facing state (`coach/state.py`).

## CoachState Type

Canonical type: `coach.state.GameState`

Required fields:
- `stage`: `str` (TFT tag like `"4-2"`). Used for stage-aware scoring.
- `player`: `PlayerState`
  - `level`: `int`
  - `hp`: `int`
  - `gold`: `int`
- `board`: `tuple[UnitState, ...]` (board units only)

Optional fields (may be empty / missing in live):
- `bench`: `tuple[UnitState, ...]`
- `shop`: `tuple[ShopUnit, ...]`
- `items`: `tuple[str, ...]` (unassigned items/components)
- `augments`: `tuple[str, ...]`
- `traits`: `tuple[tuple[str, int], ...]` (may be omitted and derived)
- `opponents`: `tuple[OpponentState, ...]` (scouted boards when available)
- `notes`: `tuple[str, ...]` (debug tags)

Versioning:
- `schema_version`: `int` on `coach.state.GameState` (current: `1`)

## Defaulting Rules

When live data is missing:
- Missing XP: `player.xp = None`
- Missing shop: `shop = ()`
- Missing unassigned items: `items = ()`
- Missing opponent boards/meta: `opponents = ()`
- Missing traits: `traits = ()` and the coach derives traits from champion reference data (`coach/scoring/features.py`) when scoring.

## Invariants

These are validated by `coach.state.validate_coach_state(state) -> list[str]`:
- Board positions must be within `0 <= row < 4`, `0 <= col < 7`.
- No two board units may occupy the same `(row, col)`.
- `len(unit.items) <= 3` for all units.
- `len(bench) <= 9`.
- `len(items) <= 10`.
- Board cap: `len(board) <= player.level` (best-effort safety check).

If validation fails:
- The WebSocket server logs the first errors and continues (no crash).
- Validation errors are included in the outgoing coach payload for UI/debug.

## Derived Fields

The coach may derive:
- `traits` from board units using champion reference data in `data/game_data/champions.jsonl`.
- Carry/tank heuristics (for candidate generation) from cost/star/items, when archetype priors are unavailable.

