from __future__ import annotations

import json
import logging
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from coach.artifacts import runtime_outputs_dir
from coach.scoring.features import board_power, derive_traits, squash01
from coach.state import GameState

_log = logging.getLogger(__name__)


def _round_num_from_stage(stage: str) -> int:
    """Compute absolute round number from a stage string like '4-2'.

    Replicates the logic in :func:`coach.coach._round_num_from_stage` to avoid
    a circular import.
    """
    try:
        stage_num = int(stage.split("-")[0])
        round_in_stage = int(stage.split("-")[1])
    except (ValueError, IndexError):
        return 4

    if stage_num <= 1:
        return max(0, round_in_stage - 1)

    base = 4 + (stage_num - 2) * 7 + (round_in_stage - 1)
    if stage_num >= 3:
        base -= 1
    return max(0, int(base))


def _gamestate_to_row(state: GameState) -> dict[str, Any]:
    """Convert a *GameState* into the dict format ``TFTFeatureEngineer.transform()`` expects."""
    return {
        "level": state.player.level,
        "hp": state.player.hp,
        "gold": state.player.gold,
        "round": _round_num_from_stage(state.stage),
        "streak": state.player.streak,
        "augments": list(state.augments),
        "units": [
            {
                "champion_id": u.champion_id,
                "star_level": u.star_level,
                "items": list(u.items),
                "position": u.position,
            }
            for u in state.board
        ],
        "traits": dict(state.traits) if state.traits else {},
    }


def _placement_to_score(placement: float) -> float:
    """Map a predicted placement (1-8) to a 0-1 board strength score.

    Placement 1 (best) maps to 1.0, placement 8 (worst) maps to 0.0.
    Values outside [1, 8] are clamped.
    """
    return max(0.0, min(1.0, (8.0 - placement) / 7.0))


class BoardEvaluator(ABC):
    @abstractmethod
    def score(self, state: GameState) -> float:
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class HeuristicEvaluator(BoardEvaluator):
    # Midpoint is roughly the board_power where we consider a board "solid".
    midpoint: float = 28.0
    sharpness: float = 0.12

    def score(self, state: GameState) -> float:
        power = board_power(state.board)
        traits = derive_traits(state.board)

        # Reward hitting multiple traits at 2+.
        trait_bonus = 0.0
        for _, count in traits.items():
            if count >= 2:
                trait_bonus += 0.8
            if count >= 4:
                trait_bonus += 0.4

        # Slight late-game bonus for higher levels.
        lvl_bonus = max(state.player.level - 6, 0) * 0.75 if state.stage_number >= 4 else 0.0

        raw = power + trait_bonus + lvl_bonus
        # Stage shifts the midpoint upward as boards scale.
        stage_midpoint = self.midpoint + max(state.stage_number - 2, 0) * 3.0
        return squash01(raw, midpoint=stage_midpoint, sharpness=self.sharpness)


@dataclass(frozen=True, slots=True)
class SklearnEvaluator(BoardEvaluator):
    model_path: str
    _model: Optional[object] = field(default=None, repr=False)
    _feature_engineer: Optional[object] = field(default=None, repr=False)

    def _load(self) -> object:
        if self._model is not None:
            return self._model

        try:
            import joblib
        except (ImportError, OSError) as e:  # pragma: no cover
            raise RuntimeError("joblib is required to load sklearn evaluator models") from e

        try:
            model = joblib.load(self.model_path)
        except (
            OSError,
            EOFError,
            ValueError,
            KeyError,
            AttributeError,
            ImportError,
            pickle.UnpicklingError,
        ) as e:
            raise RuntimeError(f"Failed to load sklearn model from {self.model_path}: {e}") from e

        object.__setattr__(self, "_model", model)
        return model

    def score(self, state: GameState) -> float:
        model = self._load()

        # Lazily initialise the feature engineer on first call.
        if self._feature_engineer is None:
            from models.feature_engineering import TFTFeatureEngineer

            fe = TFTFeatureEngineer()
            if len(fe.feature_names()) == 0:
                raise RuntimeError(
                    "TFTFeatureEngineer produced no features -- combat_data.json may be missing"
                )
            object.__setattr__(self, "_feature_engineer", fe)

        fe = self._feature_engineer
        row = _gamestate_to_row(state)

        try:
            features = fe.transform(row)  # type: ignore[union-attr]
        except (TypeError, ValueError, KeyError, AttributeError) as e:
            raise ValueError(
                f"Feature extraction failed: {e}. "
                f"GameState stage={state.stage}, board_size={len(state.board)}"
            ) from e

        features = features.reshape(1, -1)
        placement = float(model.predict(features)[0])
        return _placement_to_score(placement)


