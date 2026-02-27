"""Tests for TFTFeatureEngineer."""

from __future__ import annotations

import json

import numpy as np
import pytest

from models.feature_engineering import REQUIRED_COLUMNS, TFTFeatureEngineer


def _sample_row() -> dict:
    return {
        "game_id": 1,
        "round": 12,
        "player_id": 0,
        "level": 7,
        "hp": 74,
        "gold": 32,
        "streak": 3,
        "units": [
            {
                "champion_id": "TFT16_Fiddlesticks",
                "star_level": 2,
                "items": [
                    "TFT_Item_BlueBuff",
                    "TFT_Item_Morellonomicon",
                    "TFT_Item_JeweledGauntlet",
                ],
                "position": 17,
            },
            {
                "champion_id": "TFT16_Ornn",
                "star_level": 2,
                "items": ["TFT_Item_ProtectorsVow"],
                "position": 4,
            },
        ],
        "traits": {"TFT16_Harvester": 1, "TFT16_Blacksmith": 1},
        "augments": ["TFT10_Augment_GoingLong", "TFT_Augment_PowerUp", "TFT16_Augment_AirAxiom"],
        "opponent_hp": 61,
        "opponent_units": [
            {
                "champion_id": "TFT16_Jinx",
                "star_level": 2,
                "items": ["TFT_Item_RunaansHurricane"],
                "position": 24,
            }
        ],
        "opponent_traits": {"TFT16_Gunslinger": 2},
        "combat_result": 1,
        "damage_dealt": 12.0,
        "placement": 2,
    }


def test_transform_has_same_length_as_feature_names() -> None:
    engineer = TFTFeatureEngineer()
    vector = engineer.transform(_sample_row())
    names = engineer.feature_names()
    assert vector.shape[0] == len(names)
    assert vector.dtype == np.float32


def test_transform_has_no_nan_values() -> None:
    engineer = TFTFeatureEngineer()
    vector = engineer.transform(_sample_row())
    assert not np.isnan(vector).any()


# ---------------------------------------------------------------------------
# Schema validation tests — dict path (SCHM-01)
# ---------------------------------------------------------------------------


def test_transform_batch_validates_required_columns() -> None:
    """Missing required columns raise ValueError with descriptive message."""
    fe = TFTFeatureEngineer()
    row = {"level": 1, "hp": 100, "gold": 50, "round": 1, "streak": 0}
    # Missing: augments (strict), units group, traits group
    with pytest.raises(ValueError, match="Missing required columns") as exc_info:
        fe.transform_batch([row])
    msg = str(exc_info.value)
    assert "dict" in msg
    assert "augments" in msg
    assert "units" in msg
    assert "traits" in msg


def test_transform_batch_valid_data_passes() -> None:
    """Valid data passes validation without error."""
    fe = TFTFeatureEngineer()
    result = fe.transform_batch([_sample_row()])
    assert isinstance(result, np.ndarray)
    assert result.shape[0] == 1
    assert result.dtype == np.float32


def test_transform_batch_empty_batch_skips_validation() -> None:
    """Empty batch returns (0, N) array without validation error."""
    fe = TFTFeatureEngineer()
    result = fe.transform_batch([])
    assert result.shape[0] == 0
    assert result.ndim == 2


def test_transform_batch_error_lists_all_missing() -> None:
    """Error message lists ALL missing columns and groups, not just the first."""
    fe = TFTFeatureEngineer()
    row = {"level": 1}  # Missing 4 strict + 3 column groups
    with pytest.raises(ValueError) as exc_info:
        fe.transform_batch([row])
    msg = str(exc_info.value)
    # Strict required columns must appear
    for col in ("hp", "gold", "round", "augments"):
        assert col in msg, f"Missing column '{col}' not listed in error message"
    # Column groups must be mentioned
    for col in ("streak", "units", "traits"):
        assert col in msg, f"Missing group containing '{col}' not listed in error message"


def test_transform_batch_accepts_raw_format() -> None:
    """Raw simulation format with alternative column names passes validation."""
    fe = TFTFeatureEngineer()
    row = {
        "level": 4,
        "hp": 90,
        "gold": 12,
        "round": 4,
        "win_streak": 1,
        "loss_streak": 0,
        "board_names": ["fiddlesticks"],
        "board_stars": [2],
        "trait_names": ["harvester"],
        "trait_counts": [1],
        "augments": ["TFT10_Augment_GoingLong"],
        "placement": 2,
        "combat_result": 1,
    }
    result = fe.transform_batch([row])
    assert isinstance(result, np.ndarray)
    assert result.shape[0] == 1


# ---------------------------------------------------------------------------
# Schema validation tests — Arrow path (SCHM-02)
# ---------------------------------------------------------------------------


def test_transform_arrow_batch_validates_required_columns() -> None:
    """Arrow batch with missing columns raises ValueError."""
    pa = pytest.importorskip("pyarrow")
    fe = TFTFeatureEngineer()
    # Only "level" column — missing 7 required columns
    batch = pa.RecordBatch.from_pydict({"level": [7]})
    with pytest.raises(ValueError, match="Missing required columns") as exc_info:
        fe.transform_arrow_batch(batch)
    msg = str(exc_info.value)
    assert "Arrow" in msg


def test_transform_arrow_batch_valid_data_passes() -> None:
    """Arrow batch with all required columns passes validation."""
    pa = pytest.importorskip("pyarrow")
    fe = TFTFeatureEngineer()
    batch = pa.RecordBatch.from_pydict(
        {
            "level": [7],
            "hp": [74],
            "gold": [32],
            "round": [12],
            "streak": [3],
            "units": [
                json.dumps(
                    [{"champion_id": "TFT16_Ornn", "star_level": 2, "items": [], "position": 4}]
                )
            ],
            "traits": [json.dumps({"TFT16_Harvester": 1})],
            "augments": [json.dumps(["TFT10_Augment_GoingLong"])],
        }
    )
    result = fe.transform_arrow_batch(batch)
    assert isinstance(result, np.ndarray)
    assert result.shape[0] == 1
    assert result.dtype == np.float32


# ---------------------------------------------------------------------------
# REQUIRED_COLUMNS constant test
# ---------------------------------------------------------------------------


def test_required_columns_is_frozenset() -> None:
    """REQUIRED_COLUMNS is a frozenset with the strict required columns."""
    assert isinstance(REQUIRED_COLUMNS, frozenset)
    assert len(REQUIRED_COLUMNS) == 5
    assert "level" in REQUIRED_COLUMNS
    assert "hp" in REQUIRED_COLUMNS
    assert "gold" in REQUIRED_COLUMNS
    assert "round" in REQUIRED_COLUMNS
    assert "augments" in REQUIRED_COLUMNS
