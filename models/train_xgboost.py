"""Train XGBoost models for TFT prediction tasks."""

from __future__ import annotations

import argparse
import gc
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    roc_auc_score,
)

from .data_loader import DataLoader
from .feature_engineering import FeatureConfig, TFTFeatureEngineer

_log = logging.getLogger(__name__)

BASE_TREE_PARAMS = {
    "max_depth": 0,
    "learning_rate": 0.05,
    "n_estimators": 300,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 5,
    "reg_alpha": 0.1,
    "reg_lambda": 1.0,
    "tree_method": "hist",
    "grow_policy": "lossguide",
    "max_leaves": 256,
    "random_state": 42,
}


def _best_xgb_device() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        _log.info("torch not available; XGBoost will use CPU device")
    return "cpu"


def _train_with_fallback(
    model_class: Any,
    params: Dict[str, Any],
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_valid: np.ndarray,
    y_valid: np.ndarray,
    *,
    early_stopping_rounds: Optional[int] = None,
) -> Any:
    """Train XGBoost model and gracefully fallback to CPU when needed."""
    merged = dict(params)
    if early_stopping_rounds is not None:
        merged["early_stopping_rounds"] = early_stopping_rounds
    model = model_class(**merged)
    try:
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_valid, y_valid)],
            verbose=False,
        )
        return model
    except xgb.core.XGBoostError:
        _log.warning(
            "XGBoost GPU training failed; falling back to CPU device. "
            "This may significantly increase training time."
        )
        fallback = dict(merged)
        fallback["device"] = "cpu"
        model = model_class(**fallback)
        model.fit(
            X_train,
            y_train,
            eval_set=[(X_valid, y_valid)],
            verbose=False,
        )
        return model


def _train_booster_with_fallback(
    params: Dict[str, Any],
    dtrain: xgb.DMatrix,
    dtest: xgb.DMatrix,
    num_boost_round: int,
    early_stopping_rounds: Optional[int],
) -> xgb.Booster:
    """Train xgb.train booster with graceful CPU fallback."""
    try:
        return xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=num_boost_round,
            evals=[(dtrain, "train"), (dtest, "test")],
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=False,
        )
    except xgb.core.XGBoostError:
        _log.warning(
            "XGBoost GPU booster training failed; falling back to CPU device. "
            "This may significantly increase training time."
        )
        fallback = dict(params)
        fallback["device"] = "cpu"
        return xgb.train(
            params=fallback,
            dtrain=dtrain,
            num_boost_round=num_boost_round,
            evals=[(dtrain, "train"), (dtest, "test")],
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=False,
        )


def _as_booster(model: Any) -> xgb.Booster:
    if isinstance(model, xgb.Booster):
        return model
    return model.get_booster()


def _extract_feature_importance(model: Any, feature_names: List[str]) -> List[Tuple[str, float]]:
    booster = _as_booster(model)
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


def _safe_auc(y_true: np.ndarray, y_prob: np.ndarray) -> Optional[float]:
    if y_true.size == 0:
        return None
    try:
        return float(roc_auc_score(y_true, y_prob))
    except ValueError:
        return None


def _evaluate_classification(
    task: str, model: Any, X_test: np.ndarray, y_test: np.ndarray
) -> Dict[str, Any]:
    probabilities = model.predict_proba(X_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(np.int64)
    auc_roc = _safe_auc(y_test, probabilities)
    metrics = {
        "task": task,
        "accuracy": float(accuracy_score(y_test, predictions)),
        "auc_roc": auc_roc,
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "classification_report": classification_report(
            y_test, predictions, output_dict=True, zero_division=0
        ),
    }
    auc_display = f"{auc_roc:.4f}" if auc_roc is not None else "n/a"
    _log.info("[%s] accuracy=%.4f auc=%s", task, metrics["accuracy"], auc_display)
    _log.info("[%s] confusion_matrix=%s", task, metrics["confusion_matrix"])
    return metrics


def _evaluate_regression(model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
    predictions = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, predictions))
    _log.info("[placement] mae=%.4f", mae)
    return {"task": "placement", "mae": mae}


def _predict_booster(booster: xgb.Booster, matrix: xgb.DMatrix) -> np.ndarray:
    best_iteration = getattr(booster, "best_iteration", -1)
    if best_iteration is None or int(best_iteration) < 0:
        return booster.predict(matrix)
    return booster.predict(matrix, iteration_range=(0, int(best_iteration) + 1))