@dataclass(frozen=True, slots=True)
class LinearEvaluator(BoardEvaluator):
    feature_order: tuple[str, ...]
    weights: tuple[float, ...]
    bias: float

    @staticmethod
    def from_json(path: str | Path) -> "LinearEvaluator":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if int(data.get("schema_version") or 0) != 1:
            raise RuntimeError("Unsupported evaluator schema_version (expected 1)")
        feats = tuple(data["features"])
        w = tuple(float(x) for x in data["weights"])
        b = float(data.get("bias", 0.0))
        expected = (
            "board_power",
            "level",
            "gold",
            "hp",
            "interest",
            "streak",
            "num_traits_2plus",
        )
        if feats != expected:
            raise RuntimeError(f"Evaluator features mismatch. expected={expected} got={feats}")
        return LinearEvaluator(feature_order=feats, weights=w, bias=b)

    def _features(self, state: GameState) -> dict[str, float]:
        traits = derive_traits(state.board)
        num_2plus = sum(1 for _, c in traits.items() if c >= 2)
        return {
            "board_power": float(board_power(state.board)),
            "level": float(state.player.level),
            "gold": float(state.player.gold),
            "hp": float(state.player.hp),
            "interest": float(state.player.interest),
            "streak": float(state.player.streak),
            "num_traits_2plus": float(num_2plus),
        }

    def score(self, state: GameState) -> float:
        feats = self._features(state)
        z = self.bias
        for name, w in zip(self.feature_order, self.weights, strict=False):
            z += w * float(feats.get(name, 0.0))
        # Convert to [0,1] like a probability-like score.
        return squash01(z, midpoint=0.0, sharpness=1.0)


def default_evaluator() -> BoardEvaluator:
    """Select the best available evaluator: Sklearn > Linear > Heuristic."""
    # 1. Try SklearnEvaluator (highest priority).
    sklearn_path = runtime_outputs_dir() / "evaluator_sklearn.joblib"
    if sklearn_path.exists():
        try:
            evaluator = SklearnEvaluator(model_path=str(sklearn_path))
            evaluator._load()  # validate the model loads
            _log.info("Evaluator selected: SklearnEvaluator from %s", sklearn_path)
            return evaluator
        except (OSError, ValueError, KeyError, RuntimeError):
            _log.warning(
                "SklearnEvaluator failed to load from %s, trying next",
                sklearn_path,
                exc_info=True,
            )

    # 2. Try LinearEvaluator.
    linear_path = runtime_outputs_dir() / "evaluator_linear.json"
    if linear_path.exists():
        try:
            evaluator = LinearEvaluator.from_json(linear_path)
            _log.info("Evaluator selected: LinearEvaluator from %s", linear_path)
            return evaluator
        except (OSError, ValueError, KeyError, RuntimeError):
            _log.warning(
                "LinearEvaluator failed to load from %s, trying next",
                linear_path,
                exc_info=True,
            )

    # 3. Fallback to heuristic.
    _log.info("Evaluator selected: HeuristicEvaluator (no trained model found)")
    return HeuristicEvaluator()


@dataclass(frozen=True, slots=True)
class RuntimeEvaluator:
    evaluator: BoardEvaluator

    def check_compatibility(self) -> bool:
        """Return True if the evaluator is a valid BoardEvaluator, False otherwise."""
        if self.evaluator is None:
            _log.debug("check_compatibility: evaluator is None")
            return False
        if not isinstance(self.evaluator, BoardEvaluator):
            _log.debug(
                "check_compatibility: evaluator is %s, not a BoardEvaluator",
                type(self.evaluator).__name__,
            )
            return False
        return True

    def predict_board_strength(self, state: GameState) -> float:
        return float(self.evaluator.score(state))

    def predict_fight_prob(self, state: GameState, opponent: GameState) -> float:
        # Fast, deterministic proxy: sigmoid of relative board strength.
        a = float(self.evaluator.score(state))
        b = float(self.evaluator.score(opponent))
        diff = a - b
        return squash01(diff, midpoint=0.0, sharpness=4.0)
