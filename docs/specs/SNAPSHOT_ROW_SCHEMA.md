# SnapshotRow Schema (Collector Output)

Last updated: 2026-02-13

This document specifies the per-decision/per-round training rows emitted by the simulator collector.

Source implementation:
- `simulator/game/collector.py` (`GameCollector.get_training_rows`)

## Timing Semantics

- Snapshot state is captured **pre-combat**: after matchmaking, before combat resolves (`on_round_start`).
- Combat result metadata is attached after the round completes (`on_round_end`), without mutating the snapshot board state.

## Versioning

Each row includes:
- `row_schema_version`: `int`

Rules:
- Backwards-compatible additive fields: keep `row_schema_version` the same.
- Breaking changes (rename/remove/semantic change): bump `row_schema_version`.

Current:
- `row_schema_version = 1`

## Columns

Scalars:
- `row_schema_version`: `int`
- `game_id`: `int`
- `round`: `int` (simulator round counter; see `simulator/game/game.py` `round_num`)
- `player_id`: `int` (0-7)
- `placement`: `int` (final placement label, 1-8)
- `hp`: `int`
- `gold`: `int`
- `level`: `int`
- `streak`: `int` (signed: `win_streak - loss_streak`)
- `board_count`: `int`
- `win_streak`: `int`
- `loss_streak`: `int`
- `num_augments`: `int`
- `num_traits`: `int`
- `alive_count`: `int`

Structured (self):
- `units`: `list[dict]` where each element has:
  - `champion_id`: `str` (API name, e.g. `TFT16_Ekko`)
  - `star_level`: `int` (1-3)
  - `items`: `list[str]`
  - `position`: `int | null` (hex index `row*7 + col`, 0-27)
- `traits`: `dict[str, int]` (active traits)
- `augments`: `list[str]` (augment apiNames; length 0-3)

Structured (opponent, when available):
- `opponent_units`: `list[dict]` (same element shape as `units`)
- `opponent_traits`: `dict[str, int]`
- `opponent_hp`: `int`
- `opponent_gold`: `int`
- `opponent_level`: `int`
- `opponent_win_streak`: `int`
- `opponent_loss_streak`: `int`
- `opponent_streak`: `int`
- `opponent_board_count`: `int`
- `opponent_augments`: `list[str]`
- `opponent_num_augments`: `int`
- `opponent_num_traits`: `int`

Combat result (for this round):
- `combat_result`: `0|1|2|null` (loss/win/draw/unknown)
- `damage_dealt`: `float`
- `damage_taken`: `float`
- `combat_time`: `float`
- `survivors`: `int` (surviving units on winning side; 0 for loser/draw)
- `is_ghost`: `bool`

Compact feature helpers (redundant but fast):
- `board_names`: `list[str]`
- `board_stars`: `list[int]`
- `trait_names`: `list[str]`
- `trait_counts`: `list[int]`

## Example (Redacted)

```json
{
  "row_schema_version": 1,
  "game_id": 123,
  "round": 18,
  "player_id": 0,
  "placement": 2,
  "hp": 42,
  "gold": 31,
  "level": 7,
  "streak": -2,
  "board_count": 7,
  "win_streak": 0,
  "loss_streak": 2,
  "num_augments": 2,
  "num_traits": 5,
  "alive_count": 6,
  "units": [
    {"champion_id": "TFT16_Ekko", "star_level": 2, "items": ["TFT_Item_BlueBuff"], "position": 3}
  ],
  "traits": {"Zaun": 3, "Bruiser": 2},
  "augments": ["TFT6_Augment_Something"],
  "opponent_units": [],
  "opponent_traits": {},
  "opponent_hp": 0,
  "opponent_gold": 0,
  "opponent_level": 0,
  "opponent_win_streak": 0,
  "opponent_loss_streak": 0,
  "opponent_streak": 0,
  "opponent_board_count": 0,
  "opponent_augments": [],
  "opponent_num_augments": 0,
  "opponent_num_traits": 0,
  "combat_result": 1,
  "damage_dealt": 8.0,
  "damage_taken": 0.0,
  "combat_time": 23.5,
  "survivors": 3,
  "is_ghost": false,
  "board_names": ["Ekko"],
  "board_stars": [2],
  "trait_names": ["Zaun", "Bruiser"],
  "trait_counts": [3, 2]
}
```