def _evaluate_booster_classification(
    task: str, booster: xgb.Booster, dtest: xgb.DMatrix
) -> Dict[str, Any]:
    probabilities = _predict_booster(booster, dtest)
    y_test = dtest.get_label().astype(np.int64)
    predictions = (probabilities >= 0.5).astype(np.int64)
    auc_roc = _safe_auc(y_test, probabilities)
    metrics = {
        "task": task,
        "accuracy": float(accuracy_score(y_test, predictions)),
        "auc_roc": auc_roc,
        "confusion_matrix": confusion_matrix(y_test, predictions).tolist(),
        "classification_report": classification_report(
            y_test, predictions, output_dict=True, zero_division=0
        ),
    }
    auc_display = f"{auc_roc:.4f}" if auc_roc is not None else "n/a"
    _log.info("[%s] accuracy=%.4f auc=%s", task, metrics["accuracy"], auc_display)
    _log.info("[%s] confusion_matrix=%s", task, metrics["confusion_matrix"])
    return metrics


def _evaluate_booster_regression(booster: xgb.Booster, dtest: xgb.DMatrix) -> Dict[str, Any]:
    y_test = dtest.get_label()
    predictions = _predict_booster(booster, dtest)
    mae = float(mean_absolute_error(y_test, predictions))
    _log.info("[placement] mae=%.4f", mae)
    return {"task": "placement", "mae": mae}


def _split_for_example(
    game_id: Optional[int],
    example_index: int,
    *,
    split_seed: int,
    test_size: float,
) -> str:
    raw = game_id if game_id is not None else ~example_index
    # Knuth multiplicative hash — fast, good distribution for sequential ints
    bucket = (((raw ^ split_seed) * 2654435761) & 0xFFFFFFFF) / 0xFFFFFFFF
    return "train" if bucket < (1.0 - test_size) else "test"


def _iter_fight_examples(
    loader: DataLoader,
    *,
    row_batch_size: int,
    max_rows: Optional[int],
) -> Iterator[Tuple[Dict[str, Any], float, Optional[int]]]:
    """Yield leak-safe temporal fight examples."""
    seen_rows = 0
    current_game_id: Optional[int] = None
    prev_rows_by_player: Dict[int, Dict[str, Any]] = {}
    for row in loader.iter_raw(row_batch_size=row_batch_size):
        seen_rows += 1
        if max_rows is not None and seen_rows > max_rows:
            break

        game_id = row.get("game_id")
        player_id = row.get("player_id")
        round_num = row.get("round")
        if game_id is None or player_id is None or round_num is None:
            continue

        game_id_int = int(game_id)
        if current_game_id is None or game_id_int != current_game_id:
            current_game_id = game_id_int
            prev_rows_by_player = {}

        player_id_int = int(player_id)
        round_int = int(round_num)
        prev_row = prev_rows_by_player.get(player_id_int)
        if prev_row is not None:
            prev_round = int(prev_row.get("round", -1))
            if round_int > prev_round:
                next_result = loader._infer_binary_fight_result(row)  # noqa: SLF001
                if next_result is not None:
                    yield prev_row, float(next_result), game_id_int
        prev_rows_by_player[player_id_int] = row


def _iter_labeled_examples(
    loader: DataLoader,
    task: str,
    *,
    row_batch_size: int,
    max_rows: Optional[int],
) -> Iterator[Tuple[Dict[str, Any], float, Optional[int]]]:
    if task == "fight":
        yield from _iter_fight_examples(loader, row_batch_size=row_batch_size, max_rows=max_rows)
        return

    seen_rows = 0
    for row in loader.iter_raw(row_batch_size=row_batch_size):
        seen_rows += 1
        if max_rows is not None and seen_rows > max_rows:
            break

        placement_value = row.get("placement")
        if placement_value is None:
            continue
        placement = int(placement_value)
        if placement <= 0:
            continue

        if task == "top4":
            label = 1.0 if placement <= 4 else 0.0
        else:
            label = float(placement)

        game_id = row.get("game_id")
        game_id_int = int(game_id) if game_id is not None else None
        yield row, label, game_id_int


