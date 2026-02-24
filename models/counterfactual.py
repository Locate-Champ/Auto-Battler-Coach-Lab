"""Counterfactual what-if analysis using simulator rollouts."""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BoardUnit:
    """Minimal board-unit representation used by the counterfactual engine."""

    champion_id: str
    star_level: int = 1
    items: List[str] = field(default_factory=list)
    position: Optional[int] = None


@dataclass
class BoardState:
    """Board state container for intervention experiments."""

    units: List[BoardUnit]
    traits: Dict[str, int] = field(default_factory=dict)
    augments: List[str] = field(default_factory=list)
    game_state: Dict[str, float] = field(default_factory=dict)


class CounterfactualEngine:
    """Estimate intervention effects via simulation and model-assisted filtering."""

    def __init__(
        self, simulator: Any, model: Optional[Any] = None, n_simulations: int = 200
    ) -> None:
        self.simulator = simulator
        self.model = model
        self.n_simulations = n_simulations

    def _simulate_once(self, board: BoardState, opponent: BoardState) -> Dict[str, float]:
        """Run one rollout and return normalized metrics."""
        if hasattr(self.simulator, "simulate_combat"):
            result = self.simulator.simulate_combat(board, opponent)
        elif callable(self.simulator):
            result = self.simulator(board, opponent)
        else:
            raise ValueError("Simulator must be callable or expose simulate_combat().")

        if isinstance(result, dict):
            win = float(result.get("win", result.get("winner", 0) in (1, True, "player")))
            placement = float(result.get("placement", 4.5))
        elif isinstance(result, bool):
            win = float(result)
            placement = 4.0 if result else 5.0
        else:
            win = float(result == 1)
            placement = 4.0 if result == 1 else 5.0
        return {"win": win, "placement": placement}

    def _estimate_outcome(self, board: BoardState, opponent: BoardState) -> Dict[str, float]:
        wins = 0.0
        placements: List[float] = []
        for _ in range(self.n_simulations):
            outcome = self._simulate_once(board, opponent)
            wins += outcome["win"]
            placements.append(outcome["placement"])
        return {
            "win_rate": wins / self.n_simulations,
            "expected_placement": sum(placements) / max(1, len(placements)),
        }

    def _ate(self, baseline_rate: float, treatment_rate: float) -> Dict[str, float]:
        ate = treatment_rate - baseline_rate
        n = self.n_simulations
        se = math.sqrt(
            (baseline_rate * (1 - baseline_rate) / n) + (treatment_rate * (1 - treatment_rate) / n)
        )
        ci_low = ate - 1.96 * se
        ci_high = ate + 1.96 * se
        return {"ate": ate, "ci_low": ci_low, "ci_high": ci_high}

    def evaluate_swap(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        unit_to_remove: str,
        unit_to_add: str,
        items_to_transfer: bool = True,
    ) -> Dict[str, float]:
        """Compute ATE for replacing one champion with another."""
        baseline = self._estimate_outcome(current_board, opponent_board)
        modified = deepcopy(current_board)
        removed_items: List[str] = []
        for index, unit in enumerate(modified.units):
            if unit.champion_id == unit_to_remove:
                removed_items = unit.items[:] if items_to_transfer else []
                modified.units.pop(index)
                break
        modified.units.append(
            BoardUnit(
                champion_id=unit_to_add,
                star_level=1,
                items=removed_items[:3],
            )
        )
        treatment = self._estimate_outcome(modified, opponent_board)
        ate = self._ate(baseline["win_rate"], treatment["win_rate"])
        return {
            "baseline_win_rate": baseline["win_rate"],
            "treatment_win_rate": treatment["win_rate"],
            "baseline_expected_placement": baseline["expected_placement"],
            "treatment_expected_placement": treatment["expected_placement"],
            "placement_delta": baseline["expected_placement"] - treatment["expected_placement"],
            **ate,
        }

    def evaluate_item_change(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        unit: str,
        item_to_remove: Optional[str],
        item_to_add: Optional[str],
    ) -> Dict[str, float]:
        """Compute ATE for changing one item assignment."""
        baseline = self._estimate_outcome(current_board, opponent_board)
        modified = deepcopy(current_board)
        for board_unit in modified.units:
            if board_unit.champion_id != unit:
                continue
            if item_to_remove and item_to_remove in board_unit.items:
                board_unit.items.remove(item_to_remove)
            if item_to_add:
                board_unit.items.append(item_to_add)
                board_unit.items = board_unit.items[:3]
            break
        treatment = self._estimate_outcome(modified, opponent_board)
        ate = self._ate(baseline["win_rate"], treatment["win_rate"])
        return {
            "baseline_win_rate": baseline["win_rate"],
            "treatment_win_rate": treatment["win_rate"],
            "placement_delta": baseline["expected_placement"] - treatment["expected_placement"],
            **ate,
        }

    def evaluate_position_change(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        unit: str,
        new_position: int,
    ) -> Dict[str, float]:
        """Compute ATE for repositioning one unit."""
        baseline = self._estimate_outcome(current_board, opponent_board)
        modified = deepcopy(current_board)
        for board_unit in modified.units:
            if board_unit.champion_id == unit:
                board_unit.position = new_position
                break
        treatment = self._estimate_outcome(modified, opponent_board)
        ate = self._ate(baseline["win_rate"], treatment["win_rate"])
        return {
            "baseline_win_rate": baseline["win_rate"],
            "treatment_win_rate": treatment["win_rate"],
            "placement_delta": baseline["expected_placement"] - treatment["expected_placement"],
            **ate,
        }

    def _fast_swap_score(self, board: BoardState, opponent: BoardState) -> float:
        if self.model is not None and hasattr(self.model, "predict_win_prob"):
            return float(self.model.predict_win_prob(board, opponent))
        # Heuristic fallback: board value proxy by total champion costs.
        return float(sum(unit.star_level for unit in board.units) + 0.1 * len(board.units))

    def recommend_best_swap(
        self,
        current_board: BoardState,
        opponent_board: BoardState,
        available_champions: List[str],
        top_k: int = 5,
    ) -> List[Dict[str, float]]:
        """Two-stage swap search: model screening then simulation validation."""
        candidates: List[Dict[str, Any]] = []
        for existing in current_board.units:
            for candidate in available_champions:
                if candidate == existing.champion_id:
                    continue
                proposed = deepcopy(current_board)
                for idx, unit in enumerate(proposed.units):
                    if unit.champion_id == existing.champion_id:
                        proposed.units[idx] = BoardUnit(
                            champion_id=candidate,
                            star_level=unit.star_level,
                            items=unit.items[:],
                            position=unit.position,
                        )
                        break
                score = self._fast_swap_score(proposed, opponent_board)
                candidates.append(
                    {
                        "unit_to_remove": existing.champion_id,
                        "unit_to_add": candidate,
                        "fast_score": score,
                    }
                )

        candidates.sort(key=lambda item: item["fast_score"], reverse=True)
        shortlisted = candidates[:20]
        results = []
        for candidate in shortlisted:
            effect = self.evaluate_swap(
                current_board=current_board,
                opponent_board=opponent_board,
                unit_to_remove=candidate["unit_to_remove"],
                unit_to_add=candidate["unit_to_add"],
            )
            results.append({**candidate, **effect})
        results.sort(key=lambda item: item["ate"], reverse=True)
        return results[:top_k]

    def recommend_full_pivot(
        self,
        current_board: BoardState,
        opponent_boards: List[BoardState],
        available_resources: Dict[str, Any],
        personal_performance: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """High-level pivot ranking using available shop/bench champions."""
        shop = available_resources.get("shop", []) or []
        bench = available_resources.get("bench", []) or []
        candidate_units = [str(unit) for unit in list(shop) + list(bench)]
        if not candidate_units:
            return []

        recommendations: List[Dict[str, Any]] = []
        for candidate in candidate_units:
            # Evaluate against an averaged opponent pool.
            win_rates = []
            placement_deltas = []
            for opponent in opponent_boards[:3]:
                swaps = self.recommend_best_swap(
                    current_board=current_board,
                    opponent_board=opponent,
                    available_champions=[candidate],
                    top_k=1,
                )
                if not swaps:
                    continue
                win_rates.append(swaps[0]["treatment_win_rate"])
                placement_deltas.append(swaps[0]["placement_delta"])
            if not win_rates:
                continue
            personal_boost = float(
                personal_performance.get(candidate, {}).get("top4_rate", 0.0) or 0.0
            )
            recommendations.append(
                {
                    "pivot_target": candidate,
                    "expected_win_rate": sum(win_rates) / len(win_rates),
                    "expected_placement_improvement": sum(placement_deltas) / len(placement_deltas),
                    "personal_boost": personal_boost,
                }
            )

        recommendations.sort(
            key=lambda item: (
                item["expected_placement_improvement"] + (0.1 * item["personal_boost"])
            ),
            reverse=True,
        )
        return recommendations[:3]
