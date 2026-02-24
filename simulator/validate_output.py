"""Validate simulation output for data quality.

Checks that batch simulation results are sane before using them for ML training
or balance analysis. Catches issues like:
- Skewed placement distributions (mean should be ~4.5)
- Duplicate placements within a game
- Outlier games (too short/long)
- Missing champion or augment coverage
- Corrupt or missing data

Usage:
    python -m simulator.validate_output results/batch
    python -m simulator.validate_output results/batch --verbose
    python -m simulator.validate_output results/batch --sample-games 500 --sample-seed 42 --max-rows 200000
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from snapshot_schema import decode_jsonish

DUPLICATE_PLACEMENT_SEVERE_MAX = 3
DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT = 0.01


def _iter_parquet_rows(path: Path, row_batch_size: int = 4096) -> Iterator[Dict[str, Any]]:
    import pyarrow.parquet as pq

    parquet_file = pq.ParquetFile(path)
    for batch in parquet_file.iter_batches(batch_size=row_batch_size):
        for row in batch.to_pylist():
            yield row


def _iter_jsonl_rows(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _iter_json_array_rows(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        return
    for row in payload:
        if isinstance(row, dict):
            yield row


def _iter_training_rows(
    output_dir: str,
    row_batch_size: int = 4096,
) -> Iterator[Dict[str, Any]]:
    """Iterate training rows from chunk or legacy formats without materializing all rows."""
    root = Path(output_dir)

    chunk_parquet = sorted(root.glob("chunk_*.parquet"))
    if chunk_parquet:
        try:
            for path in chunk_parquet:
                yield from _iter_parquet_rows(path, row_batch_size=row_batch_size)
            return
        except ImportError:
            pass

    chunk_jsonl = sorted(root.glob("chunk_*.jsonl"))
    if chunk_jsonl:
        for path in chunk_jsonl:
            yield from _iter_jsonl_rows(path)
        return

    parquet_path = root / "training_data.parquet"
    if parquet_path.exists():
        try:
            yield from _iter_parquet_rows(parquet_path, row_batch_size=row_batch_size)
            return
        except ImportError:
            pass

    jsonl_path = root / "training_data.jsonl"
    if jsonl_path.exists():
        yield from _iter_jsonl_rows(jsonl_path)
        return

    json_path = root / "training_data.json"
    if json_path.exists():
        yield from _iter_json_array_rows(json_path)


def _iter_game_ids(
    output_dir: str,
    row_batch_size: int = 4096,
) -> Iterator[int]:
    current_game_id: Optional[int] = None
    for row in _iter_training_rows(output_dir, row_batch_size=row_batch_size):
        game_id = _safe_int(row.get("game_id"))
        if game_id is None:
            continue
        if current_game_id is None or game_id != current_game_id:
            current_game_id = game_id
            yield game_id


def _reservoir_sample_game_ids(
    game_ids: Iterator[int],
    sample_games: int,
    sample_seed: int,
) -> set[int]:
    rng = random.Random(sample_seed)
    reservoir: List[int] = []
    seen_games = 0

    for game_id in game_ids:
        seen_games += 1
        if len(reservoir) < sample_games:
            reservoir.append(game_id)
            continue

        replacement_index = rng.randrange(seen_games)
        if replacement_index < sample_games:
            reservoir[replacement_index] = game_id

    return set(reservoir)


def _load_summary(output_dir: str) -> Optional[Dict]:
    """Load summary.json if it exists."""
    path = Path(output_dir) / "summary.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _load_errors(output_dir: str) -> List[Dict]:
    """Load errors.json if it exists."""
    path = Path(output_dir) / "errors.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class ValidationReport:
    """Accumulates validation checks and produces a report."""

    def __init__(self):
        self.checks: List[Dict] = []
        self.warnings: List[str] = []

    def check(self, name: str, passed: bool, detail: str = ""):
        self.checks.append(
            {
                "name": name,
                "passed": passed,
                "detail": detail,
            }
        )
        return passed

    def warn(self, message: str):
        self.warnings.append(message)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c["passed"])

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c["passed"])

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def print_report(self, verbose: bool = False):
        print(f"\n{'=' * 60}")
        print("VALIDATION REPORT")
        print(f"{'=' * 60}")

        for c in self.checks:
            status = "[PASS]" if c["passed"] else "[FAIL]"
            print(f"  {status} {c['name']}")
            if (not c["passed"] or verbose) and c["detail"]:
                for line in c["detail"].split("\n"):
                    print(f"         {line}")

        if self.warnings:
            print("\nWarnings:")
            for w in self.warnings:
                print(f"  [WARN] {w}")

        print(f"\n{'=' * 60}")
        result = "ALL CHECKS PASSED" if self.all_passed else f"{self.failed} CHECK(S) FAILED"
        print(f"Result: {result} ({self.passed} passed, {self.failed} failed)")
        print(f"{'=' * 60}")


def validate_output(
    output_dir: str,
    verbose: bool = False,
    max_rows: Optional[int] = None,
    sample_games: Optional[int] = None,
    sample_seed: int = 42,
    row_batch_size: int = 4096,
) -> ValidationReport:
    """Run all validation checks on simulation output.

    Args:
        output_dir: Path to the batch output directory.
        verbose: If True, print details for passing checks too.
        max_rows: Optional cap on streamed rows used for validation.
        sample_games: Optional cap on distinct games validated via reservoir sampling.
        sample_seed: Seed for deterministic reservoir game sampling.
        row_batch_size: Batch size used for parquet row streaming.

    Returns:
        ValidationReport with all check results.
    """
    if max_rows is not None and max_rows <= 0:
        raise ValueError("max_rows must be > 0 when provided")
    if sample_games is not None and sample_games <= 0:
        raise ValueError("sample_games must be > 0 when provided")

    report = ValidationReport()

    scope_parts: List[str] = []
    if sample_games is not None:
        scope_parts.append(f"sample_games={sample_games}")
        scope_parts.append(f"sample_seed={sample_seed}")
    if max_rows is not None:
        scope_parts.append(f"max_rows={max_rows}")
    scope_suffix = f" (scope: {', '.join(scope_parts)})" if scope_parts else ""

    # ── Check 1: Output directory exists with expected files ──────────────────
    dir_exists = os.path.isdir(output_dir)
    report.check("Output directory exists", dir_exists, output_dir)
    if not dir_exists:
        return report

    summary = _load_summary(output_dir)
    # ── Check 2: summary.json exists ───────────────────────────────────────────
    report.check("summary.json exists", summary is not None)
    if not summary:
        report.warn("Cannot run remaining checks without summary.json")
        return report

    num_games = summary.get("num_games", 0)
    num_errors = summary.get("num_errors", 0)

    # ── Check 3: Games completed ───────────────────────────────────────────────
    report.check(
        "Games completed",
        num_games > 0,
        f"{num_games} games, {num_errors} errors",
    )

    # ── Check 4: Error rate ────────────────────────────────────────────────────
    total = num_games + num_errors
    error_rate = num_errors / total if total > 0 else 0
    report.check(
        "Error rate < 5%",
        error_rate < 0.05,
        f"{num_errors}/{total} = {error_rate:.1%}",
    )
    if num_errors > 0:
        errors = _load_errors(output_dir)
        if errors:
            sample = errors[0].get("error", "")[:200]
            report.warn(f"First error: {sample}")

    # Streaming accumulators
    rows_loaded = 0
    row_limit_hit = False
    selected_game_ids: Optional[set[int]] = None
    if sample_games is not None:
        selected_game_ids = _reservoir_sample_game_ids(
            _iter_game_ids(output_dir, row_batch_size=row_batch_size),
            sample_games=sample_games,
            sample_seed=sample_seed,
        )
    game_placements: Dict[int, Dict[int, int]] = {}
    game_max_rounds: Dict[int, int] = {}
    champ_counts: Counter = Counter()
    aug_counts: Counter = Counter()
    sample_row: Optional[Dict[str, Any]] = None
    min_hp: Optional[float] = None
    max_hp: Optional[float] = None
    gold_sum = 0.0
    gold_count = 0
    max_gold: Optional[float] = None

    for row in _iter_training_rows(output_dir, row_batch_size=row_batch_size):
        game_id = _safe_int(row.get("game_id"))
        if selected_game_ids is not None:
            if game_id is None:
                continue
            if game_id not in selected_game_ids:
                continue

        rows_loaded += 1
        if sample_row is None:
            sample_row = row

        if game_id is not None:
            player_id = _safe_int(row.get("player_id"))
            placement = _safe_int(row.get("placement"))
            if player_id is not None and placement is not None:
                game_placements.setdefault(game_id, {})[player_id] = placement

            round_num = _safe_int(row.get("round"))
            if round_num is not None:
                prior_round = game_max_rounds.get(game_id, 0)
                if round_num > prior_round:
                    game_max_rounds[game_id] = round_num

        names = decode_jsonish(row.get("board_names", []))
        if isinstance(names, list):
            for name in names:
                champ_counts[str(name)] += 1

        augs = decode_jsonish(row.get("augments", []))
        if isinstance(augs, list):
            for aug in augs:
                aug_counts[str(aug)] += 1

        hp_val = _safe_float(row.get("hp"))
        if hp_val is not None:
            min_hp = hp_val if min_hp is None else min(min_hp, hp_val)
            max_hp = hp_val if max_hp is None else max(max_hp, hp_val)

        gold_val = _safe_float(row.get("gold"))
        if gold_val is not None:
            gold_sum += gold_val
            gold_count += 1
            max_gold = gold_val if max_gold is None else max(max_gold, gold_val)

        if max_rows is not None and rows_loaded >= max_rows:
            row_limit_hit = True
            break

    # ── Check 5: Training data exists ──────────────────────────────────────────
    report.check(
        "Training data exists",
        rows_loaded > 0,
        f"{rows_loaded} rows loaded{scope_suffix}",
    )
    if rows_loaded == 0:
        return report

    if row_limit_hit:
        report.warn(f"Stopped row scan at max_rows={max_rows}.")
    if selected_game_ids is not None:
        report.warn(
            f"Validated {len(selected_game_ids)} sampled game_ids "
            f"(sample_games={sample_games}, sample_seed={sample_seed})."
        )

    # ── Check 6: Rows per game ─────────────────────────────────────────────────
    sampled_game_count = len(game_placements)
    denominator = sampled_game_count if sampled_game_count > 0 else num_games
    rows_per_game = rows_loaded / denominator if denominator > 0 else 0
    report.check(
        "Rows per game in range (50-300)",
        50 <= rows_per_game <= 300,
        f"{rows_per_game:.1f} rows/game over {denominator} games (expect ~128){scope_suffix}",
    )

    # ── Check 7: Placement distribution ────────────────────────────────────────
    all_placements: List[int] = []
    for player_map in game_placements.values():
        all_placements.extend(player_map.values())

    if all_placements:
        mean_placement = sum(all_placements) / len(all_placements)
        variance = sum((p - mean_placement) ** 2 for p in all_placements) / len(all_placements)
        std_placement = math.sqrt(variance)

        report.check(
            "Placement mean ~4.5 (range 3.5-5.5)",
            3.5 <= mean_placement <= 5.5,
            f"mean={mean_placement:.2f}, std={std_placement:.2f}{scope_suffix}",
        )

        # ── Check 8: Placement range ───────────────────────────────────────────
        min_p = min(all_placements)
        max_p = max(all_placements)
        report.check(
            "Placements in valid range (1-8)",
            min_p >= 1 and max_p <= 8,
            f"range: {min_p}-{max_p}{scope_suffix}",
        )

    # ── Check 9: No excessive duplicate placements per game ───────────────────
    severe_dup_games = 0
    for player_map in game_placements.values():
        placements = list(player_map.values())
        if len(placements) != len(set(placements)):
            counts = Counter(placements)
            max_dup = max(counts.values())
            if max_dup > DUPLICATE_PLACEMENT_SEVERE_MAX:
                severe_dup_games += 1

    total_games_with_placements = max(1, len(game_placements))
    severe_dup_rate = severe_dup_games / total_games_with_placements

    report.check(
        "No excessive placement duplicates",
        severe_dup_rate <= DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT,
        (
            f"{severe_dup_games}/{len(game_placements)} games "
            f"({severe_dup_rate:.2%}) with >{DUPLICATE_PLACEMENT_SEVERE_MAX} "
            f"players at same placement{scope_suffix}"
        ),
    )
    if severe_dup_games > 0 and severe_dup_rate <= DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT:
        report.warn(
            "Observed severe placement ties but within tolerated rate "
            f"({severe_dup_rate:.2%} <= {DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT:.2%})."
        )

    # ── Check 10: All 8 players per game ───────────────────────────────────────
    incomplete_games = sum(1 for player_map in game_placements.values() if len(player_map) < 8)
    report.check(
        "All games have 8 players",
        incomplete_games == 0,
        f"{incomplete_games} games with <8 players{scope_suffix}",
    )

    # ── Check 11: Round count sanity ───────────────────────────────────────────
    avg_rounds = summary.get("avg_rounds", 0)
    report.check(
        "Average rounds in range (10-45)",
        10 <= avg_rounds <= 45,
        f"avg_rounds={avg_rounds}",
    )

    # ── Check 12: No round-count outliers (<5 or >50) ─────────────────────────
    if game_max_rounds:
        outlier_short = sum(1 for r in game_max_rounds.values() if r < 5)
        outlier_long = sum(1 for r in game_max_rounds.values() if r > 50)
        report.check(
            "No round-count outliers (<5 or >50)",
            outlier_short == 0 and outlier_long == 0,
            f"{outlier_short} too short, {outlier_long} too long{scope_suffix}",
        )

    # ── Check 13: Champion coverage ────────────────────────────────────────────
    unique_champs = len(champ_counts)
    report.check(
        "Champion coverage > 50 unique champions",
        unique_champs > 50,
        f"{unique_champs} unique champions seen{scope_suffix}",
    )

    # ── Check 14: No dominant champion (>10% pick rate) ───────────────────────
    total_picks = sum(champ_counts.values())
    if total_picks > 0:
        max_champ_name, max_champ_count = champ_counts.most_common(1)[0]
        max_pct = max_champ_count / total_picks
        report.check(
            "No dominant champion (>10% pick rate)",
            max_pct <= 0.10,
            f"Most picked: {max_champ_name} at {max_pct:.1%}{scope_suffix}",
        )

    # ── Check 15: Augment coverage ─────────────────────────────────────────────
    unique_augs = len(aug_counts)
    report.check(
        "Augment coverage > 20 unique augments",
        unique_augs > 20,
        f"{unique_augs} unique augments seen{scope_suffix}",
    )

    # ── Check 16: Required fields present ──────────────────────────────────────
    required_fields = [
        "game_id",
        "round",
        "player_id",
        "placement",
        "hp",
        "gold",
        "level",
        "board_count",
        "win_streak",
        "loss_streak",
        "board_names",
        "board_stars",
        "trait_names",
        "trait_counts",
        "augments",
    ]
    if sample_row is None:
        missing_fields = required_fields
    else:
        missing_fields = [f for f in required_fields if f not in sample_row]
    report.check(
        "All required fields present",
        len(missing_fields) == 0,
        f"Missing: {missing_fields}" if missing_fields else "All 15 fields present",
    )

    # ── Check 17: HP values sensible ───────────────────────────────────────────
    if min_hp is not None and max_hp is not None:
        report.check(
            "HP values in range (0-100)",
            min_hp >= 0 and max_hp <= 100,
            f"range: {min_hp:g}-{max_hp:g}{scope_suffix}",
        )

    # ── Check 18: Gold values sensible ─────────────────────────────────────────
    if gold_count > 0 and max_gold is not None:
        avg_gold = gold_sum / gold_count
        report.check(
            "Gold values reasonable (avg < 100, max < 500)",
            avg_gold < 100 and max_gold < 500,
            f"avg={avg_gold:.1f}, max={max_gold:g}{scope_suffix}",
        )

    # ── Check 19: Performance ──────────────────────────────────────────────────
    games_per_sec = summary.get("games_per_sec", 0)
    if games_per_sec > 0:
        report.check(
            "Performance > 0.5 games/sec",
            games_per_sec >= 0.5,
            f"{games_per_sec} games/sec",
        )

    return report


def main():
    parser = argparse.ArgumentParser(description="Validate TFT simulation output quality")
    parser.add_argument("output_dir", type=str, help="Path to batch output directory")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show details for passing checks too",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap on streamed training rows validated",
    )
    parser.add_argument(
        "--sample-games",
        type=int,
        default=None,
        help="Optional cap on distinct game_ids validated via reservoir sampling",
    )
    parser.add_argument(
        "--sample-seed",
        type=int,
        default=42,
        help="Seed used for deterministic reservoir sampling when --sample-games is set",
    )
    args = parser.parse_args()

    if args.max_rows is not None and args.max_rows <= 0:
        parser.error("--max-rows must be > 0")
    if args.sample_games is not None and args.sample_games <= 0:
        parser.error("--sample-games must be > 0")

    report = validate_output(
        args.output_dir,
        verbose=args.verbose,
        max_rows=args.max_rows,
        sample_games=args.sample_games,
        sample_seed=args.sample_seed,
    )
    report.print_report(verbose=args.verbose)

    sys.exit(0 if report.all_passed else 1)


if __name__ == "__main__":
    main()
