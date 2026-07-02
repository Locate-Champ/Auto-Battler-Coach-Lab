"""Contract tests for coach.scoring.evaluator module.

Verifies:
- BoardEvaluator ABC enforcement (cannot instantiate directly)
- All three subclasses instantiate correctly
- RuntimeEvaluator.check_compatibility() returns bool in all paths
- SklearnEvaluator wiring: feature extraction, score mapping, error handling (SKLR-01)
- SklearnEvaluator integration: mock model full path, default_evaluator selection (SKLR-02)
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from coach.scoring.evaluator import (
    BoardEvaluator,
    HeuristicEvaluator,
    LinearEvaluator,
    RuntimeEvaluator,
    SklearnEvaluator,
    _gamestate_to_row,
    _placement_to_score,
    default_evaluator,
)
from coach.state import GameState, PlayerState, UnitState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game_state(
    stage: str = "4-2",
    level: int = 7,
    hp: int = 62,
    gold: int = 30,
    streak: int = 2,
) -> GameState:
    """Build a minimal but realistic GameState for testing."""
    units = (
        UnitState(
            instance_id="u1",
            champion_id="TFT13_Jinx",
            star_level=2,
            items=("TFT_Item_InfinityEdge",),
            position=(0, 0),
        ),
        UnitState(
            instance_id="u2",
            champion_id="TFT13_Vi",
            star_level=1,
            items=(),
            position=(0, 2),
        ),
    )
    return GameState(
        stage=stage,
        player=PlayerState(
            level=level,
            hp=hp,
            gold=gold,
            win_streak=max(streak, 0),
            loss_streak=max(-streak, 0),
        ),
        board=units,
        augments=("TFT9_Augment_CyberneticImplants",),
        traits=(("Marksman", 1), ("Brawler", 1)),
    )


class _MockSklearnModel:
    """Mock model that mimics XGBoost predict() interface."""

    def __init__(self, return_value: float = 3.5) -> None:
        self._return_value = return_value

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.array([self._return_value] * X.shape[0])


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


# -- SklearnEvaluator wiring tests (SKLR-01) --


class TestSklearnEvaluatorWiring:
    def test_gamestate_to_row_has_required_keys(self) -> None:
        row = _gamestate_to_row(_make_game_state())
        # Strict required columns from TFTFeatureEngineer
        for key in ("level", "hp", "gold", "round", "augments"):
            assert key in row, f"Missing required key: {key}"
        # Column-group keys
        assert "streak" in row
        assert "units" in row
        assert "traits" in row

    def test_gamestate_to_row_round_encoding(self) -> None:
        # stage "4-2": stage_num=4, round_in_stage=2
        # base = 4 + (4-2)*7 + (2-1) = 19, stage>=3 so -1 = 18
        row_4_2 = _gamestate_to_row(_make_game_state(stage="4-2"))
        assert row_4_2["round"] == 18

        # stage "2-1": stage_num=2, round_in_stage=1
        # base = 4 + (2-2)*7 + (1-1) = 4, stage<3 so no subtract
        row_2_1 = _gamestate_to_row(_make_game_state(stage="2-1"))
        assert row_2_1["round"] == 4

    def test_placement_to_score_boundaries(self) -> None:
        assert _placement_to_score(1.0) == 1.0
        assert _placement_to_score(8.0) == 0.0
        assert _placement_to_score(4.5) == pytest.approx(0.5, abs=0.01)
        # Clamping: values outside [1, 8]
        assert _placement_to_score(0.5) == 1.0  # clamped at 1.0
        assert _placement_to_score(9.0) == 0.0  # clamped at 0.0

    @patch("coach.scoring.evaluator.SklearnEvaluator._load")
    def test_score_returns_float_in_range(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _MockSklearnModel(return_value=3.5)
        evaluator = SklearnEvaluator(model_path="fake.joblib")
        # Pre-set _model so _load() return value is used as model
        object.__setattr__(evaluator, "_model", _MockSklearnModel(return_value=3.5))

        result = evaluator.score(_make_game_state())

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
        # Expected: (8.0 - 3.5) / 7.0 = 0.6428...
        assert result == pytest.approx(0.6428, abs=0.01)

    @patch("coach.scoring.evaluator.SklearnEvaluator._load")
    def test_score_not_implemented_error_gone(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _MockSklearnModel(return_value=4.0)
        evaluator = SklearnEvaluator(model_path="fake.joblib")
        object.__setattr__(evaluator, "_model", _MockSklearnModel(return_value=4.0))

        # Must not raise NotImplementedError
        try:
            evaluator.score(_make_game_state())
        except NotImplementedError:
            pytest.fail("score() still raises NotImplementedError")

    def test_load_failure_raises_runtime_error(self) -> None:
        with patch("joblib.load", side_effect=FileNotFoundError("not found")):
            evaluator = SklearnEvaluator(model_path="nonexistent.joblib")
            with pytest.raises(RuntimeError, match="Failed to load sklearn model"):
                evaluator.score(_make_game_state())

    @patch("coach.scoring.evaluator.SklearnEvaluator._load")
    def test_feature_extraction_failure_raises_value_error(self, mock_load: MagicMock) -> None:
        mock_load.return_value = _MockSklearnModel()
        evaluator = SklearnEvaluator(model_path="fake.joblib")
        object.__setattr__(evaluator, "_model", _MockSklearnModel())

        # Patch TFTFeatureEngineer.transform to raise
        mock_fe = MagicMock()
        mock_fe.feature_names.return_value = ["f1", "f2"]
        mock_fe.transform.side_effect = KeyError("missing_col")
        object.__setattr__(evaluator, "_feature_engineer", mock_fe)

        with pytest.raises(ValueError, match="Feature extraction failed"):
            evaluator.score(_make_game_state())


# -- SklearnEvaluator integration tests (SKLR-02) --


class TestSklearnEvaluatorIntegration:
    def test_mock_model_full_path(self, tmp_path: object) -> None:
        joblib = pytest.importorskip("joblib")
        model = _MockSklearnModel(return_value=2.0)
        model_file = tmp_path / "test_model.joblib"  # type: ignore[operator]
        joblib.dump(model, str(model_file))

        evaluator = SklearnEvaluator(model_path=str(model_file))
        result = evaluator.score(_make_game_state())

        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0
        # Expected: (8.0 - 2.0) / 7.0 = 0.857...
        assert result == pytest.approx(0.857, abs=0.01)

    def test_default_evaluator_prefers_sklearn(self, tmp_path: object) -> None:
        joblib = pytest.importorskip("joblib")
        model = _MockSklearnModel(return_value=4.0)
        model_file = tmp_path / "evaluator_sklearn.joblib"  # type: ignore[operator]
        joblib.dump(model, str(model_file))

        with patch("coach.scoring.evaluator.runtime_outputs_dir", return_value=tmp_path):
            ev = default_evaluator()

        assert isinstance(ev, SklearnEvaluator)

    def test_default_evaluator_falls_back_when_no_sklearn(self, tmp_path: object) -> None:
        # Write a minimal valid LinearEvaluator JSON
        linear_data = {
            "schema_version": 1,
            "features": [
                "board_power",
                "level",
                "gold",
                "hp",
                "interest",
                "streak",
                "num_traits_2plus",
            ],
            "weights": [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
            "bias": 0.0,
        }
        linear_path = tmp_path / "evaluator_linear.json"  # type: ignore[operator]
        linear_path.write_text(json.dumps(linear_data), encoding="utf-8")

        with patch("coach.scoring.evaluator.runtime_outputs_dir", return_value=tmp_path):
            ev = default_evaluator()

        assert isinstance(ev, LinearEvaluator)

    def test_default_evaluator_logs_selection(
        self, tmp_path: object, caplog: pytest.LogCaptureFixture
    ) -> None:
        with patch("coach.scoring.evaluator.runtime_outputs_dir", return_value=tmp_path):
            with caplog.at_level(logging.INFO, logger="coach.scoring.evaluator"):
                default_evaluator()

        assert "Evaluator selected: HeuristicEvaluator" in caplog.text
