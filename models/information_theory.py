"""Information-theoretic feature analysis for TFT models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.metrics import accuracy_score, mean_absolute_error, mutual_info_score
from sklearn.model_selection import train_test_split
import xgboost as xgb

from .train_xgboost import BASE_TREE_PARAMS, _best_xgb_device


def _discretize(values: np.ndarray, bins: int = 10) -> np.ndarray:
    if values.ndim != 1:
        values = values.reshape(-1)
    quantiles = np.linspace(0, 1, bins + 1)
    edges = np.unique(np.quantile(values, quantiles))
    if edges.size < 3:
        return np.zeros_like(values, dtype=np.int64)
    return np.digitize(values, edges[1:-1], right=False).astype(np.int64)


class FeatureInformationAnalyzer:
    """Run MI, redundancy, synergy, and sufficiency analyses."""

    def __init__(self, random_state: int = 42) -> None:
        self.random_state = random_state

    def marginal_mutual_information(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Sequence[str],
        task: str,
    ) -> List[Tuple[str, float]]:
        """Compute feature-wise marginal mutual information."""
        if task in {"fight", "top4"}:
            scores = mutual_info_classif(X, y, random_state=self.random_state)
        else:
            scores = mutual_info_regression(X, y, random_state=self.random_state)
        pairs = [(feature_names[idx], float(value)) for idx, value in enumerate(scores)]
        pairs.sort(key=lambda item: item[1], reverse=True)
        return pairs

    def conditional_mutual_information(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> float:
        """Approximate I(X;Y|Z) using discretized plug-in MI."""
        xd = _discretize(x)
        yd = _discretize(y)
        zd = _discretize(z)
        xz = np.asarray([f"{a}|{b}" for a, b in zip(xd.tolist(), zd.tolist())])
        return float(mutual_info_score(xz, yd) - mutual_info_score(zd, yd))

    def interaction_information(self, xi: np.ndarray, xj: np.ndarray, y: np.ndarray) -> float:
        """Approximate interaction information II(Xi;Xj;Y)."""
        xid = _discretize(xi)
        xjd = _discretize(xj)
        yd = _discretize(y)
        pair = np.asarray([f"{a}|{b}" for a, b in zip(xid.tolist(), xjd.tolist())])
        return float(
            mutual_info_score(pair, yd)
            - mutual_info_score(xid, yd)
            - mutual_info_score(xjd, yd)
            + mutual_info_score(xid, xjd)
        )

    def feature_sufficiency_curve(
        self,
        X: np.ndarray,
        y: np.ndarray,
        ranked_feature_indices: Sequence[int],
        task: str,
        max_features: int = 50,
    ) -> List[Dict[str, float]]:
        """Train models with top-k features and record performance."""
        curve: List[Dict[str, float]] = []
        max_k = min(max_features, len(ranked_feature_indices))
        for k in range(1, max_k + 1):
            selected = ranked_feature_indices[:k]
            X_selected = X[:, selected]
            X_train, X_test, y_train, y_test = train_test_split(
                X_selected,
                y,
                test_size=0.2,
                random_state=self.random_state,
                stratify=y if task in {"fight", "top4"} and len(np.unique(y)) > 1 else None,
            )
            if task in {"fight", "top4"}:
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "binary:logistic",
                        "eval_metric": "auc",
                        "device": _best_xgb_device(),
                        "n_estimators": 120,
                    }
                )
                model = xgb.XGBClassifier(**params)
                model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
                predictions = (model.predict_proba(X_test)[:, 1] >= 0.5).astype(np.int64)
                metric = float(accuracy_score(y_test, predictions))
                curve.append({"n_features": float(k), "accuracy": metric})
            else:
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "reg:squarederror",
                        "eval_metric": "mae",
                        "device": _best_xgb_device(),
                        "n_estimators": 120,
                    }
                )
                model = xgb.XGBRegressor(**params)
                model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
                preds = model.predict(X_test)
                metric = float(mean_absolute_error(y_test, preds))
                curve.append({"n_features": float(k), "mae": metric})
        return curve

    def analyze(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Sequence[str],
        task: str,
        output_path: str | Path = "models/analysis/feature_information.json",
        top_k_pairs: int = 30,
    ) -> Dict[str, Any]:
        """Run the full information-theory analysis and save the report."""
        mi_pairs = self.marginal_mutual_information(X, y, feature_names, task=task)
        top_features = mi_pairs[: top_k_pairs]
        top_indices = [feature_names.index(name) for name, _ in top_features]

        redundant_pairs: List[List[Any]] = []
        synergistic_pairs: List[List[Any]] = []
        for left in range(len(top_indices)):
            for right in range(left + 1, len(top_indices)):
                idx_i = top_indices[left]
                idx_j = top_indices[right]
                cmi = self.conditional_mutual_information(X[:, idx_i], y, X[:, idx_j])
                ii = self.interaction_information(X[:, idx_i], X[:, idx_j], y)
                left_name = feature_names[idx_i]
                right_name = feature_names[idx_j]
                if cmi <= 1e-3:
                    redundant_pairs.append([left_name, right_name, float(cmi)])
                if ii > 0:
                    synergistic_pairs.append([left_name, right_name, float(ii)])

        ranked_indices = [feature_names.index(name) for name, _ in mi_pairs]
        sufficiency = self.feature_sufficiency_curve(
            X=X,
            y=y,
            ranked_feature_indices=ranked_indices,
            task=task,
            max_features=min(50, len(feature_names)),
        )

        report = {
            "marginal_mi": {name: score for name, score in mi_pairs},
            "top_20_features_by_mi": [name for name, _ in mi_pairs[:20]],
            "redundant_pairs": redundant_pairs[:50],
            "synergistic_pairs": synergistic_pairs[:50],
            "sufficiency_curve": sufficiency,
        }

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        return report
