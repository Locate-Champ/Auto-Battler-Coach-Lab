"""Tests for DataLoader."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from models.data_loader import DataLoader


def _make_rows() -> list[dict]:
    return [
        {
            "game_id": 10,
            "round": 4,
            "player_id": 0,
            "level": 4,
            "hp": 90,
            "gold": 12,
            "win_streak": 1,
            "loss_streak": 0,
            "placement": 2,
            "combat_result": 1,
            "board_names": ["fiddlesticks"],
            "board_stars": [2],
            "trait_names": ["harvester"],
            "trait_counts": [1],
            "augments": ["TFT10_Augment_GoingLong"],
        },
        {
            "game_id": 10,
            "round": 5,
            "player_id": 0,
            "level": 5,
            "hp": 84,
            "gold": 4,
            "win_streak": 0,
            "loss_streak": 1,
            "placement": 2,
            "combat_result": 0,
            "board_names": ["fiddlesticks"],
            "board_stars": [2],
            "trait_names": ["harvester"],
            "trait_counts": [1],
            "augments": ["TFT10_Augment_GoingLong"],
        },
        {
            "game_id": 10,
            "round": 4,
            "player_id": 1,
            "level": 4,
            "hp": 85,
            "gold": 8,
            "win_streak": 0,
            "loss_streak": 1,
            "placement": 6,
            "combat_result": 0,
            "board_names": ["jinx"],
            "board_stars": [1],
            "trait_names": ["gunslinger"],
            "trait_counts": [2],
            "augments": ["TFT10_Augment_CrashTestDummies"],
        },
        {
            "game_id": 10,
            "round": 5,
            "player_id": 1,
            "level": 4,
            "hp": 79,
            "gold": 10,
            "win_streak": 1,
            "loss_streak": 0,
            "placement": 6,
            "combat_result": 1,
            "board_names": ["jinx"],
            "board_stars": [1],
            "trait_names": ["gunslinger"],
            "trait_counts": [2],
            "augments": ["TFT10_Augment_CrashTestDummies"],
        },
        {
            "game_id": 20,
            "round": 4,
            "player_id": 0,
            "level": 5,
            "hp": 95,
            "gold": 20,
            "win_streak": 2,
            "loss_streak": 0,
            "placement": 1,
            "combat_result": 1,
            "board_names": ["ornn"],
            "board_stars": [2],
            "trait_names": ["blacksmith"],
            "trait_counts": [1],
            "augments": ["TFT16_Augment_AirAxiom"],
        },
        {
            "game_id": 20,
            "round": 5,
            "player_id": 0,
            "level": 5,
            "hp": 90,
            "gold": 18,
            "win_streak": 1,
            "loss_streak": 0,
            "placement": 1,
            "combat_result": 1,
            "board_names": ["ornn"],
            "board_stars": [2],
            "trait_names": ["blacksmith"],
            "trait_counts": [1],
            "augments": ["TFT16_Augment_AirAxiom"],
        },
        {
            "game_id": 20,
            "round": 4,
            "player_id": 1,
            "level": 5,
            "hp": 70,
            "gold": 3,
            "win_streak": 0,
            "loss_streak": 2,
            "placement": 8,
            "combat_result": 0,
            "board_names": ["vayne"],
            "board_stars": [1],
            "trait_names": ["longshot"],
            "trait_counts": [2],
            "augments": ["TFT_Augment_PowerUp"],
        },
        {
            "game_id": 20,
            "round": 5,
            "player_id": 1,
            "level": 5,
            "hp": 62,
            "gold": 5,
            "win_streak": 0,
            "loss_streak": 3,
            "placement": 8,
            "combat_result": 0,
            "board_names": ["vayne"],
            "board_stars": [1],
            "trait_names": ["longshot"],
            "trait_counts": [2],
            "augments": ["TFT_Augment_PowerUp"],
        },
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_load_and_split_by_game_id(tmp_path: Path) -> None:
    rows = _make_rows()
    _write_jsonl(tmp_path / "chunk_0000.jsonl", rows)
    loader = DataLoader(tmp_path)

    loaded = loader.load_raw()
    labels = np.asarray([1 if int(row["placement"]) <= 4 else 0 for row in loaded], dtype=np.int64)
    train_rows, test_rows, _, _ = loader._split_by_game_id(loaded, labels, test_size=0.5, seed=42, stratify=True)  # noqa: SLF001

    train_games = {row["game_id"] for row in train_rows}
    test_games = {row["game_id"] for row in test_rows}
    assert train_games.isdisjoint(test_games)


def test_task_loaders_return_feature_matrices(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "chunk_0000.jsonl", _make_rows())
    loader = DataLoader(tmp_path)

    X_train, X_test, y_train, y_test = loader.load_top4_classification_data(test_size=0.5, seed=42)
    assert X_train.ndim == 2 and X_test.ndim == 2
    assert y_train.ndim == 1 and y_test.ndim == 1
    assert X_train.shape[1] == X_test.shape[1]


def test_fight_loader_uses_next_round_labels(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "chunk_0000.jsonl", _make_rows())
    loader = DataLoader(tmp_path)

    X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(test_size=0.5, seed=42)
    total_examples = X_train.shape[0] + X_test.shape[0]
    combined_labels = np.concatenate([y_train, y_test])

    # We have 4 player timelines with at least 2 rounds each -> 4 temporal examples.
    assert total_examples == 4
    assert set(combined_labels.tolist()) == {0, 1}
