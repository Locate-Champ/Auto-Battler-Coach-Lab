# Live Data Integration Progress

Last Updated: 2026-02-19

## Summary
Live runtime state ingestion is implemented through log parsing and websocket broadcast.

## Completed
- Parser wiring for board/bench/roster events.
- State manager updates for player board, bench, and roster.
- Frontend websocket hooks for live state updates.
- Board transformation utilities for UI rendering.

## Current data paths
- Runtime logs: local provider logs (for example MetaTFT/Overwolf) on the local machine.
- Runtime websocket: `ws://127.0.0.1:8765/ws`

## Security and privacy notes
- Account-linked profile dumps and per-match raw payloads are local-only.
- Do not commit account identifiers, UUIDs, or raw personal exports.

## Next checks
1. Validate end-to-end live update flow in a local session.
2. Confirm no personal raw dumps are tracked.
3. Keep all runtime dumps under `data/local/**`.
