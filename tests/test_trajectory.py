"""Tests for GameTrajectoryModel."""

from __future__ import annotations

import numpy as np

from models.trajectory import GameTrajectoryModel


class _MockTransitionModel:
    def __init__(self) -> None:
        self.rng = np.random.default_rng(42)

    def simulate_to_end(self, _state: dict, player_index: int = 0) -> dict:
        placement = int(self.rng.integers(1, 9))
        rounds_alive = int(self.rng.integers(1, 12))
        hp_path = np.maximum(
            0, 100 - np.cumsum(self.rng.integers(0, 20, size=rounds_alive + 1))
        ).tolist()
        return {
            "placement": placement,
            "rounds_alive": rounds_alive,
            "hp_path": hp_path,
            "player_index": player_index,
        }


def test_top4_probability_outputs_distribution() -> None:
    model = GameTrajectoryModel(transition_model=_MockTransitionModel(), n_simulations=50)
    result = model.compute_top4_probability(current_game_state={}, player_index=0)
    assert 0.0 <= result["top4_probability"] <= 1.0
    assert len(result["placement_distribution"]) == 8


def test_survival_analysis_has_monotonic_curve() -> None:
    model = GameTrajectoryModel(transition_model=_MockTransitionModel(), n_simulations=50)
    result = model.survival_analysis(current_game_state={}, player_index=0)
    probabilities = [point["probability"] for point in result["survival_function"]]
    assert all(
        probabilities[idx] >= probabilities[idx + 1] for idx in range(len(probabilities) - 1)
    )
