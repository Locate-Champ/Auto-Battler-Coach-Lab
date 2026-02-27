"""Contract tests for coach.scoring.evaluator module.

Verifies:
- BoardEvaluator ABC enforcement (cannot instantiate directly)
- All three subclasses instantiate correctly
- RuntimeEvaluator.check_compatibility() returns bool in all paths
"""

from __future__ import annotations

import pytest

from coach.scoring.evaluator import (
    BoardEvaluator,
    HeuristicEvaluator,
    LinearEvaluator,
    RuntimeEvaluator,
    SklearnEvaluator,
)

# -- BoardEvaluator ABC tests (TYPE-02) --


class TestBoardEvaluatorABC:
    def test_board_evaluator_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            BoardEvaluator()

    def test_heuristic_evaluator_instantiates(self) -> None:
        evaluator = HeuristicEvaluator()
        assert isinstance(evaluator, BoardEvaluator)

    def test_sklearn_evaluator_instantiates(self) -> None:
        evaluator = SklearnEvaluator(model_path="dummy")
        assert isinstance(evaluator, BoardEvaluator)

    def test_linear_evaluator_is_board_evaluator(self) -> None:
        evaluator = LinearEvaluator(feature_order=("a",), weights=(1.0,), bias=0.0)
        assert isinstance(evaluator, BoardEvaluator)


# -- check_compatibility() tests (TYPE-01) --


class TestCheckCompatibility:
    def test_check_compatibility_returns_true_for_valid_evaluator(self) -> None:
        rt = RuntimeEvaluator(evaluator=HeuristicEvaluator())
        assert rt.check_compatibility() is True

    def test_check_compatibility_returns_false_for_none(self) -> None:
        rt = RuntimeEvaluator(evaluator=None)
        assert rt.check_compatibility() is False

    def test_check_compatibility_returns_false_for_wrong_type(self) -> None:
        rt = RuntimeEvaluator(evaluator="not_an_evaluator")
        assert rt.check_compatibility() is False

    def test_check_compatibility_return_type_is_bool(self) -> None:
        rt_valid = RuntimeEvaluator(evaluator=HeuristicEvaluator())
        result_true = rt_valid.check_compatibility()
        assert type(result_true) is bool

        rt_none = RuntimeEvaluator(evaluator=None)
        result_false = rt_none.check_compatibility()
        assert type(result_false) is bool
