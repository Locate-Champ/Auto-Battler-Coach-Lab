"""Pre-encode Parquet training data into chunked .pt tensor files.

Reads raw Parquet simulation output, applies feature engineering and tensor
encoding offline, and writes the results as PyTorch .pt chunk files organized
by train/val/test split. This eliminates per-sample Python processing during
transformer training — DataLoader workers just load pre-built tensors.

Usage::

    python -m models.preprocess_tensors \\
        --data results/gate_b_50k \\
        --output data/preencoded \\
        --label-mode next_round \\
        --chunk-size 10000
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch

from .dataset import (
    TFTDataset,
    _discover_chunk_files,
    _infer_binary_fight_result,
    _iter_file_rows,
    assign_split_for_game_id,
)

_log = logging.getLogger(__name__)


def _process_current_mode(
    files: list,
    encoder: TFTDataset,
    split_seed: int,
    train_ratio: float,
    val_ratio: float,
    row_batch_size: int,
) -> Dict[str, List[Dict[str, torch.Tensor]]]:
    """Process files in 'current' label mode — each row is one sample."""
    splits: Dict[str, list] = {"train": [], "val": [], "test": []}

    for path in files:
        for row in _iter_file_rows(path, row_batch_size=row_batch_size):
            game_id = row.get("game_id")
            if game_id is None:
                continue
            split = assign_split_for_game_id(
                int(game_id),
                split_seed=split_seed,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
            )
            sample = encoder.encode_row(row)
            splits[split].append(sample)

    return splits


def _process_next_round_mode(
    files: list,
    encoder: TFTDataset,
    split_seed: int,
    train_ratio: float,
    val_ratio: float,
    row_batch_size: int,
) -> Dict[str, List[Dict[str, torch.Tensor]]]:
    """Process files in 'next_round' label mode — consecutive round pairs per player."""
    splits: Dict[str, list] = {"train": [], "val": [], "test": []}

    current_game_id: Optional[int] = None
    prev_rows_by_player: Dict[int, Dict[str, Any]] = {}

    for path in files:
        for row in _iter_file_rows(path, row_batch_size=row_batch_size):
            game_id = row.get("game_id")
            player_id = row.get("player_id")
            round_num = row.get("round")
            if game_id is None or player_id is None or round_num is None:
                continue

            game_id_int = int(game_id)
            split = assign_split_for_game_id(
                game_id_int,
                split_seed=split_seed,
                train_ratio=train_ratio,
                val_ratio=val_ratio,
            )

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
                        sample = encoder.encode_row(
                            prev_row,
                            fight_result_override=float(next_result),
                        )
                        splits[split].append(sample)

            prev_rows_by_player[player_id_int] = row

    return splits


def _save_chunks(
    samples: List[Dict[str, torch.Tensor]],
    output_dir: Path,
    chunk_size: int,
) -> int:
    """Save samples as chunked .pt files. Returns number of chunks written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    n_chunks = 0

    for start in range(0, len(samples), chunk_size):
        chunk = samples[start : start + chunk_size]
        chunk_path = output_dir / f"chunk_{n_chunks:04d}.pt"
        torch.save(chunk, chunk_path)
        n_chunks += 1

    return n_chunks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-encode Parquet data into .pt tensor chunks for fast training."
    )
    parser.add_argument("--data", required=True, help="Path to raw Parquet data directory")
    parser.add_argument("--output", required=True, help="Output directory for .pt chunks")
    parser.add_argument("--label-mode", default="next_round", choices=["current", "next_round"])
    parser.add_argument("--chunk-size", type=int, default=10_000, help="Samples per .pt chunk")
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--row-batch-size", type=int, default=4096)
    parser.add_argument("--max-units", type=int, default=14)
    parser.add_argument("--champion-vocab", type=int, default=109)
    parser.add_argument("--item-vocab", type=int, default=152)
    parser.add_argument("--augment-vocab", type=int, default=375)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    data_dir = Path(args.data)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = _discover_chunk_files(data_dir)
    if not files:
        _log.error("No data files found in %s", data_dir)
        return

    _log.info("Found %d data files in %s", len(files), data_dir)
    _log.info("Label mode: %s, chunk size: %d", args.label_mode, args.chunk_size)

    # Create a lightweight encoder (empty rows — we only need its encode_row method)
    encoder = TFTDataset(
        data_dir=data_dir,
        rows=[],
        max_units=args.max_units,
        champion_vocab_size=args.champion_vocab,
        item_vocab_size=args.item_vocab,
        augment_vocab_size=args.augment_vocab,
    )

    t0 = time.perf_counter()

    if args.label_mode == "current":
        splits = _process_current_mode(
            files,
            encoder,
            args.split_seed,
            args.train_ratio,
            args.val_ratio,
            args.row_batch_size,
        )
    else:
        splits = _process_next_round_mode(
            files,
            encoder,
            args.split_seed,
            args.train_ratio,
            args.val_ratio,
            args.row_batch_size,
        )

    elapsed = time.perf_counter() - t0

    # Save chunks per split
    metadata = {
        "label_mode": args.label_mode,
        "chunk_size": args.chunk_size,
        "split_seed": args.split_seed,
        "train_ratio": args.train_ratio,
        "val_ratio": args.val_ratio,
        "source_dir": str(data_dir),
        "splits": {},
    }

    for split_name, samples in splits.items():
        split_dir = output_dir / split_name
        n_chunks = _save_chunks(samples, split_dir, args.chunk_size)
        metadata["splits"][split_name] = {
            "count": len(samples),
            "chunks": n_chunks,
        }
        _log.info("  %s: %d samples -> %d chunks", split_name, len(samples), n_chunks)

    meta_path = output_dir / "metadata.json"
    with meta_path.open("w") as f:
        json.dump(metadata, f, indent=2)

    total = sum(len(s) for s in splits.values())
    _log.info("Done in %.1fs. Total: %d samples. Output: %s", elapsed, total, output_dir)


if __name__ == "__main__":
    main()
