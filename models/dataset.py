"""PyTorch dataset for TFT simulator training rows."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

import torch
from torch.utils.data import Dataset, IterableDataset, get_worker_info

from snapshot_schema import decode_jsonish, normalize_jsonish_fields

from .feature_engineering import TFTFeatureEngineer

try:  # pragma: no cover - optional dependency
    import pyarrow.parquet as pq
except (ImportError, OSError):  # pragma: no cover - optional dependency
    pq = None


def _normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return normalize_jsonish_fields(row)


def _discover_chunk_files(root: Path) -> List[Path]:
    parquet_files = sorted(root.rglob("*.parquet"))
    jsonl_files = sorted(root.rglob("*.jsonl"))
    # Prefer parquet when present in the same directory tree.
    return parquet_files if parquet_files else jsonl_files


def _iter_file_rows(path: Path, row_batch_size: int = 4096) -> Iterator[Dict[str, Any]]:
    if path.suffix == ".parquet":
        if pq is None:  # pragma: no cover - optional dependency
            raise RuntimeError("pyarrow is required to read parquet chunks.")
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(batch_size=row_batch_size):
            for row in batch.to_pylist():
                yield _normalize_row(row)
        return

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield _normalize_row(json.loads(line))


def _iter_rows_from_files(
    files: Iterable[Path],
    row_batch_size: int = 4096,
) -> Iterator[Dict[str, Any]]:
    for path in files:
        yield from _iter_file_rows(path, row_batch_size=row_batch_size)


def _iter_file_rows_split_filtered(
    path: Path,
    *,
    target_split: str,
    split_seed: int = 42,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    row_batch_size: int = 4096,
) -> Iterator[Dict[str, Any]]:
    """Like _iter_file_rows but pre-filters Parquet rows by split using game_id column projection."""
    if path.suffix != ".parquet" or pq is None:
        # Fallback: no optimization for JSONL
        for row in _iter_file_rows(path, row_batch_size=row_batch_size):
            yield row
        return

    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=row_batch_size):
        # Get game_ids for the batch using zero-copy Arrow access
        game_ids = batch.column("game_id")
        rows_list = None  # Lazy - only materialize if needed

        for i in range(len(game_ids)):
            gid = game_ids[i].as_py()
            if gid is None:
                continue
            split = assign_split_for_game_id(
                int(gid),
                split_seed=split_seed,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
            )
            if split != target_split:
                continue
            # Only now materialize the full row
            if rows_list is None:
                rows_list = batch.to_pylist()
            yield _normalize_row(rows_list[i])


def _iter_rows_from_files_filtered(
    files: Iterable[Path],
    *,
    target_split: str,
    split_seed: int = 42,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    row_batch_size: int = 4096,
) -> Iterator[Dict[str, Any]]:
    for path in files:
        yield from _iter_file_rows_split_filtered(
            path,
            target_split=target_split,
            split_seed=split_seed,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            row_batch_size=row_batch_size,
        )


def _infer_binary_fight_result(row: Dict[str, Any]) -> Optional[int]:
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


def assign_split_for_game_id(
    game_id: int,
    split_seed: int = 42,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
) -> str:
    token = f"{split_seed}:{game_id}".encode("utf-8")
    digest = hashlib.sha1(token).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    if bucket < train_ratio:
        return "train"
    if bucket < train_ratio + val_ratio:
        return "val"
    return "test"


def estimate_streaming_split_counts(
    data_dir: str | Path,
    *,
    split_seed: int = 42,
    label_mode: str = "next_round",
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    row_batch_size: int = 4096,
    max_rows: Optional[int] = None,
) -> Dict[str, int]:
    """Count train/val/test examples without loading all rows into memory.

    For Parquet files:
    - ``label_mode="current"``: reads only the ``game_id`` column, so each
      file requires a single column-projection scan instead of full row reads.
    - ``label_mode="next_round"``: reads only ``game_id``, ``player_id``,
      ``round``, and ``combat_result`` / streak columns to count valid fight
      pairs without deserialising the full row payload.

    For JSONL files the original row-iteration path is retained.
    """
    if label_mode not in {"current", "next_round"}:
        raise ValueError("label_mode must be 'current' or 'next_round'")

    root = Path(data_dir)
    files = _discover_chunk_files(root)
    counts = {"train": 0, "val": 0, "test": 0}

    # Fast path: all files are Parquet and pyarrow is available.
    all_parquet = bool(files) and all(f.suffix == ".parquet" for f in files) and pq is not None

    if all_parquet and label_mode == "current":
        # Read only the game_id column — column projection avoids decoding the
        # rest of the row data.
        seen_rows = 0
        for path in files:
            pf = pq.ParquetFile(path)
            for batch in pf.iter_batches(batch_size=row_batch_size, columns=["game_id"]):
                for game_id_raw in batch.column("game_id").to_pylist():
                    if game_id_raw is None:
                        continue
                    seen_rows += 1
                    if max_rows is not None and seen_rows > max_rows:
                        return counts
                    split = assign_split_for_game_id(
                        int(game_id_raw),
                        split_seed=split_seed,
                        train_ratio=train_ratio,
                        val_ratio=val_ratio,
                    )
                    counts[split] += 1
        return counts

    if all_parquet and label_mode == "next_round":
        # Read only the minimal columns needed to identify valid fight pairs.
        # combat_result and streak columns may not be present in all files, so
        # we fall back gracefully when they are absent.
        _NEXT_ROUND_COLS = [
            "game_id",
            "player_id",
            "round",
            "combat_result",
            "win_streak",
            "loss_streak",
        ]
        seen_rows = 0
        current_game_id: Optional[int] = None
        # Maps player_id -> (round_int,) for the previous row seen.
        prev_round_by_player: Dict[int, int] = {}

        for path in files:
            pf = pq.ParquetFile(path)
            # Only request columns that actually exist in this file.
            available = {name for name in pf.schema_arrow.names}
            cols = [c for c in _NEXT_ROUND_COLS if c in available]
            for batch in pf.iter_batches(batch_size=row_batch_size, columns=cols):
                rows_py = batch.to_pylist()
                for row in rows_py:
                    seen_rows += 1
                    if max_rows is not None and seen_rows > max_rows:
                        return counts

                    game_id_raw = row.get("game_id")
                    player_id_raw = row.get("player_id")
                    round_raw = row.get("round")
                    if game_id_raw is None or player_id_raw is None or round_raw is None:
                        continue

                    game_id_int = int(game_id_raw)
                    split = assign_split_for_game_id(
                        game_id_int,
                        split_seed=split_seed,
                        train_ratio=train_ratio,
                        val_ratio=val_ratio,
                    )

                    if current_game_id is None or game_id_int != current_game_id:
                        current_game_id = game_id_int
                        prev_round_by_player = {}

                    player_id_int = int(player_id_raw)
                    round_int = int(round_raw)
                    prev_round = prev_round_by_player.get(player_id_int)
                    if prev_round is not None and round_int > prev_round:
                        # Check whether this row has a valid fight result.
                        next_result = _infer_binary_fight_result(row)
                        if next_result is not None:
                            counts[split] += 1
                    prev_round_by_player[player_id_int] = round_int
        return counts

    # --- Fallback: JSONL files or pyarrow unavailable ---
    seen_rows = 0
    current_game_id_fb: Optional[int] = None
    prev_rows_by_player: Dict[int, Dict[str, Any]] = {}

    for row in _iter_rows_from_files(files, row_batch_size=row_batch_size):
        seen_rows += 1
        if max_rows is not None and seen_rows > max_rows:
            break

        game_id = row.get("game_id")
        if game_id is None:
            continue
        game_id_int = int(game_id)
        split = assign_split_for_game_id(
            game_id_int,
            split_seed=split_seed,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
        )

        if label_mode == "current":
            counts[split] += 1
            continue

        player_id = row.get("player_id")
        round_num = row.get("round")
        if player_id is None or round_num is None:
            continue

        if current_game_id_fb is None or game_id_int != current_game_id_fb:
            current_game_id_fb = game_id_int
            prev_rows_by_player = {}

        player_id_int = int(player_id)
        round_int = int(round_num)
        prev_row = prev_rows_by_player.get(player_id_int)
        if prev_row is not None:
            prev_round = int(prev_row.get("round", -1))
            if round_int > prev_round:
                next_result = _infer_binary_fight_result(row)
                if next_result is not None:
                    counts[split] += 1
        prev_rows_by_player[player_id_int] = row

    return counts


class TFTDataset(Dataset[Dict[str, torch.Tensor]]):
    """Structured dataset matching ``TFTTransformerV2`` input schema."""

    def __init__(
        self,
        data_dir: str | Path,
        rows: Optional[Sequence[Dict[str, Any]]] = None,
        max_units: int = 14,
        champion_vocab_size: int = 109,
        item_vocab_size: int = 152,
        augment_vocab_size: int = 375,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.max_units = max_units
        self.champion_vocab_size = champion_vocab_size
        self.item_vocab_size = item_vocab_size
        self.augment_vocab_size = augment_vocab_size
        self.feature_engineer = TFTFeatureEngineer()
        self.rows = list(rows) if rows is not None else self._load_rows(self.data_dir)
        self.game_ids = [int(row.get("game_id", idx)) for idx, row in enumerate(self.rows)]

        self.champion_to_idx = self._build_champion_lookup()
        self.item_to_idx = self._build_item_lookup()
        self.augment_to_idx = self._build_augment_lookup()
        self.trait_order = [trait.api_name for trait in self.feature_engineer.traits]

    def _load_rows(self, root: Path) -> List[Dict[str, Any]]:
        return list(_iter_rows_from_files(_discover_chunk_files(root)))

    def _build_champion_lookup(self) -> Dict[str, int]:
        lookup = {"<PAD>": 0, "<UNK>": 1}
        champions = sorted(self.feature_engineer.champion_costs.keys())
        capacity = self.champion_vocab_size - 2
        for index, champion in enumerate(champions[:capacity], start=2):
            lookup[champion] = index
        return lookup

    def _build_item_lookup(self) -> Dict[str, int]:
        lookup = {"<PAD>": 0, "<UNK>": 1}
        items = sorted(self.feature_engineer.item_stats.keys())
        capacity = self.item_vocab_size - 2
        for index, item in enumerate(items[:capacity], start=2):
            lookup[item] = index
        return lookup

    def _build_augment_lookup(self) -> Dict[str, int]:
        lookup = {"<PAD>": 0, "<UNK>": 1}
        augments = sorted(self.feature_engineer.augment_encoding.keys())
        capacity = self.augment_vocab_size - 2
        for index, augment in enumerate(augments[:capacity], start=2):
            lookup[augment] = index
        return lookup

    def __len__(self) -> int:
        return len(self.rows)

    def _encode_units(self, row: Dict[str, Any], prefix: str) -> Tuple[torch.Tensor, ...]:
        units = self.feature_engineer._extract_units(row, prefix=prefix)  # noqa: SLF001
        champion_ids = torch.zeros(self.max_units, dtype=torch.long)
        star_levels = torch.zeros(self.max_units, dtype=torch.long)
        items = torch.zeros((self.max_units, 3), dtype=torch.long)
        positions = torch.zeros(self.max_units, dtype=torch.long)
        costs = torch.zeros(self.max_units, dtype=torch.long)
        mask = torch.zeros(self.max_units, dtype=torch.bool)

        for idx, unit in enumerate(units[: self.max_units]):
            champion = str(unit.get("champion_id", ""))
            champion_ids[idx] = self.champion_to_idx.get(champion, 1)
            star_levels[idx] = max(0, min(3, int(unit.get("star_level", 1))))
            costs[idx] = max(0, min(7, int(self.feature_engineer.champion_costs.get(champion, 0))))
            raw_position = unit.get("position")
            if raw_position is not None:
                position = max(0, min(27, int(raw_position)))
                positions[idx] = position + 1  # 0 reserved for padding/unknown

            for item_slot, raw_item in enumerate((unit.get("items") or [])[:3]):
                canonical_item = self.feature_engineer._canonical_item_name(raw_item)  # noqa: SLF001
                items[idx, item_slot] = self.item_to_idx.get(canonical_item, 1)
            mask[idx] = True

        return champion_ids, star_levels, items, positions, costs, mask

    def _encode_traits(self, row: Dict[str, Any], prefix: str) -> torch.Tensor:
        traits = self.feature_engineer._extract_traits(row, prefix=prefix)  # noqa: SLF001
        tensor = torch.zeros(len(self.trait_order), dtype=torch.float32)
        for index, trait_name in enumerate(self.trait_order):
            tensor[index] = float(traits.get(trait_name, 0))
        return tensor

    def _encode_augments(self, row: Dict[str, Any], prefix: str) -> torch.Tensor:
        if prefix == "opponent_":
            raw = decode_jsonish(row.get("opponent_augments", []))
            if not raw:
                return torch.zeros(3, dtype=torch.long)
            augments = []
            for item in list(raw)[:3]:
                augments.append(str(item))
            while len(augments) < 3:
                augments.append("")
        else:
            augments = self.feature_engineer._extract_augments(row)  # noqa: SLF001

        encoded = [self.augment_to_idx.get(name, 1) if name else 0 for name in augments[:3]]
        while len(encoded) < 3:
            encoded.append(0)
        return torch.tensor(encoded, dtype=torch.long)

    def _encode_game_state(self, row: Dict[str, Any], prefix: str) -> torch.Tensor:
        level = float(row.get(f"{prefix}level", row.get("level", 1)))
        hp = float(row.get(f"{prefix}hp", row.get("hp", 100)))
        gold = float(row.get(f"{prefix}gold", row.get("gold", 0)))
        streak = row.get(f"{prefix}streak")
        if streak is None:
            win_streak = float(row.get(f"{prefix}win_streak", row.get("win_streak", 0)) or 0)
            loss_streak = float(row.get(f"{prefix}loss_streak", row.get("loss_streak", 0)) or 0)
            streak = win_streak - loss_streak
        streak = float(streak)
        round_num = float(row.get("round", 0))
        stage = float(int(round_num // 7) + 1)
        return torch.tensor(
            [
                max(0.0, min(1.0, level / 10.0)),
                max(0.0, min(1.0, hp / 100.0)),
                max(0.0, min(1.0, gold / 100.0)),
                max(-1.0, min(1.0, streak / 20.0)),
                max(0.0, min(1.0, round_num / 60.0)),
                max(0.0, min(1.0, stage / 10.0)),
            ],
            dtype=torch.float32,
        )

    def _targets(
        self,
        row: Dict[str, Any],
        *,
        fight_result_override: Optional[float] = None,
    ) -> Dict[str, torch.Tensor]:
        if fight_result_override is not None:
            fight_result = float(fight_result_override)
        else:
            combat_result = row.get("combat_result")
            if combat_result in (0, 1):
                fight_result = float(combat_result)
            else:
                win_streak = int(row.get("win_streak", 0) or 0)
                loss_streak = int(row.get("loss_streak", 0) or 0)
                fight_result = 1.0 if win_streak > 0 and loss_streak == 0 else 0.0

        placement = int(row.get("placement", 8) or 8)
        placement = max(1, min(8, placement)) - 1
        return {
            "fight_result": torch.tensor([fight_result], dtype=torch.float32),
            "damage_dealt": torch.tensor(
                [float(row.get("damage_dealt", row.get("damage", 0.0)) or 0.0)], dtype=torch.float32
            ),
            "survivors": torch.tensor([float(row.get("survivors", 0) or 0)], dtype=torch.float32),
            "combat_time": torch.tensor(
                [float(row.get("combat_time", 0.0) or 0.0)], dtype=torch.float32
            ),
            "placement": torch.tensor([placement], dtype=torch.long),
        }

    def encode_row(
        self,
        row: Dict[str, Any],
        *,
        fight_result_override: Optional[float] = None,
    ) -> Dict[str, torch.Tensor]:
        sample: Dict[str, torch.Tensor] = {}

        player_fields = self._encode_units(row, prefix="")
        sample["player_champion_ids"] = player_fields[0]
        sample["player_star_levels"] = player_fields[1]
        sample["player_items"] = player_fields[2]
        sample["player_positions"] = player_fields[3]
        sample["player_costs"] = player_fields[4]
        sample["player_mask"] = player_fields[5]
        sample["player_traits"] = self._encode_traits(row, prefix="")
        sample["player_augments"] = self._encode_augments(row, prefix="")
        sample["player_game_state"] = self._encode_game_state(row, prefix="")

        opponent_fields = self._encode_units(row, prefix="opponent_")
        sample["opponent_champion_ids"] = opponent_fields[0]
        sample["opponent_star_levels"] = opponent_fields[1]
        sample["opponent_items"] = opponent_fields[2]
        sample["opponent_positions"] = opponent_fields[3]
        sample["opponent_costs"] = opponent_fields[4]
        sample["opponent_mask"] = opponent_fields[5]
        sample["opponent_traits"] = self._encode_traits(row, prefix="opponent_")
        sample["opponent_augments"] = self._encode_augments(row, prefix="opponent_")
        sample["opponent_game_state"] = self._encode_game_state(row, prefix="opponent_")

        sample.update(self._targets(row, fight_result_override=fight_result_override))
        return sample

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:
        return self.encode_row(self.rows[index])


class TFTStreamingDataset(IterableDataset[Dict[str, torch.Tensor]]):
    """Streaming dataset for large training corpora."""

    def __init__(
        self,
        data_dir: str | Path,
        *,
        split: str = "train",
        split_seed: int = 42,
        label_mode: str = "next_round",
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        max_examples: Optional[int] = None,
        shuffle_files: bool = True,
        row_batch_size: int = 4096,
        max_units: int = 14,
        champion_vocab_size: int = 109,
        item_vocab_size: int = 152,
        augment_vocab_size: int = 375,
    ) -> None:
        if split not in {"train", "val", "test"}:
            raise ValueError("split must be one of {'train', 'val', 'test'}")
        if label_mode not in {"current", "next_round"}:
            raise ValueError("label_mode must be 'current' or 'next_round'")
        if not (0.0 < train_ratio <= 1.0):
            raise ValueError("train_ratio must be in (0, 1]")
        if not (0.0 <= val_ratio < 1.0):
            raise ValueError("val_ratio must be in [0, 1)")
        if train_ratio + val_ratio > 1.0:
            raise ValueError("train_ratio + val_ratio must be <= 1")

        self.data_dir = Path(data_dir)
        self.split = split
        self.split_seed = split_seed
        self.label_mode = label_mode
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.max_examples = max_examples
        self.shuffle_files = shuffle_files
        self.row_batch_size = row_batch_size
        self._epoch = 0
        self._files = _discover_chunk_files(self.data_dir)
        self._encoder = TFTDataset(
            data_dir=self.data_dir,
            rows=[],
            max_units=max_units,
            champion_vocab_size=champion_vocab_size,
            item_vocab_size=item_vocab_size,
            augment_vocab_size=augment_vocab_size,
        )

    def set_epoch(self, epoch: int) -> None:
        self._epoch = max(0, int(epoch))

    def _split_for_row(self, row: Dict[str, Any]) -> Optional[str]:
        game_id = row.get("game_id")
        if game_id is None:
            return None
        return assign_split_for_game_id(
            int(game_id),
            split_seed=self.split_seed,
            train_ratio=self.train_ratio,
            val_ratio=self.val_ratio,
        )

    def _iter_files_for_worker(self) -> List[Path]:
        worker_info = get_worker_info()
        files = list(self._files)
        if worker_info is not None:
            files = files[worker_info.id :: worker_info.num_workers]
            worker_offset = worker_info.id * 10007
        else:
            worker_offset = 0

        if self.shuffle_files and len(files) > 1:
            rng = random.Random(self.split_seed + self._epoch + worker_offset)
            rng.shuffle(files)
        return files

    def __iter__(self) -> Iterator[Dict[str, torch.Tensor]]:
        files = self._iter_files_for_worker()
        emitted = 0

        if self.label_mode == "current":
            for row in _iter_rows_from_files_filtered(
                files,
                target_split=self.split,
                split_seed=self.split_seed,
                train_ratio=self.train_ratio,
                val_ratio=self.val_ratio,
                row_batch_size=self.row_batch_size,
            ):
                split = self._split_for_row(row)
                if split != self.split:
                    continue
                yield self._encoder.encode_row(row)
                emitted += 1
                if self.max_examples is not None and emitted >= self.max_examples:
                    return
            return

        current_game_id: Optional[int] = None
        prev_rows_by_player: Dict[int, Dict[str, Any]] = {}
        for row in _iter_rows_from_files_filtered(
            files,
            target_split=self.split,
            split_seed=self.split_seed,
            train_ratio=self.train_ratio,
            val_ratio=self.val_ratio,
            row_batch_size=self.row_batch_size,
        ):
            split = self._split_for_row(row)
            if split != self.split:
                continue

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
                    next_result = _infer_binary_fight_result(row)
                    if next_result is not None:
                        yield self._encoder.encode_row(
                            prev_row,
                            fight_result_override=float(next_result),
                        )
                        emitted += 1
                        if self.max_examples is not None and emitted >= self.max_examples:
                            return
            prev_rows_by_player[player_id_int] = row


class PreEncodedTFTDataset(Dataset):
    """Map-style dataset loading pre-encoded .pt tensor chunks.

    Created by ``python -m models.preprocess_tensors``.
    Each chunk is a list of sample dicts (str -> Tensor).
    """

    def __init__(self, data_dir: str | Path, split: str = "train") -> None:
        root = Path(data_dir) / split
        if not root.is_dir():
            raise FileNotFoundError(f"Split directory not found: {root}")

        meta_path = Path(data_dir) / "metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"metadata.json not found in {data_dir}")

        with meta_path.open("r") as f:
            meta = json.load(f)

        self._split = split
        self._total = meta["splits"][split]["count"]
        self._chunk_size = meta["chunk_size"]
        self._chunk_files = sorted(root.glob("chunk_*.pt"))
        if not self._chunk_files:
            raise FileNotFoundError(f"No chunk_*.pt files in {root}")

        # LRU cache for loaded chunks
        self._cache: Dict[int, list] = {}
        self._cache_order: list = []
        self._max_cache = 16

    def __len__(self) -> int:
        return self._total

    def _load_chunk(self, chunk_idx: int) -> list:
        if chunk_idx in self._cache:
            return self._cache[chunk_idx]
        data = torch.load(self._chunk_files[chunk_idx], map_location="cpu", weights_only=False)
        # Evict oldest if cache full
        if len(self._cache) >= self._max_cache:
            oldest = self._cache_order.pop(0)
            self._cache.pop(oldest, None)
        self._cache[chunk_idx] = data
        self._cache_order.append(chunk_idx)
        return data

    def __getitem__(self, index: int) -> Dict[str, torch.Tensor]:
        chunk_idx = index // self._chunk_size
        offset = index % self._chunk_size
        chunk = self._load_chunk(chunk_idx)
        return chunk[offset]
