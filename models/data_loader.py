"""Data loading utilities for TFT ML training."""

from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.model_selection import train_test_split

from .feature_engineering import FeatureConfig, TFTFeatureEngineer
from snapshot_schema import normalize_jsonish_fields

try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover - optional dependency
    pq = None


_worker_fe: Optional[TFTFeatureEngineer] = None


def _init_fe_worker(config: FeatureConfig, repo_root: Path) -> None:
    """Initialize feature engineer in worker process."""
    global _worker_fe
    _worker_fe = TFTFeatureEngineer(config=config, repo_root=repo_root)


def _transform_single(row: Dict[str, Any]) -> np.ndarray:
    """Transform a single row in a worker process."""
    assert _worker_fe is not None
    return _worker_fe.transform(row)


class DataLoader:
    """Load simulator chunks and build train/test matrices."""

    def __init__(
        self,
        data_dir: str | Path,
        feature_engineer: Optional[TFTFeatureEngineer] = None,
        *,
        n_workers: int = 0,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.feature_engineer = feature_engineer or TFTFeatureEngineer()
        self.n_workers = n_workers

    def _iter_parquet_rows(
        self,
        path: Path,
        row_batch_size: int = 4096,
    ) -> Iterator[Dict[str, Any]]:
        if pq is None:  # pragma: no cover - optional dependency
            return
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(batch_size=row_batch_size):
            for row in batch.to_pylist():
                yield self._normalize_row(row)

    def _iter_jsonl_rows(self, path: Path) -> Iterator[Dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield self._normalize_row(json.loads(line))

    def iter_raw(
        self,
        data_dir: Optional[str | Path] = None,
        row_batch_size: int = 4096,
    ) -> Iterator[Dict[str, Any]]:
        """Stream parquet/jsonl rows from ``data_dir`` without full materialization."""
        root = Path(data_dir) if data_dir is not None else self.data_dir
        parquet_files = sorted(root.rglob("*.parquet"))
        jsonl_files = sorted(root.rglob("*.jsonl"))

        if pq is not None:
            for path in parquet_files:
                yield from self._iter_parquet_rows(path, row_batch_size=row_batch_size)

        for path in jsonl_files:
            yield from self._iter_jsonl_rows(path)

    def load_raw(
        self,
        data_dir: Optional[str | Path] = None,
        *,
        max_rows: Optional[int] = None,
        sample: bool = False,
        seed: int = 42,
        row_batch_size: int = 4096,
    ) -> List[Dict[str, Any]]:
        """Load rows from ``data_dir`` with optional streaming cap/sampling."""
        if max_rows is not None and max_rows <= 0:
            return []

        iterator = self.iter_raw(data_dir=data_dir, row_batch_size=row_batch_size)

        if max_rows is None:
            return list(iterator)

        if not sample:
            rows: List[Dict[str, Any]] = []
            for row in iterator:
                rows.append(row)
                if len(rows) >= max_rows:
                    break
            return rows

        rng = np.random.default_rng(seed)
        reservoir: List[Dict[str, Any]] = []
        for seen, row in enumerate(iterator, start=1):
            if len(reservoir) < max_rows:
                reservoir.append(row)
                continue
            swap_index = int(rng.integers(0, seen))
            if swap_index < max_rows:
                reservoir[swap_index] = row
        return reservoir

    def count_rows(
        self,
        data_dir: Optional[str | Path] = None,
    ) -> int:
        """Return the number of rows in parquet/jsonl chunks."""
        root = Path(data_dir) if data_dir is not None else self.data_dir
        parquet_files = sorted(root.rglob("*.parquet"))
        jsonl_files = sorted(root.rglob("*.jsonl"))
        total = 0

        if pq is not None:
            for path in parquet_files:
                total += int(pq.ParquetFile(path).metadata.num_rows)

        for path in jsonl_files:
            with path.open("r", encoding="utf-8") as handle:
                total += sum(1 for line in handle if line.strip())

        return total

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return normalize_jsonish_fields(row)

    def _split_by_game_id(
        self,
        rows: Sequence[Dict[str, Any]],
        labels: np.ndarray,
        test_size: float,
        seed: int,
        stratify: bool,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], np.ndarray, np.ndarray]:
        """Split rows by game id to avoid leakage."""
        game_ids = [row.get("game_id") for row in rows]
        if not all(game_id is not None for game_id in game_ids):
            return self._split_by_row(rows, labels, test_size, seed, stratify)

        game_to_rows: Dict[Any, List[int]] = {}
        for index, game_id in enumerate(game_ids):
            game_to_rows.setdefault(game_id, []).append(index)

        unique_games = np.array(list(game_to_rows.keys()))
        if unique_games.size < 2:
            return self._split_by_row(rows, labels, test_size, seed, stratify)
        game_labels = []
        for game_id in unique_games:
            game_row_indices = game_to_rows[game_id]
            game_label = float(np.mean(labels[game_row_indices]))
            game_labels.append(1 if game_label >= 0.5 else 0)
        game_labels_arr = np.asarray(game_labels)

        stratify_arr = game_labels_arr if stratify and len(np.unique(game_labels_arr)) > 1 else None
        try:
            train_games, test_games = train_test_split(
                unique_games,
                test_size=test_size,
                random_state=seed,
                stratify=stratify_arr,
            )
        except ValueError:
            return self._split_by_row(rows, labels, test_size, seed, stratify)
        train_set = set(train_games.tolist())
        train_indices = [idx for idx, game_id in enumerate(game_ids) if game_id in train_set]
        test_indices = [idx for idx, game_id in enumerate(game_ids) if game_id not in train_set]

        train_rows = [rows[idx] for idx in train_indices]
        test_rows = [rows[idx] for idx in test_indices]
        y_train = labels[train_indices]
        y_test = labels[test_indices]
        return train_rows, test_rows, y_train, y_test

    def _split_by_row(
        self,
        rows: Sequence[Dict[str, Any]],
        labels: np.ndarray,
        test_size: float,
        seed: int,
        stratify: bool,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], np.ndarray, np.ndarray]:
        """Fallback split when game ids are not available."""
        if len(rows) < 2:
            return list(rows), [], labels, np.asarray([], dtype=labels.dtype)
        indices = np.arange(len(rows))
        stratify_arr = labels if stratify and len(np.unique(labels)) > 1 else None
        try:
            train_idx, test_idx = train_test_split(
                indices,
                test_size=test_size,
                random_state=seed,
                stratify=stratify_arr,
            )
        except ValueError:
            return list(rows), [], labels, np.asarray([], dtype=labels.dtype)
        train_rows = [rows[idx] for idx in train_idx.tolist()]
        test_rows = [rows[idx] for idx in test_idx.tolist()]
        return train_rows, test_rows, labels[train_idx], labels[test_idx]

    def _vectorize_rows(self, rows: Sequence[Dict[str, Any]]) -> np.ndarray:
        """Transform rows into feature vectors, optionally in parallel."""
        n_features = len(self.feature_engineer.feature_names())
        if not rows:
            return np.zeros((0, n_features), dtype=np.float32)

        workers = self.n_workers
        if workers == 0:
            workers = min(os.cpu_count() or 1, 64)

        if workers > 1 and len(rows) >= 500:
            chunksize = max(1, len(rows) // (workers * 4))
            print(f"[features] vectorizing {len(rows)} rows with {workers} workers...")
            with multiprocessing.Pool(
                processes=workers,
                initializer=_init_fe_worker,
                initargs=(self.feature_engineer.config, self.feature_engineer.repo_root),
            ) as pool:
                vectors = pool.map(_transform_single, rows, chunksize=chunksize)
            return np.array(vectors, dtype=np.float32)

        result = np.empty((len(rows), n_features), dtype=np.float32)
        for i, row in enumerate(rows):
            result[i] = self.feature_engineer.transform(row)
        return result

    def _print_dataset_stats(
        self,
        task_name: str,
        total_rows: int,
        train_rows: int,
        test_rows: int,
        y_train: np.ndarray,
        y_test: np.ndarray,
        feature_count: int,
    ) -> None:
        print(f"[{task_name}] rows={total_rows} train={train_rows} test={test_rows} features={feature_count}")
        if y_train.size == 0 and y_test.size == 0:
            return
        y_all = np.concatenate([y_train, y_test]) if y_train.size and y_test.size else (y_train if y_train.size else y_test)
        unique, counts = np.unique(y_all, return_counts=True)
        balance = ", ".join(f"{int(value)}:{int(count)}" for value, count in zip(unique, counts))
        print(f"[{task_name}] class/target balance -> {balance}")

    def _infer_binary_fight_result(self, row: Dict[str, Any]) -> Optional[int]:
        """Infer binary fight result from a row if possible.

        Priority:
        1. combat_result field (0/1 only, draw ignored)
        2. streak sign for legacy rows without combat_result
        """
        combat_result = row.get("combat_result")
        if combat_result is not None:
            result = int(combat_result)
            if result in (0, 1):
                return result
            return None

        win_streak = int(row.get("win_streak", 0) or 0)
        loss_streak = int(row.get("loss_streak", 0) or 0)
        if win_streak > 0 and loss_streak == 0:
            return 1
        if loss_streak > 0 and win_streak == 0:
            return 0
        return None

    def load_fight_prediction_data(
        self,
        test_size: float = 0.2,
        seed: int = 42,
        max_rows: Optional[int] = None,
        sample_rows: bool = False,
        row_batch_size: int = 4096,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build dataset for win/loss prediction."""
        rows = self.load_raw(
            max_rows=max_rows,
            sample=sample_rows,
            seed=seed,
            row_batch_size=row_batch_size,
        )

        filtered_rows: List[Dict[str, Any]] = []
        labels: List[int] = []
        for row in rows:
            result = self._infer_binary_fight_result(row)
            if result is None:
                continue
            filtered_rows.append(row)
            labels.append(int(result))

        if not filtered_rows:
            raise ValueError(
                "No fight examples found. "
                "Need combat_result=0/1 (draw rows are ignored) or inferrable streak fields."
            )

        label_array = np.asarray(labels, dtype=np.int64)
        train_rows, test_rows, y_train, y_test = self._split_by_game_id(
            filtered_rows,
            label_array,
            test_size=test_size,
            seed=seed,
            stratify=True,
        )
        X_train = self._vectorize_rows(train_rows)
        X_test = self._vectorize_rows(test_rows)
        self._print_dataset_stats(
            task_name="fight",
            total_rows=len(filtered_rows),
            train_rows=X_train.shape[0],
            test_rows=X_test.shape[0],
            y_train=y_train,
            y_test=y_test,
            feature_count=X_train.shape[1] if X_train.size else len(self.feature_engineer.feature_names()),
        )
        print("[fight] labeling=current_round_combat_result")
        return X_train, X_test, y_train.astype(np.int64), y_test.astype(np.int64)

    def _build_temporal_fight_examples(
        self,
        rows: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[int]]:
        """Create leak-safe fight examples from consecutive rounds per player."""
        grouped: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
        for row in rows:
            game_id = row.get("game_id")
            player_id = row.get("player_id")
            round_num = row.get("round")
            if game_id is None or player_id is None or round_num is None:
                continue
            grouped.setdefault((game_id, player_id), []).append(row)

        examples: List[Dict[str, Any]] = []
        labels: List[int] = []
        for sequence in grouped.values():
            ordered = sorted(sequence, key=lambda item: int(item.get("round", -1)))
            for idx in range(len(ordered) - 1):
                current_row = ordered[idx]
                next_row = ordered[idx + 1]
                current_round = int(current_row.get("round", -1))
                next_round = int(next_row.get("round", -1))
                if next_round <= current_round:
                    continue

                next_result = self._infer_binary_fight_result(next_row)
                if next_result is None:
                    continue

                examples.append(current_row)
                labels.append(next_result)

        return examples, labels

    def load_placement_prediction_data(
        self,
        test_size: float = 0.2,
        seed: int = 42,
        max_rows: Optional[int] = None,
        sample_rows: bool = False,
        row_batch_size: int = 4096,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build dataset for final placement regression (1-8)."""
        rows = self.load_raw(
            max_rows=max_rows,
            sample=sample_rows,
            seed=seed,
            row_batch_size=row_batch_size,
        )
        filtered_rows = [row for row in rows if row.get("placement") is not None and int(row.get("placement", 0)) > 0]
        if not filtered_rows:
            raise ValueError("No placement labels found in the provided dataset.")

        labels = np.asarray([int(row["placement"]) for row in filtered_rows], dtype=np.int64)
        train_rows, test_rows, y_train, y_test = self._split_by_game_id(
            filtered_rows,
            labels,
            test_size=test_size,
            seed=seed,
            stratify=False,
        )
        X_train = self._vectorize_rows(train_rows)
        X_test = self._vectorize_rows(test_rows)
        self._print_dataset_stats(
            task_name="placement",
            total_rows=len(filtered_rows),
            train_rows=X_train.shape[0],
            test_rows=X_test.shape[0],
            y_train=y_train,
            y_test=y_test,
            feature_count=X_train.shape[1] if X_train.size else len(self.feature_engineer.feature_names()),
        )
        return X_train, X_test, y_train.astype(np.int64), y_test.astype(np.int64)

    def load_top4_classification_data(
        self,
        test_size: float = 0.2,
        seed: int = 42,
        max_rows: Optional[int] = None,
        sample_rows: bool = False,
        row_batch_size: int = 4096,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build dataset for top4-vs-bot4 classification."""
        rows = self.load_raw(
            max_rows=max_rows,
            sample=sample_rows,
            seed=seed,
            row_batch_size=row_batch_size,
        )
        filtered_rows = [row for row in rows if row.get("placement") is not None and int(row.get("placement", 0)) > 0]
        if not filtered_rows:
            raise ValueError("No placement labels found in the provided dataset.")

        labels = np.asarray([1 if int(row["placement"]) <= 4 else 0 for row in filtered_rows], dtype=np.int64)
        train_rows, test_rows, y_train, y_test = self._split_by_game_id(
            filtered_rows,
            labels,
            test_size=test_size,
            seed=seed,
            stratify=True,
        )
        X_train = self._vectorize_rows(train_rows)
        X_test = self._vectorize_rows(test_rows)
        self._print_dataset_stats(
            task_name="top4",
            total_rows=len(filtered_rows),
            train_rows=X_train.shape[0],
            test_rows=X_test.shape[0],
            y_train=y_train,
            y_test=y_test,
            feature_count=X_train.shape[1] if X_train.size else len(self.feature_engineer.feature_names()),
        )
        return X_train, X_test, y_train.astype(np.int64), y_test.astype(np.int64)
