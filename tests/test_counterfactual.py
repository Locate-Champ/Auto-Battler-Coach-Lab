"""Tests for CounterfactualEngine."""

from __future__ import annotations

from models.counterfactual import BoardState, BoardUnit, CounterfactualEngine


class _MockSimulator:
    def simulate_combat(self, board: BoardState, opponent: BoardState) -> dict:
        own_power = sum(unit.star_level for unit in board.units)
        opp_power = sum(unit.star_level for unit in opponent.units)
        return {
            "win": float(own_power >= opp_power),
            "placement": 3 if own_power >= opp_power else 6,
        }


def _board(*champs: tuple[str, int]) -> BoardState:
    return BoardState(
        units=[BoardUnit(champion_id=name, star_level=stars) for name, stars in champs]
    )


def test_swap_returns_positive_ate_for_stronger_unit() -> None:
    engine = CounterfactualEngine(simulator=_MockSimulator(), n_simulations=30)
    current = _board(("weak", 1), ("tank", 1))
    opponent = _board(("enemy", 2), ("enemy2", 1))
    result = engine.evaluate_swap(current, opponent, unit_to_remove="weak", unit_to_add="carry")
    assert "ate" in result
    assert result["baseline_win_rate"] <= result["treatment_win_rate"]


def test_recommend_best_swap_returns_ranked_results() -> None:
    engine = CounterfactualEngine(simulator=_MockSimulator(), n_simulations=10)
    current = _board(("a", 1), ("b", 1))
    opponent = _board(("enemy", 2))
    recs = engine.recommend_best_swap(
        current, opponent, available_champions=["carry", "tank"], top_k=2
    )
    assert len(recs) <= 2
