# Auto-Battler Coach Companion - Project Knowledge Base

## Scope
This document summarizes the core project context for the coaching overlay, runtime API, and simulation-backed recommendation loop.

## Core system
- Live state ingestion from local provider logs.
- Runtime API and websocket server under `app/`.
- Decision modules and scoring under `coach/`.
- Deterministic simulation under `simulator/`.

## Data policy
- Personal match data is local-only under `data/local/**`.
- Tracked repository data must be sanitized and non-account-linked.
- Asset packs and proprietary icon dumps are local-only.

## Runtime artifacts
- Tracked runtime artifacts live under `outputs/coach/**`.
- Checkpoints and run outputs are generated and untracked.

## Operational reminders
- Keep docs and scripts aligned with `AGENTS.md`.
- Avoid cross-track refactors unless intentional and scoped.
- Prefer deterministic checks before broader test runs.
