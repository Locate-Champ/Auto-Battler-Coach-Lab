"""Train XGBoost models for TFT prediction tasks."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    roc_auc_score,
)
import xgboost as xgb

from .data_loader import DataLoader
from .feature_engineering import FeatureConfig, TFTFeatureEngineer


BASE_TREE_PARAMS = {
    "max_depth": 8,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "tree_method": "hist",
    "random_state": 42,
}


def _best_xgb_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _train_with_fallback(
    model_class: Any,
    params: Dict[str, Any],
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_valid: np.ndarray,
    y_valid: np.ndarray,
) -> Any:
    """Train XGBoost model and gracefully fallback to CPU when needed."""
    model = model_class(**params)
    try:
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_valid, y_valid)],
            verbose=False,
        )
        return model
    except xgb.core.XGBoostError:
        fallback = dict(params)
        fallback["device"] = "cpu"
        model = model_class(**fallback)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_valid, y_valid)],
            verbose=False,
        )
        return model


def _extract_feature_importance(model: Any, feature_names: List[str]) -> List[Tuple[str, float]]:
    booster = model.get_booster()
    raw = booster.get_score(importance_type="gain")
    scored: List[Tuple[str, float]] = []
    for key, value in raw.items():
        if key.startswith("f"):
            index = int(key[1:])
            if 0 <= index < len(feature_names):
                scored.append((feature_names[index], float(value)))
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def _save_feature_chart(importances: List[Tuple[str, float]], output_path: Path) -> None:
    top = importances[:20]
    if not top:
        return
    labels = [name for name, _ in top][::-1]
    values = [value for _, value in top][::-1]
    plt.figure(figsize=(12, 8))
    plt.barh(labels, values)
    plt.xlabel("Gain")
    plt.title("Top 20 XGBoost Features")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def _evaluate_classification(task: str, model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(np.int64)
    metrics = {
        "task": task,
        "accuracy": float(accuracy_score(y_test, predictions)),
        "auc_roc": float(roc_auc_score(y_test, probabilities)),
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "classification_report": classification_report(y_test, predictions, output_dict=True, zero_division=0),
    }
    print(f"[{task}] accuracy={metrics['accuracy']:.4f} auc={metrics['auc_roc']:.4f}")
    print(f"[{task}] confusion_matrix={metrics['confusion_matrix']}")
    return metrics


def _evaluate_regression(model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
    predictions = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, predictions))
    print(f"[placement] mae={mae:.4f}")
    return {"task": "placement", "mae": mae}


def _run_ablation(
    args: argparse.Namespace,
    baseline_metric: float,
    is_higher_better: bool,
) -> Dict[str, float]:
    toggles = [
        "use_composition",
        "use_economy",
        "use_traits",
        "use_items",
        "use_augments",
        "use_matchup",
        "use_personal_weights",
    ]
    deltas: Dict[str, float] = {}
    for toggle in toggles:
        config = FeatureConfig()
        setattr(config, toggle, False)
        loader = DataLoader(args.data, feature_engineer=TFTFeatureEngineer(config=config))
        if args.task == "fight":
            X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(test_size=args.test_size, seed=args.seed)
            params = dict(BASE_TREE_PARAMS)
            params.update(
                {
                    "objective": "binary:logistic",
                    "eval_metric": "auc",
                    "device": _best_xgb_device(),
                    "n_estimators": min(200, args.n_estimators),
                }
            )
            model = _train_with_fallback(xgb.XGBClassifier, params, X_train, y_train, X_test, y_test)
            metric = accuracy_score(y_test, (model.predict_proba(X_test)[:, 1] >= 0.5).astype(np.int64))
        elif args.task == "top4":
            X_train, X_test, y_train, y_test = loader.load_top4_classification_data(test_size=args.test_size, seed=args.seed)
            params = dict(BASE_TREE_PARAMS)
            params.update(
                {
                    "objective": "binary:logistic",
                    "eval_metric": "auc",
                    "device": _best_xgb_device(),
                    "n_estimators": min(200, args.n_estimators),
                }
            )
            model = _train_with_fallback(xgb.XGBClassifier, params, X_train, y_train, X_test, y_test)
            metric = accuracy_score(y_test, (model.predict_proba(X_test)[:, 1] >= 0.5).astype(np.int64))
        else:
            X_train, X_test, y_train, y_test = loader.load_placement_prediction_data(test_size=args.test_size, seed=args.seed)
            params = dict(BASE_TREE_PARAMS)
            params.update(
                {
                    "objective": "reg:squarederror",
                    "eval_metric": "mae",
                    "device": _best_xgb_device(),
                    "n_estimators": min(200, args.n_estimators),
                }
            )
            model = _train_with_fallback(xgb.XGBRegressor, params, X_train, y_train, X_test, y_test)
            metric = mean_absolute_error(y_test, model.predict(X_test))

        delta = float(metric - baseline_metric) if is_higher_better else float(baseline_metric - metric)
        deltas[toggle] = delta
        print(f"[ablation] disable={toggle} metric={metric:.4f} delta={delta:.4f}")
    return deltas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost TFT models.")
    parser.add_argument("--data", type=str, required=True, help="Directory containing parquet/jsonl chunks")
    parser.add_argument("--task", type=str, choices=("fight", "top4", "placement"), required=True)
    parser.add_argument("--output", type=str, default="models/checkpoints", help="Output directory")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=500)
    parser.add_argument("--ablation", action="store_true", help="Run feature-group ablation study")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    loader = DataLoader(args.data)
    feature_names = loader.feature_engineer.feature_names()

    if args.task == "fight":
        X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(test_size=args.test_size, seed=args.seed)
        params = dict(BASE_TREE_PARAMS)
        params.update(
            {
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "device": _best_xgb_device(),
                "n_estimators": args.n_estimators,
            }
        )
        model = _train_with_fallback(xgb.XGBClassifier, params, X_train, y_train, X_test, y_test)
        metrics = _evaluate_classification("fight", model, X_test, y_test)
        baseline_metric = metrics["accuracy"]
        is_higher_better = True
    elif args.task == "top4":
        X_train, X_test, y_train, y_test = loader.load_top4_classification_data(test_size=args.test_size, seed=args.seed)
        params = dict(BASE_TREE_PARAMS)
        params.update(
            {
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "device": _best_xgb_device(),
                "n_estimators": args.n_estimators,
            }
        )
        model = _train_with_fallback(xgb.XGBClassifier, params, X_train, y_train, X_test, y_test)
        metrics = _evaluate_classification("top4", model, X_test, y_test)
        baseline_metric = metrics["accuracy"]
        is_higher_better = True
    else:
        X_train, X_test, y_train, y_test = loader.load_placement_prediction_data(test_size=args.test_size, seed=args.seed)
        params = dict(BASE_TREE_PARAMS)
        params.update(
            {
                "objective": "reg:squarederror",
                "eval_metric": "mae",
                "device": _best_xgb_device(),
                "n_estimators": args.n_estimators,
            }
        )
        model = _train_with_fallback(xgb.XGBRegressor, params, X_train, y_train, X_test, y_test)
        metrics = _evaluate_regression(model, X_test, y_test)
        baseline_metric = metrics["mae"]
        is_higher_better = False

    importances = _extract_feature_importance(model, feature_names)
    print("Top 20 feature importances:")
    for feature, score in importances[:20]:
        print(f"  {feature}: {score:.4f}")

    model_path = output_dir / f"{args.task}_xgboost.json"
    model.save_model(model_path)
    chart_path = output_dir / f"{args.task}_feature_importance.png"
    _save_feature_chart(importances, chart_path)
    print(f"Saved model -> {model_path}")
    print(f"Saved chart -> {chart_path}")

    report = {
        "task": args.task,
        "params": params,
        "metrics": metrics,
        "top_features": importances[:20],
        "feature_count": len(feature_names),
    }

    if args.ablation:
        report["ablation"] = _run_ablation(args, baseline_metric=baseline_metric, is_higher_better=is_higher_better)

    report_path = output_dir / f"{args.task}_training_report.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"Saved report -> {report_path}")


if __name__ == "__main__":
    main()
