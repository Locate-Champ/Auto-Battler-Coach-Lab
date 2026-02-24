from __future__ import annotations

import argparse
from pathlib import Path

from coach.offline.train_evaluator import train_linear_pairwise


def main() -> None:
    parser = argparse.ArgumentParser(description="Train coach models (currently: linear evaluator)")
    parser.add_argument(
        "--input-dir", type=Path, required=True, help="Results dir containing chunk_*.parquet"
    )
    parser.add_argument("--seed", type=int, default=1337)
    args = parser.parse_args()

    out = train_linear_pairwise(
        args.input_dir, Path("outputs/coach/evaluator_linear.json"), seed=args.seed
    )
    print(f"[OK] Models trained: evaluator val_acc={out['val_acc']:.3f}")


if __name__ == "__main__":
    main()