def _scan_split_stats(
    loader: DataLoader,
    task: str,
    *,
    test_size: float,
    split_seed: int,
    row_batch_size: int,
    max_rows: Optional[int],
) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "train_examples": 0,
        "test_examples": 0,
    }
    if task in {"fight", "top4"}:
        stats.update(
            {
                "train_positive": 0,
                "test_positive": 0,
            }
        )

    for example_index, (_, label, game_id) in enumerate(
        _iter_labeled_examples(
            loader,
            task,
            row_batch_size=row_batch_size,
            max_rows=max_rows,
        )
    ):
        split = _split_for_example(
            game_id,
            example_index,
            split_seed=split_seed,
            test_size=test_size,
        )
        stats[f"{split}_examples"] += 1
        if task in {"fight", "top4"} and int(label) == 1:
            stats[f"{split}_positive"] += 1

    if task in {"fight", "top4"}:
        for split in ("train", "test"):
            total = int(stats[f"{split}_examples"])
            positives = int(stats[f"{split}_positive"])
            stats[f"{split}_positive_rate"] = float(positives / total) if total > 0 else 0.0
    return stats


class _ExternalMemoryDataIter(xgb.DataIter):
    """XGBoost DataIter that streams TFT rows and caches pages on disk."""

    def __init__(
        self,
        loader: DataLoader,
        task: str,
        split: str,
        *,
        split_seed: int,
        test_size: float,
        row_batch_size: int,
        max_rows: Optional[int],
        batch_size: int,
        cache_prefix: str,
    ) -> None:
        super().__init__(cache_prefix=cache_prefix, release_data=True)
        self.loader = loader
        self.task = task
        self.split = split
        self.split_seed = split_seed
        self.test_size = test_size
        self.row_batch_size = row_batch_size
        self.max_rows = max_rows
        self.batch_size = max(1, int(batch_size))
        self._batch_iter: Optional[Iterator[Tuple[np.ndarray, np.ndarray]]] = None
        self.examples_seen = 0
        self.positives_seen = 0
        self.reset()

    def _stream_batches(self) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        batch_rows: List[Dict[str, Any]] = []
        labels: List[float] = []
        count = 0
        pos = 0
        for example_index, (row, label, game_id) in enumerate(
            _iter_labeled_examples(
                self.loader,
                self.task,
                row_batch_size=self.row_batch_size,
                max_rows=self.max_rows,
            )
        ):
            assigned = _split_for_example(
                game_id,
                example_index,
                split_seed=self.split_seed,
                test_size=self.test_size,
            )
            if assigned != self.split:
                continue
            batch_rows.append(row)
            labels.append(label)
            count += 1
            if int(label) == 1:
                pos += 1
            if len(batch_rows) >= self.batch_size:
                X = self.loader._vectorize_rows(batch_rows)
                y = np.asarray(labels, dtype=np.float32)
                yield X, y
                batch_rows = []
                labels = []

        if batch_rows:
            X = self.loader._vectorize_rows(batch_rows)
            y = np.asarray(labels, dtype=np.float32)
            yield X, y

        self.examples_seen = count
        self.positives_seen = pos

    def reset(self) -> None:
        self._batch_iter = self._stream_batches()

    def next(self, input_data: Any) -> bool:
        if self._batch_iter is None:
            self.reset()
        assert self._batch_iter is not None
        try:
            features, labels = next(self._batch_iter)
        except StopIteration:
            return False
        input_data(data=features, label=labels)
        return True


def _external_cache_dir(args: argparse.Namespace, output_dir: Path) -> Path:
    if args.external_cache_dir:
        return Path(args.external_cache_dir)
    return output_dir / f".xgb_cache_{args.task}"


def _cleanup_external_cache(cache_dir: Path) -> None:
    if not cache_dir.exists():
        return
    try:
        shutil.rmtree(cache_dir)
    except OSError as exc:
        _log.warning("Unable to remove XGBoost cache dir %s: %s", cache_dir, exc)


