"""Data loading utilities for TFT ML training."""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import pickle
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.model_selection import train_test_split

from snapshot_schema import normalize_jsonish_fields

from .feature_engineering import FeatureConfig, TFTFeatureEngineer

try:
    import pyarrow.parquet as pq
except (ImportError, OSError) as _pyarrow_err:
    raise ImportError(
        "pyarrow is required for DataLoader but could not be imported. "
        "Install: pip install 'pyarrow>=14.0'. "
        "Without pyarrow, the data pipeline silently returns empty iterators."
    ) from _pyarrow_err

_log = logging.getLogger(__name__)

_worker_fe: Optional[TFTFeatureEngineer] = None


def _init_fe_worker(config: FeatureConfig, repo_root: Path) -> None:
    """Initialize feature engineer in worker process (loads from disk)."""
    global _worker_fe
    _worker_fe = TFTFeatureEngineer(config=config, repo_root=repo_root)


def _init_fe_worker_pickled(fe_state: bytes) -> None:
    """Initialize worker from pickled FE state (avoids per-worker disk I/O)."""
    global _worker_fe
    _worker_fe = pickle.loads(fe_state)


def _transform_chunk(rows: List[Dict[str, Any]]) -> np.ndarray:
    """Transform a chunk of rows in a worker process."""
    assert _worker_fe is not None
    return _worker_fe.transform_batch(rows)


