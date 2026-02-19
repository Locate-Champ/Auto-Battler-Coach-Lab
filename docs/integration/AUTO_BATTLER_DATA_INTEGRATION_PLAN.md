# Auto-Battler Match Data Integration Plan

## Goal
Build a local-only pipeline for importing, cleaning, and using match history without committing personal or account-linked data.

## Inputs (local-only)
- Raw Riot API exports under `data/local/matches/`.
- Optional log-derived augment exports under `data/local/personal/`.

## Outputs (local-only)
- `data/local/matches/all_matches.csv`
- `data/local/personal/carry_performance_corrected.csv`
- `data/local/personal/trait_performance_corrected.csv`
- `data/local/personal/item_performance_corrected.csv`

## Processing steps
1. Fetch raw matches with `scripts/pull_riot_matches.py`.
2. Normalize/merge with `scripts/process_riot_matches.py`.
3. Generate summary personal stats with local analysis scripts.
4. Validate schema compatibility before runtime use.

## Runtime contract
- Runtime does not load sample data by default.
- If required local files are missing, runtime must fail with a clear message and expected paths.

## Safety rules
- Never commit `data/local/**`.
- Never commit account identifiers or match-level personal logs.
- Keep only sanitized examples under `data/examples/**`.
