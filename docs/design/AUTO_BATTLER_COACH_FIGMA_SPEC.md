# Auto-Battler Coach Companion - Figma UI Specification

## Purpose
Define a compact overlay UI for live coaching suggestions and board context.

## Layout blocks
- Header: app title, connection status, stage/round.
- Board panel: current board and bench.
- Recommendation panel: top actions for items, positioning, economy, and shop.
- Context panel: traits, augments, and quick risk indicators.

## Data contract expectations
- Live state arrives from websocket updates.
- Missing optional fields should degrade gracefully in UI.
- Trait icons are optional local assets; text fallback must always work.

## Design constraints
- Desktop-first overlay with readable typography at small sizes.
- High-contrast status colors for quick glanceability.
- Stable panel sizing to reduce layout jitter during updates.
