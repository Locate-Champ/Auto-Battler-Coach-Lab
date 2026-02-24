"""Tests for TFTFeatureEngineer."""

from __future__ import annotations

import numpy as np

from models.feature_engineering import TFTFeatureEngineer


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
