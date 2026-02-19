# Data Directory Policy

Tracked data in this repository must be safe, minimal, and non-personal.

## Local-only data (gitignored)
Put real runtime/personal/raw data under:
- `data/local/**`
- `data/raw/**`
- `data/matches/**`
- `knowledge-base/raw/**`
- `data/api/raw/**`
- `data/api/tft_*/**`

## Tracked data
Tracked files under `data/**` should be:
- Schema/reference files.
- Small sanitized examples for tests/docs.
- Non-personal processed metadata.

## Runtime behavior
Runtime code should not silently fall back to fake samples. If required local data is missing, fail with a clear, actionable error.
