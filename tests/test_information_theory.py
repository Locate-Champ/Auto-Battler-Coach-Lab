"""Tests for information-theory analysis helpers."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("xgboost")

from models.information_theory import FeatureInformationAnalyzer


def test_marginal_mi_ranks_informative_feature_first() -> None:
    rng = np.random.default_rng(7)
    n = 300
    signal = rng.integers(0, 2, size=n)
    noise_1 = rng.normal(size=n)
    noise_2 = rng.normal(size=n)
    X = np.column_stack([signal, noise_1, noise_2]).astype(np.float32)
    y = signal.astype(np.int64)

    analyzer = FeatureInformationAnalyzer(random_state=42)
    ranking = analyzer.marginal_mutual_information(X, y, ["signal", "noise_1", "noise_2"], task="fight")
    assert ranking[0][0] == "signal"


def test_conditional_and_interaction_information_are_numeric() -> None:
    rng = np.random.default_rng(123)
    x1 = rng.normal(size=200)
    x2 = rng.normal(size=200)
    y = (x1 + x2 > 0).astype(np.float32)
    analyzer = FeatureInformationAnalyzer(random_state=0)
    cmi = analyzer.conditional_mutual_information(x1, y, x2)
    ii = analyzer.interaction_information(x1, x2, y)
    assert isinstance(cmi, float)
    assert isinstance(ii, float)
