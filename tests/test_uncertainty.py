"""Tests for BayesianPredictor."""

from __future__ import annotations

import pytest

pytest.importorskip("torch")

import torch
import torch.nn as nn

from models.uncertainty import BayesianPredictor


class _DummyModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, 16),
            nn.ReLU(),
            nn.Dropout(p=0.5),
            nn.Linear(16, 10),
        )

    def forward(self, batch: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        x = batch["x"]
        out = self.net(x)
        return {
            "fight_win_logits": out[:, 0],
            "damage_dealt": out[:, 1],
            "placement_logits": out[:, 2:10],
            "board_strength": out[:, 1],
        }


def test_mc_dropout_produces_nonzero_uncertainty() -> None:
    model = _DummyModel()
    predictor = BayesianPredictor(model=model, n_samples=20)
    batch = {"x": torch.randn(8, 4)}
    results = predictor.predict_with_uncertainty(batch)
    assert results["fight_win_total_uncertainty"].shape[0] == 8
    assert torch.any(results["fight_win_total_uncertainty"] > 0)
