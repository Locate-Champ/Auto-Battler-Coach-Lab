"""Comprehensive evaluation helpers for TFT models."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import xgboost as xgb
from scipy.stats import spearmanr
from sklearn.calibration import calibration_curve
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import KFold, StratifiedKFold

from .data_loader import DataLoader
from .train_xgboost import BASE_TREE_PARAMS, _best_xgb_device


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Compute a Wilson score confidence interval."""
    if n <= 0:
        return 0.0, 0.0
    p = successes / n
    denominator = 1.0 + (z**2) / n
    center = p + (z**2) / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + (z**2) / (4 * n)) / n)
    lower = (center - margin) / denominator
    upper = (center + margin) / denominator
    return lower, upper


def _feature_importance_table(model: Any, feature_names: List[str]) -> List[Tuple[str, float]]:
    raw = model.get_booster().get_score(importance_type="gain")
    table: List[Tuple[str, float]] = []
    for key, value in raw.items():
        if key.startswith("f"):
            index = int(key[1:])
            if 0 <= index < len(feature_names):
                table.append((feature_names[index], float(value)))
    table.sort(key=lambda item: item[1], reverse=True)
    return table


def _classification_metrics(y_true: np.ndarray, y_prob: np.ndarray) -> Dict[str, Any]:
    def _expected_calibration_error(
        y_true_arr: np.ndarray, y_prob_arr: np.ndarray, n_bins: int = 10
    ) -> float:
        if y_true_arr.size == 0:
            return 0.0
        bins = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        for idx in range(n_bins):
            lo = bins[idx]
            hi = bins[idx + 1]
            if idx == n_bins - 1:
                mask = (y_prob_arr >= lo) & (y_prob_arr <= hi)
            else:
                mask = (y_prob_arr >= lo) & (y_prob_arr < hi)
            if not np.any(mask):
                continue
            acc = float(np.mean(y_true_arr[mask]))
            conf = float(np.mean(y_prob_arr[mask]))
            ece += abs(acc - conf) * (float(np.sum(mask)) / float(y_true_arr.size))
        return float(ece)

    y_pred = (y_prob >= 0.5).astype(np.int64)
    accuracy = float(accuracy_score(y_true, y_pred))
    precision = float(precision_score(y_true, y_pred, zero_division=0))
    recall = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    auc = float(roc_auc_score(y_true, y_prob))
    brier = float(np.mean((y_prob - y_true.astype(np.float32)) ** 2))
    ece = _expected_calibration_error(
        y_true.astype(np.float32), y_prob.astype(np.float32), n_bins=10
    )
    predicted_positive = int((y_pred == 1).sum())
    true_positive = int(((y_pred == 1) & (y_true == 1)).sum())
    lower, upper = (
        wilson_interval(true_positive, predicted_positive) if predicted_positive > 0 else (0.0, 0.0)
    )
    cal_true, cal_pred = calibration_curve(y_true, y_prob, n_bins=10)
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auc_roc": auc,
        "brier": brier,
        "ece": ece,
        "precision_wilson_95": [lower, upper],
        "calibration_curve": [
            {"pred": float(p), "true": float(t)} for p, t in zip(cal_pred, cal_true)
        ],
    }


def _regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
    spearman = float(spearmanr(y_true, y_pred).statistic)
    return {"mae": mae, "rmse": rmse, "spearman": spearman}


def _mutual_information(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: List[str],
    task: str,
) -> List[Tuple[str, float]]:
    if task in {"fight", "top4"}:
        scores = mutual_info_classif(X, y, random_state=42)
    else:
        scores = mutual_info_regression(X, y, random_state=42)
    table = list(zip(feature_names, scores.astype(float).tolist()))
    table.sort(key=lambda item: item[1], reverse=True)
    return table


def _cross_validate(
    X: np.ndarray,
    y: np.ndarray,
    task: str,
) -> Dict[str, Any]:
    metrics: List[float] = []
    if task in {"fight", "top4"}:
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        params = dict(BASE_TREE_PARAMS)
        params.update(
            {
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "device": _best_xgb_device(),
                "n_estimators": 200,
            }
        )
        for train_idx, test_idx in splitter.split(X, y):
            model = xgb.XGBClassifier(**params)
            model.fit(
                X[train_idx], y[train_idx], eval_set=[(X[test_idx], y[test_idx])], verbose=False
            )
            probs = model.predict_proba(X[test_idx])[:, 1]
            metrics.append(roc_auc_score(y[test_idx], probs))
        return {
            "cv_metric": "auc_roc",
            "mean": float(np.mean(metrics)),
            "std": float(np.std(metrics)),
        }

    splitter = KFold(n_splits=5, shuffle=True, random_state=42)
    params = dict(BASE_TREE_PARAMS)
    params.update(
        {
            "objective": "reg:squarederror",
            "eval_metric": "mae",
            "device": _best_xgb_device(),
            "n_estimators": 200,
        }
    )
    for train_idx, test_idx in splitter.split(X, y):
        model = xgb.XGBRegressor(**params)
        model.fit(X[train_idx], y[train_idx], eval_set=[(X[test_idx], y[test_idx])], verbose=False)
        preds = model.predict(X[test_idx])
        metrics.append(mean_absolute_error(y[test_idx], preds))
    return {"cv_metric": "mae", "mean": float(np.mean(metrics)), "std": float(np.std(metrics))}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate TFT XGBoost models.")
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--task", type=str, choices=("fight", "top4", "placement"), required=True)
    parser.add_argument(
        "--model", type=str, required=True, help="Path to trained XGBoost .json model"
    )
    parser.add_argument("--output", type=str, default="models/checkpoints/evaluation_report.json")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    loader = DataLoader(args.data)
    feature_names = loader.feature_engineer.feature_names()

    if args.task == "fight":
        X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(
            test_size=args.test_size, seed=args.seed
        )
        model = xgb.XGBClassifier()
        model.load_model(args.model)
        probabilities = model.predict_proba(X_test)[:, 1]
        primary = _classification_metrics(y_test, probabilities)
        full_X = np.vstack([X_train, X_test])
        full_y = np.concatenate([y_train, y_test])
    elif args.task == "top4":
        X_train, X_test, y_train, y_test = loader.load_top4_classification_data(
            test_size=args.test_size, seed=args.seed
        )
        model = xgb.XGBClassifier()
        model.load_model(args.model)
        probabilities = model.predict_proba(X_test)[:, 1]
        primary = _classification_metrics(y_test, probabilities)
        full_X = np.vstack([X_train, X_test])
        full_y = np.concatenate([y_train, y_test])
    else:
        X_train, X_test, y_train, y_test = loader.load_placement_prediction_data(
            test_size=args.test_size, seed=args.seed
        )
        model = xgb.XGBRegressor()
        model.load_model(args.model)
        predictions = model.predict(X_test)
        primary = _regression_metrics(y_test, predictions)
        full_X = np.vstack([X_train, X_test])
        full_y = np.concatenate([y_train, y_test])

    feature_importance = _feature_importance_table(model, feature_names)
    mutual_info = _mutual_information(full_X, full_y, feature_names, task=args.task)
    cv_summary = _cross_validate(full_X, full_y, task=args.task)

    report = {
        "task": args.task,
        "model_path": args.model,
        "primary_metrics": primary,
        "feature_importance_top20": feature_importance[:20],
        "mutual_information_top20": mutual_info[:20],
        "cross_validation": cv_summary,
        "feature_count": len(feature_names),
        "test_rows": int(X_test.shape[0]),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"Saved evaluation report -> {output_path}")


if __name__ == "__main__":
    main()
