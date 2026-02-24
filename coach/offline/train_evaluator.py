from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pyarrow.parquet as pq
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

from simulator.game.constants import NAME_TO_COST

_STAR_MULT = {1: 1.0, 2: 3.0, 3: 9.0}


def _board_power(board_names: list[str], board_stars: list[int]) -> float:
    total = 0.0
    for name, star in zip(board_names, board_stars, strict=False):
        cost = NAME_TO_COST.get(str(name), 3)
        total += float(cost) * _STAR_MULT.get(int(star), 1.0)
    return total


def _num_traits_2plus(trait_counts: list[int]) -> int:
    return int(sum(1 for c in trait_counts if int(c) >= 2))


@dataclass(frozen=True, slots=True)
class Snapshot:
    game_id: int
    player_id: int
    placement: int
    features: np.ndarray


def _iter_parquet_rows(paths: Iterable[Path]):
    for p in paths:
        table = pq.read_table(p)
        yield table.to_pandas()


def _load_snapshots(input_dir: Path) -> list[Snapshot]:
    parquet_paths = sorted(input_dir.glob("chunk_*.parquet"))
    if not parquet_paths:
        raise SystemExit(f"No chunk_*.parquet files found in {input_dir}")

    # Read and concatenate minimal columns for training.
    frames = []
    cols = [
        "game_id",
        "round",
        "player_id",
        "placement",
        "hp",
        "gold",
        "level",
        "streak",
        "board_count",
        "num_augments",
        "num_traits",
        "alive_count",
        "board_names",
        "board_stars",
        "trait_counts",
    ]
    for df in _iter_parquet_rows(parquet_paths):
        frames.append(df[cols])

    import pandas as pd

    full = pd.concat(frames, ignore_index=True)

    # One snapshot per (game_id, player_id): take the latest round we observed.
    idx = full.groupby(["game_id", "player_id"])["round"].idxmax()
    snap_df = full.loc[idx].reset_index(drop=True)

    snapshots: list[Snapshot] = []
    for row in snap_df.itertuples(index=False):

        def _parse_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    return []
            return []

        board_names = list(_parse_list(getattr(row, "board_names", None)))
        board_stars = list(_parse_list(getattr(row, "board_stars", None)))
        trait_counts = list(_parse_list(getattr(row, "trait_counts", None)))

        power = _board_power(board_names, board_stars)
        num_2plus = _num_traits_2plus(trait_counts)

        gold = int(getattr(row, "gold") or 0)
        interest = min(max(gold, 0) // 10, 5)

        feats = np.array(
            [
                float(power),
                float(getattr(row, "level") or 0),
                float(gold),
                float(getattr(row, "hp") or 0),
                float(interest),
                float(getattr(row, "streak") or 0),
                float(num_2plus),
            ],
            dtype=np.float32,
        )

        snapshots.append(
            Snapshot(
                game_id=int(getattr(row, "game_id")),
                player_id=int(getattr(row, "player_id")),
                placement=int(getattr(row, "placement") or 0),
                features=feats,
            )
        )

    return snapshots


def _build_pairwise_dataset(snaps: list[Snapshot]) -> tuple[np.ndarray, np.ndarray]:
    by_game: dict[int, list[Snapshot]] = {}
    for s in snaps:
        by_game.setdefault(s.game_id, []).append(s)

    x_list = []
    y_list = []
    for game_id, players in by_game.items():
        if len(players) < 2:
            continue
        players = sorted(players, key=lambda s: s.player_id)
        for i in range(len(players)):
            for j in range(i + 1, len(players)):
                a = players[i]
                b = players[j]
                if a.placement == b.placement:
                    continue
                y = 1 if a.placement < b.placement else 0
                diff = a.features - b.features
                x_list.append(diff)
                y_list.append(y)

    if not x_list:
        raise SystemExit("No pairwise examples produced (check input data)")

    return np.stack(x_list, axis=0), np.array(y_list, dtype=np.int64)


def train_linear_pairwise(input_dir: Path, output_path: Path, seed: int = 1337) -> dict:
    snapshots = _load_snapshots(input_dir)
    X, y = _build_pairwise_dataset(snapshots)

    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    split = int(len(idx) * 0.8)
    train_idx, val_idx = idx[:split], idx[split:]

    model = LogisticRegression(
        fit_intercept=False,
        max_iter=2000,
        solver="lbfgs",
    )
    model.fit(X[train_idx], y[train_idx])

    train_pred = model.predict(X[train_idx])
    val_pred = model.predict(X[val_idx]) if len(val_idx) else train_pred

    train_acc = float(accuracy_score(y[train_idx], train_pred))
    val_acc = float(accuracy_score(y[val_idx], val_pred)) if len(val_idx) else train_acc

    feature_names = (
        "board_power",
        "level",
        "gold",
        "hp",
        "interest",
        "streak",
        "num_traits_2plus",
    )

    weights = model.coef_[0].astype(float).tolist()
    artifact = {
        "schema_version": 1,
        "type": "linear_logistic_pairwise_diff",
        "input_dir": str(input_dir),
        "features": list(feature_names),
        "weights": weights,
        "bias": 0.0,
        "train_pairs": int(len(train_idx)),
        "val_pairs": int(len(val_idx)),
        "train_acc": train_acc,
        "val_acc": val_acc,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a simple linear evaluator from simulator parquet chunks"
    )
    parser.add_argument(
        "--input-dir", type=Path, required=True, help="Results dir containing chunk_*.parquet"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/coach/evaluator_linear.json"),
        help="Output evaluator artifact path",
    )
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    artifact = train_linear_pairwise(args.input_dir, args.output, seed=args.seed)
    print(f"[OK] Wrote evaluator -> {args.output}")
    print(f"  train_acc={artifact['train_acc']:.3f} val_acc={artifact['val_acc']:.3f}")


if __name__ == "__main__":
    main()
