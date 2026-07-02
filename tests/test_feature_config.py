"""Tests for NumericFeatureConfig creation, immutability, override, and wiring."""

from __future__ import annotations

import dataclasses

import pytest

from models.feature_config import DEFAULT_CONFIG, NumericFeatureConfig


def test_default_config_instantiation() -> None:
    """DEFAULT_CONFIG is a NumericFeatureConfig with expected defaults."""
    assert isinstance(DEFAULT_CONFIG, NumericFeatureConfig)
    assert len(dataclasses.fields(DEFAULT_CONFIG)) == 16
    # Spot-check representative fields
    assert DEFAULT_CONFIG.max_interest == 5.0
    assert DEFAULT_CONFIG.interest_gold_divisor == 10.0
    assert DEFAULT_CONFIG.default_avg_placement == 4.5
    assert DEFAULT_CONFIG.classification_threshold == 0.2


def test_config_is_frozen() -> None:
    """Attempting to mutate a frozen config raises an error."""
    with pytest.raises(AttributeError):
        DEFAULT_CONFIG.max_interest = 99.0  # type: ignore[misc]


def test_config_override_with_replace() -> None:
    """dataclasses.replace() creates a new config without mutating the original."""
    custom = dataclasses.replace(DEFAULT_CONFIG, max_interest=10.0)
    assert custom.max_interest == 10.0
    assert DEFAULT_CONFIG.max_interest == 5.0  # Original unchanged


def test_feature_engineer_uses_custom_config() -> None:
    """TFTFeatureEngineer accepts and stores a custom numeric config."""
    from models.feature_engineering import TFTFeatureEngineer

    custom = dataclasses.replace(DEFAULT_CONFIG, max_interest=10.0)
    fe = TFTFeatureEngineer(numeric_config=custom)
    assert fe._numeric_config.max_interest == 10.0


def test_feature_engineer_default_config() -> None:
    """TFTFeatureEngineer uses DEFAULT_CONFIG when no numeric_config is provided."""
    from models.feature_engineering import TFTFeatureEngineer

    fe = TFTFeatureEngineer()
    assert fe._numeric_config is DEFAULT_CONFIG


def test_all_fields_are_float() -> None:
    """Every field on NumericFeatureConfig is annotated as float."""
    for field in dataclasses.fields(NumericFeatureConfig):
        assert field.type == "float", (
            f"Field {field.name!r} has type {field.type!r}, expected 'float'"
        )
