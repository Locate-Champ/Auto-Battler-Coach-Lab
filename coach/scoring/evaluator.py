from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from coach.artifacts import runtime_outputs_dir
from coach.scoring.features import board_power, derive_traits, squash01
from coach.state import GameState

_log = logging.getLogger(__name__)


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
    _model: Optional[object] = None

    def _load(self) -> object:
        if self._model is not None:
            return self._model

        try:
            import joblib
        except Exception as e:  # pragma: no cover
            raise RuntimeError("joblib is required to load sklearn evaluator models") from e

        self._model = joblib.load(self.model_path)
        return self._model

    def score(self, state: GameState) -> float:
        # Placeholder: integration expects a feature vector consistent with the training script.
        model = self._load()
        if not hasattr(model, "predict_proba"):
            raise RuntimeError("Loaded evaluator model missing predict_proba()")
        raise NotImplementedError("SklearnEvaluator feature extraction is not wired yet")


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
    # Optional: prefer a trained evaluator artifact when present.
    path = runtime_outputs_dir() / "evaluator_linear.json"
    if path.exists():
        try:
            return LinearEvaluator.from_json(path)
        except Exception:
            pass
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
