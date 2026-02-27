"""Trajectory and survival modeling for TFT games."""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Tuple

import numpy as np

_log = logging.getLogger(__name__)


def _wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    p = successes / n
    denominator = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)
    return (center - margin) / denominator, (center + margin) / denominator


class GameTrajectoryModel:
    """Monte Carlo trajectory estimator for top4 and survival probabilities."""

    def __init__(self, transition_model: Any, n_simulations: int = 1000) -> None:
        self.transition_model = transition_model
        self.n_simulations = n_simulations

    def _simulate_to_end(
        self, current_game_state: Dict[str, Any], player_index: int
    ) -> Dict[str, Any]:
        if hasattr(self.transition_model, "simulate_to_end"):
            return self.transition_model.simulate_to_end(
                current_game_state, player_index=player_index
            )
        if callable(self.transition_model):
            return self.transition_model(current_game_state, player_index=player_index)

        # Generic fallback for unit tests or dry runs.
        rng = np.random.default_rng()
        placement = int(rng.integers(1, 9))
        rounds_alive = int(rng.integers(1, 20))
        hp_path = np.maximum(
            0, 100 - np.cumsum(rng.integers(0, 15, size=rounds_alive + 1))
        ).tolist()
        return {
            "placement": placement,
            "rounds_alive": rounds_alive,
            "hp_path": hp_path,
        }

    def compute_top4_probability(
        self, current_game_state: Dict[str, Any], player_index: int
    ) -> Dict[str, Any]:
        """Estimate top4 probability and placement distribution from current state."""
        placements = []
        for _ in range(self.n_simulations):
            outcome = self._simulate_to_end(current_game_state, player_index)
            placements.append(int(outcome.get("placement", 8)))

        placements_arr = np.asarray(placements, dtype=np.int64)
        top4_successes = int((placements_arr <= 4).sum())
        top4_probability = top4_successes / max(1, self.n_simulations)
        ci_low, ci_high = _wilson_interval(top4_successes, self.n_simulations)

        distribution = {
            str(place): float((placements_arr == place).sum() / self.n_simulations)
            for place in range(1, 9)
        }
        return {
            "top4_probability": float(top4_probability),
            "top4_wilson_95": [float(ci_low), float(ci_high)],
            "placement_distribution": distribution,
            "expected_placement": float(placements_arr.mean()),
            "samples": self.n_simulations,
        }

    def compute_hp_trajectory(
        self,
        current_game_state: Dict[str, Any],
        player_index: int,
        n_rounds_forward: int = 10,
    ) -> Dict[str, Any]:
        """Simulate future HP trajectories and return percentile fan-chart bands."""
        hp_matrix = []
        for _ in range(self.n_simulations):
            outcome = self._simulate_to_end(current_game_state, player_index)
            hp_path = list(outcome.get("hp_path", []))
            if not hp_path:
                hp_path = [100.0]
            if len(hp_path) < n_rounds_forward + 1:
                hp_path.extend([hp_path[-1]] * (n_rounds_forward + 1 - len(hp_path)))
            hp_matrix.append(hp_path[: n_rounds_forward + 1])

        hp_arr = np.asarray(hp_matrix, dtype=np.float32)
        rounds = list(range(hp_arr.shape[1]))
        median = np.median(hp_arr, axis=0)
        p10 = np.percentile(hp_arr, 10, axis=0)
        p25 = np.percentile(hp_arr, 25, axis=0)
        p75 = np.percentile(hp_arr, 75, axis=0)
        p90 = np.percentile(hp_arr, 90, axis=0)
        elimination_probability = (hp_arr <= 0).mean(axis=0)

        return {
            "rounds": rounds,
            "median_hp": median.tolist(),
            "p10_hp": p10.tolist(),
            "p25_hp": p25.tolist(),
            "p75_hp": p75.tolist(),
            "p90_hp": p90.tolist(),
            "elimination_probability": elimination_probability.tolist(),
        }

    def survival_analysis(
        self, current_game_state: Dict[str, Any], player_index: int
    ) -> Dict[str, Any]:
        """Compute Kaplan-Meier style survival estimates."""
        elimination_rounds: List[int] = []
        for _ in range(self.n_simulations):
            outcome = self._simulate_to_end(current_game_state, player_index)
            elimination_rounds.append(int(outcome.get("rounds_alive", 0)))

        max_round = max(elimination_rounds) if elimination_rounds else 0
        at_risk = self.n_simulations
        survival = 1.0
        curve: List[Tuple[int, float]] = []
        expected_rounds_remaining = 0.0
        median_survival = None

        for round_idx in range(1, max_round + 1):
            deaths = sum(1 for value in elimination_rounds if value == round_idx)
            if at_risk > 0:
                survival *= 1.0 - (deaths / at_risk)
            at_risk -= deaths
            curve.append((round_idx, float(survival)))
            expected_rounds_remaining += survival
            if median_survival is None and survival <= 0.5:
                median_survival = round_idx

        return {
            "survival_function": [
                {"round": round_idx, "probability": prob} for round_idx, prob in curve
            ],
            "median_survival": median_survival,
            "expected_rounds_remaining": float(expected_rounds_remaining),
        }
