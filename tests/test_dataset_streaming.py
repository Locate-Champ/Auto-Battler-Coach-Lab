"""Tests for streaming transformer datasets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("torch")

from models.dataset import TFTStreamingDataset, _normalize_row, estimate_streaming_split_counts


def _rows() -> list[dict]:
    return [
        {
            "game_id": 1,
            "round": 4,
            "player_id": 0,
            "level": 4,
            "hp": 90,
            "gold": 12,
            "win_streak": 1,
            "loss_streak": 0,
            "placement": 2,
            "combat_result": 1,
            "units": [{"champion_id": "TFT16_Jinx", "star_level": 2, "items": [], "position": 1}],
            "traits": {"TFT16_Gunslinger": 2},
            "augments": [],
            "opponent_units": [
                {"champion_id": "TFT16_Vayne", "star_level": 1, "items": [], "position": 2}
            ],
            "opponent_traits": {"TFT16_Longshot": 2},
        },
        {
            "game_id": 1,
            "round": 5,
            "player_id": 0,
            "level": 4,
            "hp": 85,
            "gold": 10,
            "win_streak": 0,
            "loss_streak": 1,
            "placement": 2,
            "combat_result": 0,
            "units": [{"champion_id": "TFT16_Jinx", "star_level": 2, "items": [], "position": 1}],
            "traits": {"TFT16_Gunslinger": 2},
            "augments": [],
            "opponent_units": [
                {"champion_id": "TFT16_Vayne", "star_level": 1, "items": [], "position": 2}
            ],
            "opponent_traits": {"TFT16_Longshot": 2},
        },
        {
            "game_id": 1,
            "round": 4,
            "player_id": 1,
            "level": 4,
            "hp": 80,
            "gold": 8,
            "win_streak": 0,
            "loss_streak": 1,
            "placement": 6,
            "combat_result": 0,
            "units": [{"champion_id": "TFT16_Vayne", "star_level": 1, "items": [], "position": 2}],
            "traits": {"TFT16_Longshot": 2},
            "augments": [],
            "opponent_units": [
                {"champion_id": "TFT16_Jinx", "star_level": 2, "items": [], "position": 1}
            ],
            "opponent_traits": {"TFT16_Gunslinger": 2},
        },
        {
            "game_id": 1,
            "round": 5,
            "player_id": 1,
            "level": 4,
            "hp": 76,
            "gold": 9,
            "win_streak": 1,
            "loss_streak": 0,
            "placement": 6,
            "combat_result": 1,
            "units": [{"champion_id": "TFT16_Vayne", "star_level": 1, "items": [], "position": 2}],
            "traits": {"TFT16_Longshot": 2},
            "augments": [],
            "opponent_units": [
                {"champion_id": "TFT16_Jinx", "star_level": 2, "items": [], "position": 1}
            ],
            "opponent_traits": {"TFT16_Gunslinger": 2},
        },
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_estimate_streaming_split_counts_next_round(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "chunk_0000.jsonl", _rows())
    counts = estimate_streaming_split_counts(
        tmp_path,
        label_mode="next_round",
        train_ratio=1.0,
        val_ratio=0.0,
    )
    # Two players with one next-round transition each.
    assert counts["train"] == 2
    assert counts["val"] == 0
    assert counts["test"] == 0


def test_streaming_dataset_next_round_labels(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "chunk_0000.jsonl", _rows())
    dataset = TFTStreamingDataset(
        tmp_path,
        split="train",
        label_mode="next_round",
        train_ratio=1.0,
        val_ratio=0.0,
        shuffle_files=False,
    )
    samples = list(dataset)
    assert len(samples) == 2

    labels = {float(sample["fight_result"].item()) for sample in samples}
    assert labels == {0.0, 1.0}

    for sample in samples:
        assert "player_champion_ids" in sample
        assert "opponent_champion_ids" in sample
        assert sample["placement"].shape == (1,)


def test_normalize_row_decodes_opponent_augments_json_string() -> None:
    normalized = _normalize_row(
        {
            "opponent_augments": '["TFT_Augment_PowerUp", "TFT16_Augment_AirAxiom"]',
        }
    )
    assert normalized["opponent_augments"] == ["TFT_Augment_PowerUp", "TFT16_Augment_AirAxiom"]