def _train_external_memory(
    args: argparse.Namespace,
    loader: DataLoader,
    output_dir: Path,
) -> Tuple[xgb.Booster, Dict[str, Any], Dict[str, Any], Dict[str, Any], Path]:
    cache_dir = _external_cache_dir(args, output_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    train_iter = _ExternalMemoryDataIter(
        loader,
        args.task,
        "train",
        split_seed=args.seed,
        test_size=args.test_size,
        row_batch_size=args.row_batch_size,
        max_rows=args.max_rows,
        batch_size=args.external_batch_size,
        cache_prefix=str(cache_dir / "train_cache"),
    )
    dtrain = xgb.ExtMemQuantileDMatrix(train_iter)

    test_iter = _ExternalMemoryDataIter(
        loader,
        args.task,
        "test",
        split_seed=args.seed,
        test_size=args.test_size,
        row_batch_size=args.row_batch_size,
        max_rows=args.max_rows,
        batch_size=args.external_batch_size,
        cache_prefix=str(cache_dir / "test_cache"),
    )
    dtest = xgb.ExtMemQuantileDMatrix(test_iter, ref=dtrain)

    # Log split stats collected during iterator consumption (no separate pre-pass)
    train_examples = train_iter.examples_seen
    test_examples = test_iter.examples_seen
    split_stats: Dict[str, Any] = {
        "train_examples": train_examples,
        "test_examples": test_examples,
    }
    if train_examples <= 0 or test_examples <= 0:
        raise ValueError(
            "External-memory split produced empty train/test data. "
            "Increase data size or adjust --test-size."
        )
    _log.info(
        "[external] split stats -> train=%d test=%d (seed=%d, test_size=%.2f)",
        train_examples,
        test_examples,
        args.seed,
        args.test_size,
    )
    if args.task in {"fight", "top4"}:
        train_pos = train_iter.positives_seen / max(1, train_examples)
        test_pos = test_iter.positives_seen / max(1, test_examples)
        split_stats["train_positive_rate"] = train_pos
        split_stats["test_positive_rate"] = test_pos
        _log.info(
            "[external] class balance -> train_pos_rate=%.4f test_pos_rate=%.4f",
            train_pos,
            test_pos,
        )

    params = dict(BASE_TREE_PARAMS)
    if args.task in {"fight", "top4"}:
        params.update(
            {
                "objective": "binary:logistic",
                "eval_metric": "auc",
                "device": _best_xgb_device(),
            }
        )
    else:
        params.update(
            {
                "objective": "reg:squarederror",
                "eval_metric": "mae",
                "device": _best_xgb_device(),
            }
        )

    booster = _train_booster_with_fallback(
        params=params,
        dtrain=dtrain,
        dtest=dtest,
        num_boost_round=args.n_estimators,
        early_stopping_rounds=args.early_stopping_rounds,
    )

    if args.task in {"fight", "top4"}:
        metrics = _evaluate_booster_classification(args.task, booster, dtest)
    else:
        metrics = _evaluate_booster_regression(booster, dtest)

    del dtrain, dtest, train_iter, test_iter
    gc.collect()

    return booster, params, metrics, split_stats, cache_dir


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
        with DataLoader(args.data, feature_engineer=TFTFeatureEngineer(config=config)) as loader:
            if args.task == "fight":
                X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                    row_batch_size=args.row_batch_size,
                )
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "binary:logistic",
                        "eval_metric": "auc",
                        "device": _best_xgb_device(),
                        "n_estimators": min(200, args.n_estimators),
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBClassifier, params, X_train, y_train, X_test, y_test
                )
                metric = accuracy_score(
                    y_test, (model.predict_proba(X_test)[:, 1] >= 0.5).astype(np.int64)
                )
            elif args.task == "top4":
                X_train, X_test, y_train, y_test = loader.load_top4_classification_data(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                    row_batch_size=args.row_batch_size,
                )
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "binary:logistic",
                        "eval_metric": "auc",
                        "device": _best_xgb_device(),
                        "n_estimators": min(200, args.n_estimators),
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBClassifier, params, X_train, y_train, X_test, y_test
                )
                metric = accuracy_score(
                    y_test, (model.predict_proba(X_test)[:, 1] >= 0.5).astype(np.int64)
                )
            else:
                X_train, X_test, y_train, y_test = loader.load_placement_prediction_data(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                    row_batch_size=args.row_batch_size,
                )
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "reg:squarederror",
                        "eval_metric": "mae",
                        "device": _best_xgb_device(),
                        "n_estimators": min(200, args.n_estimators),
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBRegressor, params, X_train, y_train, X_test, y_test
                )
                metric = mean_absolute_error(y_test, model.predict(X_test))

        delta = (
            float(metric - baseline_metric) if is_higher_better else float(baseline_metric - metric)
        )
        deltas[toggle] = delta
        _log.info("[ablation] disable=%s metric=%.4f delta=%.4f", toggle, metric, delta)
    return deltas


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train XGBoost TFT models.")
    parser.add_argument(
        "--data", type=str, required=True, help="Directory containing parquet/jsonl chunks"
    )
    parser.add_argument("--task", type=str, choices=("fight", "top4", "placement"), required=True)
    parser.add_argument("--output", type=str, default="models/checkpoints", help="Output directory")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument(
        "--row-batch-size",
        type=int,
        default=4096,
        help="Raw row batch size for parquet/jsonl streaming",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap on raw rows scanned before feature building",
    )
    parser.add_argument(
        "--external-memory", action="store_true", help="Use ExtMemQuantileDMatrix training path"
    )
    parser.add_argument(
        "--external-batch-size",
        type=int,
        default=8192,
        help="Examples per external-memory iterator batch",
    )
    parser.add_argument(
        "--external-cache-dir",
        type=str,
        default=None,
        help="Directory for xgboost external-memory cache pages",
    )
    parser.add_argument(
        "--keep-external-cache",
        action="store_true",
        help="Keep external-memory cache files after training",
    )
    parser.add_argument(
        "--early-stopping-rounds",
        type=int,
        default=50,
        help="Early stopping rounds (set 0 to disable)",
    )
    parser.add_argument(
        "--feature-workers",
        type=int,
        default=0,
        help="Parallel workers for feature engineering (0=auto)",
    )
    parser.add_argument("--ablation", action="store_true", help="Run feature-group ablation study")
    parser.add_argument(
        "--grow-policy",
        choices=("depthwise", "lossguide"),
        default=None,
        help="XGBoost grow policy (default: lossguide)",
    )
    parser.add_argument(
        "--max-leaves", type=int, default=None, help="Max leaves per tree (lossguide mode)"
    )
    parser.add_argument(
        "--max-depth", type=int, default=None, help="Max tree depth (depthwise mode, 0=unlimited)"
    )
    parser.add_argument(
        "--arrow",
        action="store_true",
        help="Use Arrow-based data loading (Parquet -> features without row dicts)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not 0.0 < args.test_size < 1.0:
        raise ValueError("--test-size must be in (0, 1)")
    if args.external_memory and args.ablation:
        raise ValueError("--ablation is not supported with --external-memory")

    es_rounds = args.early_stopping_rounds if args.early_stopping_rounds else None

    # Apply CLI tree-param overrides
    if args.grow_policy is not None:
        BASE_TREE_PARAMS["grow_policy"] = args.grow_policy
    if args.max_leaves is not None:
        BASE_TREE_PARAMS["max_leaves"] = args.max_leaves
    if args.max_depth is not None:
        BASE_TREE_PARAMS["max_depth"] = args.max_depth

    with DataLoader(args.data, n_workers=args.feature_workers) as loader:
        feature_names = loader.feature_engineer.feature_names()
        split_stats: Optional[Dict[str, Any]] = None
        cache_dir: Optional[Path] = None

        if args.external_memory:
            model, params, metrics, split_stats, cache_dir = _train_external_memory(
                args, loader, output_dir
            )
            if args.task in {"fight", "top4"}:
                baseline_metric = float(metrics["accuracy"])
                is_higher_better = True
            else:
                baseline_metric = float(metrics["mae"])
                is_higher_better = False
        elif getattr(args, "arrow", False) and args.task in {"fight", "top4", "placement"}:
            if args.task == "fight":
                X_train, X_test, y_train, y_test = loader.load_fight_prediction_arrow(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                )
            elif args.task == "top4":
                X_train, X_test, y_train, y_test = loader.load_top4_classification_arrow(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                )
            else:
                X_train, X_test, y_train, y_test = loader.load_placement_prediction_arrow(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                )
            params = dict(BASE_TREE_PARAMS)
            if args.task in {"fight", "top4"}:
                params.update(
                    {
                        "objective": "binary:logistic",
                        "eval_metric": "auc",
                        "device": _best_xgb_device(),
                        "n_estimators": args.n_estimators,
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBClassifier,
                    params,
                    X_train,
                    y_train,
                    X_test,
                    y_test,
                    early_stopping_rounds=es_rounds,
                )
                metrics = _evaluate_classification(args.task, model, X_test, y_test)
                baseline_metric = float(metrics["accuracy"])
                is_higher_better = True
            else:
                params.update(
                    {
                        "objective": "reg:squarederror",
                        "eval_metric": "mae",
                        "device": _best_xgb_device(),
                        "n_estimators": args.n_estimators,
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBRegressor,
                    params,
                    X_train,
                    y_train,
                    X_test,
                    y_test,
                    early_stopping_rounds=es_rounds,
                )
                metrics = _evaluate_regression(model, X_test, y_test)
                baseline_metric = float(metrics["mae"])
                is_higher_better = False
        else:
            if args.task == "fight":
                X_train, X_test, y_train, y_test = loader.load_fight_prediction_data(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                    row_batch_size=args.row_batch_size,
                )
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "binary:logistic",
                        "eval_metric": "auc",
                        "device": _best_xgb_device(),
                        "n_estimators": args.n_estimators,
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBClassifier,
                    params,
                    X_train,
                    y_train,
                    X_test,
                    y_test,
                    early_stopping_rounds=es_rounds,
                )
                metrics = _evaluate_classification("fight", model, X_test, y_test)
                baseline_metric = float(metrics["accuracy"])
                is_higher_better = True
            elif args.task == "top4":
                X_train, X_test, y_train, y_test = loader.load_top4_classification_data(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                    row_batch_size=args.row_batch_size,
                )
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "binary:logistic",
                        "eval_metric": "auc",
                        "device": _best_xgb_device(),
                        "n_estimators": args.n_estimators,
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBClassifier,
                    params,
                    X_train,
                    y_train,
                    X_test,
                    y_test,
                    early_stopping_rounds=es_rounds,
                )
                metrics = _evaluate_classification("top4", model, X_test, y_test)
                baseline_metric = float(metrics["accuracy"])
                is_higher_better = True
            else:
                X_train, X_test, y_train, y_test = loader.load_placement_prediction_data(
                    test_size=args.test_size,
                    seed=args.seed,
                    max_rows=args.max_rows,
                    row_batch_size=args.row_batch_size,
                )
                params = dict(BASE_TREE_PARAMS)
                params.update(
                    {
                        "objective": "reg:squarederror",
                        "eval_metric": "mae",
                        "device": _best_xgb_device(),
                        "n_estimators": args.n_estimators,
                    }
                )
                model = _train_with_fallback(
                    xgb.XGBRegressor,
                    params,
                    X_train,
                    y_train,
                    X_test,
                    y_test,
                    early_stopping_rounds=es_rounds,
                )
                metrics = _evaluate_regression(model, X_test, y_test)
                baseline_metric = float(metrics["mae"])
                is_higher_better = False

        importances = _extract_feature_importance(model, feature_names)
        _log.info("Top 20 feature importances:")
        for feature, score in importances[:20]:
            _log.info("  %s: %.4f", feature, score)

        model_path = output_dir / f"{args.task}_xgboost.json"
        model.save_model(model_path)
        chart_path = output_dir / f"{args.task}_feature_importance.png"
        _save_feature_chart(importances, chart_path)
        _log.info("Saved model -> %s", model_path)
        _log.info("Saved chart -> %s", chart_path)

        report = {
            "task": args.task,
            "params": params,
            "metrics": metrics,
            "top_features": importances[:20],
            "feature_count": len(feature_names),
            "training_mode": "external_memory" if args.external_memory else "in_memory",
            "early_stopping_rounds": es_rounds,
            "split_stats": split_stats,
            "data_loading": {
                "test_size": args.test_size,
                "seed": args.seed,
                "row_batch_size": args.row_batch_size,
                "max_rows": args.max_rows,
            },
            "external_memory": {
                "enabled": bool(args.external_memory),
                "batch_size": args.external_batch_size if args.external_memory else None,
                "cache_dir": str(cache_dir) if cache_dir else None,
                "keep_cache": bool(args.keep_external_cache) if args.external_memory else None,
                "early_stopping_rounds": (
                    args.early_stopping_rounds if args.external_memory else None
                ),
            },
        }

        if args.ablation:
            report["ablation"] = _run_ablation(
                args, baseline_metric=baseline_metric, is_higher_better=is_higher_better
            )

        report_path = output_dir / f"{args.task}_training_report.json"
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        _log.info("Saved report -> %s", report_path)

        if args.external_memory and cache_dir is not None and not args.keep_external_cache:
            gc.collect()
            _cleanup_external_cache(cache_dir)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    main()