def _transform_arrow_file(args: Tuple[str, int]) -> np.ndarray:
    """Worker: transform a single Parquet file via Arrow path."""
    path_str, batch_size = args
    assert _worker_fe is not None
    import pyarrow.parquet as _pq

    chunks: List[np.ndarray] = []
    pf = _pq.ParquetFile(path_str)
    for batch in pf.iter_batches(batch_size=batch_size):
        chunk = _worker_fe.transform_arrow_batch(batch)
        if chunk.shape[0] > 0:
            chunks.append(chunk)
    if not chunks:
        return np.zeros((0, len(_worker_fe.feature_names())), dtype=np.float32)
    return np.vstack(chunks)


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
        self._pool: Optional[multiprocessing.pool.Pool] = None

    def _effective_workers(self) -> int:
        if self.n_workers == 0:
            return min(os.cpu_count() or 1, 64)
        return self.n_workers

    def _ensure_pool(self) -> multiprocessing.pool.Pool:
        """Lazily create and return a persistent worker pool.

        Uses pickled FE state to initialize workers (~1ms per worker vs ~30ms
        loading from disk).  Falls back to disk-based init on pickle failure.
        """
        if self._pool is None:
            workers = self._effective_workers()
            try:
                fe_state = pickle.dumps(self.feature_engineer)
                self._pool = multiprocessing.Pool(
                    processes=workers,
                    initializer=_init_fe_worker_pickled,
                    initargs=(fe_state,),
                )
            except (pickle.PicklingError, TypeError) as exc:
                _log.warning(
                    "FeatureEngineer pickle failed (%s); falling back to ~30x slower disk-based "
                    "worker init (~30ms per worker vs ~1ms). Fix: ensure FeatureEngineer is "
                    "picklable, or check __getstate__/__setstate__.",
                    exc,
                )
                self._pool = multiprocessing.Pool(
                    processes=workers,
                    initializer=_init_fe_worker,
                    initargs=(self.feature_engineer.config, self.feature_engineer.repo_root),
                )
        return self._pool

    def close(self) -> None:
        """Shut down the worker pool."""
        if self._pool is not None:
            self._pool.close()
            self._pool.join()
            self._pool = None

    def __enter__(self) -> "DataLoader":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            self.close()
        except (OSError, RuntimeError) as cleanup_err:
            _log.warning(
                "DataLoader worker pool cleanup failed during __exit__: %s. "
                "Original exception (if any) takes priority.",
                cleanup_err,
            )
        return False  # Never suppress the original exception

    def __del__(self) -> None:
        if getattr(self, "_pool", None) is not None:
            import warnings

            warnings.warn(
                "DataLoader was garbage-collected without being closed. "
                "Use 'with DataLoader(...) as dl:' or call dl.close() explicitly.",
                ResourceWarning,
                stacklevel=2,
            )
            try:
                self.close()
            except (OSError, RuntimeError):
                pass

    def _iter_parquet_rows(
        self,
        path: Path,
        row_batch_size: int = 4096,
    ) -> Iterator[Dict[str, Any]]:
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(batch_size=row_batch_size):
            for row in batch.to_pylist():
                yield self._normalize_row(row)

    def _iter_parquet_batches(
        self,
        path: Path,
        batch_size: int = 4096,
    ) -> Iterator[Any]:
        """Yield Arrow RecordBatches without dict conversion."""
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(batch_size=batch_size):
            yield batch

    def iter_arrow_batches(
        self,
        data_dir: Optional[str | Path] = None,
        batch_size: int = 4096,
    ) -> Iterator[Any]:
        """Stream Arrow RecordBatches from parquet files without dict conversion."""
        root = Path(data_dir) if data_dir is not None else self.data_dir
        for path in sorted(root.rglob("*.parquet")):
            yield from self._iter_parquet_batches(path, batch_size=batch_size)

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

        workers = self._effective_workers()

        if workers > 1 and len(rows) >= 500:
            chunk_size = max(1, len(rows) // (workers * 4))
            row_chunks = [rows[i : i + chunk_size] for i in range(0, len(rows), chunk_size)]
            _log.info(
                "[features] vectorizing %d rows with %d workers (%d chunks)...",
                len(rows),
                workers,
                len(row_chunks),
            )
            pool = self._ensure_pool()
            chunk_results = pool.map(_transform_chunk, row_chunks)
            return np.vstack(chunk_results)

        return self.feature_engineer.transform_batch(list(rows))

    def vectorize_arrow_parallel(
        self,
        data_dir: Optional[str | Path] = None,
        *,
        batch_size: int = 4096,
    ) -> np.ndarray:
        """Vectorize Parquet files in parallel via Arrow path (no row-dict IPC).

        Each worker opens Parquet files directly and transforms via Arrow,
        avoiding the expensive pickling of row dicts between processes.
        Only numpy result arrays are sent back.

        Auto-tunes: uses single-process for small datasets (<300K rows or
        <4 files) where IPC overhead exceeds compute savings.
        """
        root = Path(data_dir) if data_dir is not None else self.data_dir
        parquet_files = sorted(root.rglob("*.parquet"))
        n_features = len(self.feature_engineer.feature_names())
        if not parquet_files:
            return np.zeros((0, n_features), dtype=np.float32)

        workers = self._effective_workers()

        # Auto-tune: estimate total rows and decide single vs parallel
        total_rows = sum(int(pq.ParquetFile(p).metadata.num_rows) for p in parquet_files)
        use_parallel = workers > 1 and len(parquet_files) >= 4 and total_rows >= 300_000

        if not use_parallel:
            chunks: List[np.ndarray] = []
            for path in parquet_files:
                for batch in self._iter_parquet_batches(path, batch_size=batch_size):
                    chunk = self.feature_engineer.transform_arrow_batch(batch)
                    if chunk.shape[0] > 0:
                        chunks.append(chunk)
            if not chunks:
                return np.zeros((0, n_features), dtype=np.float32)
            return np.vstack(chunks)

        # Cap workers to file count (no benefit from idle workers)
        effective_workers = min(workers, len(parquet_files))
        pool = self._ensure_pool()
        args = [(str(p), batch_size) for p in parquet_files]
        _log.info(
            "[features] Arrow-parallel: %d files, %d rows, %d workers...",
            len(parquet_files),
            total_rows,
            effective_workers,
        )
        results = pool.map(_transform_arrow_file, args)
        non_empty = [r for r in results if r.shape[0] > 0]
        if not non_empty:
            return np.zeros((0, n_features), dtype=np.float32)
        return np.vstack(non_empty)

    def load_fight_prediction_arrow(
        self,
        test_size: float = 0.2,
        seed: int = 42,
        max_rows: Optional[int] = None,
        batch_size: int = 8192,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Arrow-based fight prediction: Parquet -> features without row dicts.

        Streams Arrow batches, extracts labels from scalar columns, transforms
        features via transform_arrow_batch, then splits by game_id.  Avoids
        building Python dicts for every row.
        """
        import pyarrow as pa

        feature_chunks: List[np.ndarray] = []
        labels_list: List[int] = []
        game_ids_list: List[Optional[int]] = []
        collected = 0

        for batch in self.iter_arrow_batches(batch_size=batch_size):
            schema_names = set(batch.schema.names)
            if "combat_result" not in schema_names:
                continue

            combat_results = batch.column("combat_result").to_pylist()
            game_ids_raw = (
                batch.column("game_id").to_pylist()
                if "game_id" in schema_names
                else [None] * batch.num_rows
            )

            # Filter valid fight rows (combat_result 0 or 1, not 2/draw)
            valid_indices: List[int] = []
            batch_labels: List[int] = []
            batch_game_ids: List[Optional[int]] = []
            for i, result in enumerate(combat_results):
                if result is not None and int(result) in (0, 1):
                    valid_indices.append(i)
                    batch_labels.append(int(result))
                    gid = game_ids_raw[i]
                    batch_game_ids.append(int(gid) if gid is not None else None)

            if not valid_indices:
                continue

            # Take only valid rows from the batch
            filtered_batch = batch.take(pa.array(valid_indices, type=pa.int32()))

            features = self.feature_engineer.transform_arrow_batch(filtered_batch)
            feature_chunks.append(features)
            labels_list.extend(batch_labels)
            game_ids_list.extend(batch_game_ids)
            collected += len(batch_labels)

            if max_rows is not None and collected >= max_rows:
                excess = collected - max_rows
                if excess > 0:
                    feature_chunks[-1] = feature_chunks[-1][:-excess]
                    labels_list = labels_list[:max_rows]
                    game_ids_list = game_ids_list[:max_rows]
                break

        if not feature_chunks:
            raise ValueError(
                "No fight examples found. Need combat_result=0/1 (draw rows are ignored)."
            )

        X_all = np.vstack(feature_chunks)
        y_all = np.asarray(labels_list, dtype=np.int64)

        # Split by game_id
        if all(gid is not None for gid in game_ids_list):
            game_to_indices: Dict[Any, List[int]] = {}
            for i, gid in enumerate(game_ids_list):
                game_to_indices.setdefault(gid, []).append(i)

            unique_games = np.array(list(game_to_indices.keys()))
            game_labels = []
            for gid in unique_games:
                indices = game_to_indices[gid]
                avg = float(np.mean(y_all[indices]))
                game_labels.append(1 if avg >= 0.5 else 0)
            game_labels_arr = np.asarray(game_labels)

            stratify_arr = game_labels_arr if len(np.unique(game_labels_arr)) > 1 else None
            try:
                train_games, test_games = train_test_split(
                    unique_games,
                    test_size=test_size,
                    random_state=seed,
                    stratify=stratify_arr,
                )
            except ValueError:
                # Stratification failed (e.g. too few members in a class)
                # Retry without stratification
                train_games, test_games = train_test_split(
                    unique_games,
                    test_size=test_size,
                    random_state=seed,
                )
            train_set = set(train_games.tolist())
            train_idx = [i for i, gid in enumerate(game_ids_list) if gid in train_set]
            test_idx = [i for i, gid in enumerate(game_ids_list) if gid not in train_set]
        else:
            indices = np.arange(len(y_all))
            stratify_arr = y_all if len(np.unique(y_all)) > 1 else None
            try:
                train_idx_arr, test_idx_arr = train_test_split(
                    indices,
                    test_size=test_size,
                    random_state=seed,
                    stratify=stratify_arr,
                )
                train_idx = train_idx_arr.tolist()
                test_idx = test_idx_arr.tolist()
            except ValueError:
                train_idx = list(range(len(y_all)))
                test_idx = []

        X_train = X_all[train_idx]
        X_test = X_all[test_idx]
        y_train = y_all[train_idx]
        y_test = y_all[test_idx]

        self._print_dataset_stats(
            task_name="fight",
            total_rows=len(y_all),
            train_rows=X_train.shape[0],
            test_rows=X_test.shape[0],
            y_train=y_train,
            y_test=y_test,
            feature_count=X_train.shape[1],
        )
        _log.info("[fight] labeling=current_round_combat_result")
        return X_train, X_test, y_train.astype(np.int64), y_test.astype(np.int64)

    def load_top4_classification_arrow(
        self,
        test_size: float = 0.2,
        seed: int = 42,
        max_rows: Optional[int] = None,
        batch_size: int = 8192,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Arrow-based top4 classification: Parquet -> features without row dicts.

        Streams Arrow batches, extracts placement labels from scalar columns,
        transforms features via transform_arrow_batch, then splits by game_id.
        Label: 1 if placement <= 4, else 0.
        """
        import pyarrow as pa

        feature_chunks: List[np.ndarray] = []
        labels_list: List[int] = []
        game_ids_list: List[Optional[int]] = []
        collected = 0

        for batch in self.iter_arrow_batches(batch_size=batch_size):
            schema_names = set(batch.schema.names)
            if "placement" not in schema_names:
                continue

            placements = batch.column("placement").to_pylist()
            game_ids_raw = (
                batch.column("game_id").to_pylist()
                if "game_id" in schema_names
                else [None] * batch.num_rows
            )

            # Filter rows with valid placement (1-8)
            valid_indices: List[int] = []
            batch_labels: List[int] = []
            batch_game_ids: List[Optional[int]] = []
            for i, placement in enumerate(placements):
                if placement is not None and int(placement) > 0:
                    valid_indices.append(i)
                    batch_labels.append(1 if int(placement) <= 4 else 0)
                    gid = game_ids_raw[i]
                    batch_game_ids.append(int(gid) if gid is not None else None)

            if not valid_indices:
                continue

            filtered_batch = batch.take(pa.array(valid_indices, type=pa.int32()))
            features = self.feature_engineer.transform_arrow_batch(filtered_batch)
            feature_chunks.append(features)
            labels_list.extend(batch_labels)
            game_ids_list.extend(batch_game_ids)
            collected += len(batch_labels)

            if max_rows is not None and collected >= max_rows:
                excess = collected - max_rows
                if excess > 0:
                    feature_chunks[-1] = feature_chunks[-1][:-excess]
                    labels_list = labels_list[:max_rows]
                    game_ids_list = game_ids_list[:max_rows]
                break

        if not feature_chunks:
            raise ValueError("No top4 examples found. Need rows with placement > 0.")

        X_all = np.vstack(feature_chunks)
        y_all = np.asarray(labels_list, dtype=np.int64)

        # Split by game_id using the same Knuth-hash split as load_fight_prediction_arrow
        if all(gid is not None for gid in game_ids_list):
            game_to_indices: Dict[Any, List[int]] = {}
            for i, gid in enumerate(game_ids_list):
                game_to_indices.setdefault(gid, []).append(i)

            unique_games = np.array(list(game_to_indices.keys()))
            game_labels = []
            for gid in unique_games:
                indices = game_to_indices[gid]
                avg = float(np.mean(y_all[indices]))
                game_labels.append(1 if avg >= 0.5 else 0)
            game_labels_arr = np.asarray(game_labels)

            stratify_arr = game_labels_arr if len(np.unique(game_labels_arr)) > 1 else None
            try:
                train_games, test_games = train_test_split(
                    unique_games,
                    test_size=test_size,
                    random_state=seed,
                    stratify=stratify_arr,
                )
            except ValueError:
                train_games, test_games = train_test_split(
                    unique_games,
                    test_size=test_size,
                    random_state=seed,
                )
            train_set = set(train_games.tolist())
            train_idx = [i for i, gid in enumerate(game_ids_list) if gid in train_set]
            test_idx = [i for i, gid in enumerate(game_ids_list) if gid not in train_set]
        else:
            indices = np.arange(len(y_all))
            stratify_arr = y_all if len(np.unique(y_all)) > 1 else None
            try:
                train_idx_arr, test_idx_arr = train_test_split(
                    indices,
                    test_size=test_size,
                    random_state=seed,
                    stratify=stratify_arr,
                )
                train_idx = train_idx_arr.tolist()
                test_idx = test_idx_arr.tolist()
            except ValueError:
                train_idx = list(range(len(y_all)))
                test_idx = []

        X_train = X_all[train_idx]
        X_test = X_all[test_idx]
        y_train = y_all[train_idx]
        y_test = y_all[test_idx]

        self._print_dataset_stats(
            task_name="top4",
            total_rows=len(y_all),
            train_rows=X_train.shape[0],
            test_rows=X_test.shape[0],
            y_train=y_train,
            y_test=y_test,
            feature_count=X_train.shape[1],
        )
        _log.info("[top4] labeling=placement<=4")
        return X_train, X_test, y_train.astype(np.int64), y_test.astype(np.int64)

    def load_placement_prediction_arrow(
        self,
        test_size: float = 0.2,
        seed: int = 42,
        max_rows: Optional[int] = None,
        batch_size: int = 8192,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Arrow-based placement regression: Parquet -> features without row dicts.

        Streams Arrow batches, extracts placement as a float regression label,
        transforms features via transform_arrow_batch, then splits by game_id.
        """
        import pyarrow as pa

        feature_chunks: List[np.ndarray] = []
        labels_list: List[float] = []
        game_ids_list: List[Optional[int]] = []
        collected = 0

        for batch in self.iter_arrow_batches(batch_size=batch_size):
            schema_names = set(batch.schema.names)
            if "placement" not in schema_names:
                continue

            placements = batch.column("placement").to_pylist()
            game_ids_raw = (
                batch.column("game_id").to_pylist()
                if "game_id" in schema_names
                else [None] * batch.num_rows
            )

            # Filter rows with valid placement (1-8)
            valid_indices: List[int] = []
            batch_labels: List[float] = []
            batch_game_ids: List[Optional[int]] = []
            for i, placement in enumerate(placements):
                if placement is not None and int(placement) > 0:
                    valid_indices.append(i)
                    batch_labels.append(float(placement))
                    gid = game_ids_raw[i]
                    batch_game_ids.append(int(gid) if gid is not None else None)

            if not valid_indices:
                continue

            filtered_batch = batch.take(pa.array(valid_indices, type=pa.int32()))
            features = self.feature_engineer.transform_arrow_batch(filtered_batch)
            feature_chunks.append(features)
            labels_list.extend(batch_labels)
            game_ids_list.extend(batch_game_ids)
            collected += len(batch_labels)

            if max_rows is not None and collected >= max_rows:
                excess = collected - max_rows
                if excess > 0:
                    feature_chunks[-1] = feature_chunks[-1][:-excess]
                    labels_list = labels_list[:max_rows]
                    game_ids_list = game_ids_list[:max_rows]
                break

        if not feature_chunks:
            raise ValueError("No placement examples found. Need rows with placement > 0.")

        X_all = np.vstack(feature_chunks)
        y_all = np.asarray(labels_list, dtype=np.float32)

        # Split by game_id (no stratification for regression)
        if all(gid is not None for gid in game_ids_list):
            game_to_indices: Dict[Any, List[int]] = {}
            for i, gid in enumerate(game_ids_list):
                game_to_indices.setdefault(gid, []).append(i)

            unique_games = np.array(list(game_to_indices.keys()))
            try:
                train_games, test_games = train_test_split(
                    unique_games,
                    test_size=test_size,
                    random_state=seed,
                )
            except ValueError:
                train_games, test_games = unique_games, np.array([], dtype=unique_games.dtype)
            train_set = set(train_games.tolist())
            train_idx = [i for i, gid in enumerate(game_ids_list) if gid in train_set]
            test_idx = [i for i, gid in enumerate(game_ids_list) if gid not in train_set]
        else:
            indices = np.arange(len(y_all))
            try:
                train_idx_arr, test_idx_arr = train_test_split(
                    indices,
                    test_size=test_size,
                    random_state=seed,
                )
                train_idx = train_idx_arr.tolist()
                test_idx = test_idx_arr.tolist()
            except ValueError:
                train_idx = list(range(len(y_all)))
                test_idx = []

        X_train = X_all[train_idx]
        X_test = X_all[test_idx]
        y_train = y_all[train_idx]
        y_test = y_all[test_idx]

        self._print_dataset_stats(
            task_name="placement",
            total_rows=len(y_all),
            train_rows=X_train.shape[0],
            test_rows=X_test.shape[0],
            y_train=y_train,
            y_test=y_test,
            feature_count=X_train.shape[1],
        )
        _log.info("[placement] labeling=final_placement_regression")
        return X_train, X_test, y_train, y_test

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
        _log.info(
            "[%s] rows=%d train=%d test=%d features=%d",
            task_name,
            total_rows,
            train_rows,
            test_rows,
            feature_count,
        )
        if y_train.size == 0 and y_test.size == 0:
            return
        y_all = (
            np.concatenate([y_train, y_test])
            if y_train.size and y_test.size
            else (y_train if y_train.size else y_test)
        )
        unique, counts = np.unique(y_all, return_counts=True)
        balance = ", ".join(
            f"{int(value)}:{int(count)}" for value, count in zip(unique, counts, strict=True)
        )
        _log.info("[%s] class/target balance -> %s", task_name, balance)

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
            feature_count=X_train.shape[1]
            if X_train.size
            else len(self.feature_engineer.feature_names()),
        )
        _log.info("[fight] labeling=current_round_combat_result")
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
        filtered_rows = [
            row
            for row in rows
            if row.get("placement") is not None and int(row.get("placement", 0)) > 0
        ]
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
            feature_count=X_train.shape[1]
            if X_train.size
            else len(self.feature_engineer.feature_names()),
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
        filtered_rows = [
            row
            for row in rows
            if row.get("placement") is not None and int(row.get("placement", 0)) > 0
        ]
        if not filtered_rows:
            raise ValueError("No placement labels found in the provided dataset.")

        labels = np.asarray(
            [1 if int(row["placement"]) <= 4 else 0 for row in filtered_rows], dtype=np.int64
        )
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
            feature_count=X_train.shape[1]
            if X_train.size
            else len(self.feature_engineer.feature_names()),
        )
        return X_train, X_test, y_train.astype(np.int64), y_test.astype(np.int64)
