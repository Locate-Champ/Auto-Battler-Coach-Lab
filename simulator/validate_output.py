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
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional


DUPLICATE_PLACEMENT_SEVERE_MAX = 3
DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT = 0.01


def _load_training_data(output_dir: str) -> List[Dict]:
    """Load training data from chunks or legacy single-file format."""
    rows = []

    # Try chunk files first (new streaming format)
    chunk_files = sorted(Path(output_dir).glob('chunk_*.parquet'))
    if chunk_files:
        try:
            import pyarrow.parquet as pq
            for f in chunk_files:
                table = pq.read_table(f)
                rows.extend(table.to_pylist())
            return rows
        except ImportError:
            pass

    chunk_files = sorted(Path(output_dir).glob('chunk_*.jsonl'))
    if chunk_files:
        for f in chunk_files:
            with open(f, 'r', encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        return rows

    # Legacy single-file formats
    parquet_path = Path(output_dir) / 'training_data.parquet'
    if parquet_path.exists():
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(parquet_path)
            return table.to_pylist()
        except ImportError:
            pass

    json_path = Path(output_dir) / 'training_data.json'
    if json_path.exists():
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    return rows


def _load_summary(output_dir: str) -> Optional[Dict]:
    """Load summary.json if it exists."""
    path = Path(output_dir) / 'summary.json'
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def _load_errors(output_dir: str) -> List[Dict]:
    """Load errors.json if it exists."""
    path = Path(output_dir) / 'errors.json'
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


class ValidationReport:
    """Accumulates validation checks and produces a report."""

    def __init__(self):
        self.checks: List[Dict] = []
        self.warnings: List[str] = []

    def check(self, name: str, passed: bool, detail: str = ''):
        self.checks.append({
            'name': name,
            'passed': passed,
            'detail': detail,
        })
        return passed

    def warn(self, message: str):
        self.warnings.append(message)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c['passed'])

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c['passed'])

    @property
    def all_passed(self) -> bool:
        return self.failed == 0

    def print_report(self, verbose: bool = False):
        print(f"\n{'='*60}")
        print(f"VALIDATION REPORT")
        print(f"{'='*60}")

        for c in self.checks:
            status = '[PASS]' if c['passed'] else '[FAIL]'
            print(f"  {status} {c['name']}")
            if (not c['passed'] or verbose) and c['detail']:
                for line in c['detail'].split('\n'):
                    print(f"         {line}")

        if self.warnings:
            print(f"\nWarnings:")
            for w in self.warnings:
                print(f"  [WARN] {w}")

        print(f"\n{'='*60}")
        result = 'ALL CHECKS PASSED' if self.all_passed else f'{self.failed} CHECK(S) FAILED'
        print(f"Result: {result} ({self.passed} passed, {self.failed} failed)")
        print(f"{'='*60}")


def validate_output(output_dir: str, verbose: bool = False) -> ValidationReport:
    """Run all validation checks on simulation output.

    Args:
        output_dir: Path to the batch output directory.
        verbose: If True, print details for passing checks too.

    Returns:
        ValidationReport with all check results.
    """
    report = ValidationReport()

    # ── Check 1: Output directory exists with expected files ─────────
    dir_exists = os.path.isdir(output_dir)
    report.check('Output directory exists', dir_exists, output_dir)
    if not dir_exists:
        return report

    summary = _load_summary(output_dir)
    # ── Check 2: summary.json exists ────────────────────────────────
    report.check('summary.json exists', summary is not None)
    if not summary:
        report.warn("Cannot run remaining checks without summary.json")
        return report

    num_games = summary.get('num_games', 0)
    num_errors = summary.get('num_errors', 0)

    # ── Check 3: Games completed ─────────────────────────────────────
    report.check(
        'Games completed',
        num_games > 0,
        f"{num_games} games, {num_errors} errors"
    )

    # ── Check 4: Error rate ──────────────────────────────────────────
    total = num_games + num_errors
    error_rate = num_errors / total if total > 0 else 0
    report.check(
        'Error rate < 5%',
        error_rate < 0.05,
        f"{num_errors}/{total} = {error_rate:.1%}"
    )
    if num_errors > 0:
        errors = _load_errors(output_dir)
        if errors:
            sample = errors[0].get('error', '')[:200]
            report.warn(f"First error: {sample}")

    # ── Check 5: Training data exists ────────────────────────────────
    rows = _load_training_data(output_dir)
    report.check(
        'Training data exists',
        len(rows) > 0,
        f"{len(rows)} rows loaded"
    )
    if not rows:
        return report

    # ── Check 6: Rows per game ───────────────────────────────────────
    rows_per_game = len(rows) / num_games if num_games > 0 else 0
    # Expect ~128 rows per game (8 players * ~16 rounds)
    report.check(
        'Rows per game in range (50-300)',
        50 <= rows_per_game <= 300,
        f"{rows_per_game:.1f} rows/game (expect ~128)"
    )

    # ── Check 7: Placement distribution ──────────────────────────────
    # Group rows by game_id, find final placement per player per game
    game_placements: Dict[int, List[int]] = {}
    for row in rows:
        gid = row.get('game_id', -1)
        pid = row.get('player_id', -1)
        placement = row.get('placement', 0)
        # Only track once per player per game (use highest round)
        key = (gid, pid)
        if gid not in game_placements:
            game_placements[gid] = {}
        game_placements[gid][pid] = placement

    all_placements = []
    for gid, player_map in game_placements.items():
        all_placements.extend(player_map.values())

    if all_placements:
        mean_placement = sum(all_placements) / len(all_placements)
        variance = sum((p - mean_placement) ** 2 for p in all_placements) / len(all_placements)
        std_placement = math.sqrt(variance)

        report.check(
            'Placement mean ~4.5 (range 3.5-5.5)',
            3.5 <= mean_placement <= 5.5,
            f"mean={mean_placement:.2f}, std={std_placement:.2f}"
        )

        # ── Check 8: Placement range ────────────────────────────────
        min_p = min(all_placements)
        max_p = max(all_placements)
        report.check(
            'Placements in valid range (1-8)',
            min_p >= 1 and max_p <= 8,
            f"range: {min_p}-{max_p}"
        )

    # ── Check 9: No excessive duplicate placements per game ──────────
    severe_dup_games = 0
    for gid, player_map in game_placements.items():
        placements = list(player_map.values())
        if len(placements) != len(set(placements)):
            # Allow ties (players eliminated same round get same placement)
            # but check for persistently high severe-duplicate frequency.
            counts = Counter(placements)
            max_dup = max(counts.values())
            if max_dup > DUPLICATE_PLACEMENT_SEVERE_MAX:
                severe_dup_games += 1

    total_games_with_placements = max(1, len(game_placements))
    severe_dup_rate = severe_dup_games / total_games_with_placements

    report.check(
        'No excessive placement duplicates',
        severe_dup_rate <= DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT,
        (
            f"{severe_dup_games}/{len(game_placements)} games "
            f"({severe_dup_rate:.2%}) with >{DUPLICATE_PLACEMENT_SEVERE_MAX} "
            "players at same placement"
        ),
    )
    if severe_dup_games > 0 and severe_dup_rate <= DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT:
        report.warn(
            "Observed severe placement ties but within tolerated rate "
            f"({severe_dup_rate:.2%} <= {DUPLICATE_PLACEMENT_SEVERE_RATE_LIMIT:.2%})."
        )

    # ── Check 10: All 8 players per game ─────────────────────────────
    incomplete_games = 0
    for gid, player_map in game_placements.items():
        if len(player_map) < 8:
            incomplete_games += 1

    report.check(
        'All games have 8 players',
        incomplete_games == 0,
        f"{incomplete_games} games with <8 players"
    )

    # ── Check 11: Round count sanity ────────────────────────────────
    avg_rounds = summary.get('avg_rounds', 0)
    report.check(
        'Average rounds in range (10-45)',
        10 <= avg_rounds <= 45,
        f"avg_rounds={avg_rounds}"
    )

    # Per-game round counts from training data
    game_max_rounds: Dict[int, int] = {}
    for row in rows:
        gid = row.get('game_id', -1)
        rnd = row.get('round', 0)
        game_max_rounds[gid] = max(game_max_rounds.get(gid, 0), rnd)

    if game_max_rounds:
        outlier_short = sum(1 for r in game_max_rounds.values() if r < 5)
        outlier_long = sum(1 for r in game_max_rounds.values() if r > 50)
        # ── Check 12: No round-count outliers (<5 or >50) ────────────
        report.check(
            'No round-count outliers (<5 or >50)',
            outlier_short == 0 and outlier_long == 0,
            f"{outlier_short} too short, {outlier_long} too long"
        )

    # ── Check 13: Champion coverage ─────────────────────────────────
    champ_counts = Counter()
    for row in rows:
        names = row.get('board_names', [])
        if isinstance(names, str):
            names = json.loads(names)
        for name in names:
            champ_counts[name] += 1

    unique_champs = len(champ_counts)
    # Set 16 has ~100 champions; with random agents we should see most of them
    report.check(
        'Champion coverage > 50 unique champions',
        unique_champs > 50,
        f"{unique_champs} unique champions seen"
    )

    # ── Check 14: No dominant champion (>10% pick rate) ──────────────
    total_picks = sum(champ_counts.values())
    if total_picks > 0:
        max_champ_name, max_champ_count = champ_counts.most_common(1)[0]
        max_pct = max_champ_count / total_picks
        report.check(
            'No dominant champion (>10% pick rate)',
            max_pct <= 0.10,
            f"Most picked: {max_champ_name} at {max_pct:.1%}"
        )

    # ── Check 15: Augment coverage ──────────────────────────────────
    aug_counts = Counter()
    for row in rows:
        augs = row.get('augments', [])
        if isinstance(augs, str):
            augs = json.loads(augs)
        for aug in augs:
            aug_counts[aug] += 1

    unique_augs = len(aug_counts)
    report.check(
        'Augment coverage > 20 unique augments',
        unique_augs > 20,
        f"{unique_augs} unique augments seen"
    )

    # ── Check 16: Required fields present ───────────────────────────
    sample_row = rows[0]
    required_fields = [
        'game_id', 'round', 'player_id', 'placement', 'hp', 'gold',
        'level', 'board_count', 'win_streak', 'loss_streak',
        'board_names', 'board_stars', 'trait_names', 'trait_counts', 'augments',
    ]
    missing_fields = [f for f in required_fields if f not in sample_row]
    report.check(
        'All required fields present',
        len(missing_fields) == 0,
        f"Missing: {missing_fields}" if missing_fields else "All 15 fields present"
    )

    # ── Check 17: HP values sensible ────────────────────────────────
    hp_values = [row.get('hp', 0) for row in rows]
    if hp_values:
        min_hp = min(hp_values)
        max_hp = max(hp_values)
        report.check(
            'HP values in range (0-100)',
            min_hp >= 0 and max_hp <= 100,
            f"range: {min_hp}-{max_hp}"
        )

    # ── Check 18: Gold values sensible ──────────────────────────────
    gold_values = [row.get('gold', 0) for row in rows]
    if gold_values:
        max_gold = max(gold_values)
        avg_gold = sum(gold_values) / len(gold_values)
        report.check(
            'Gold values reasonable (avg < 100, max < 500)',
            avg_gold < 100 and max_gold < 500,
            f"avg={avg_gold:.1f}, max={max_gold}"
        )

    # ── Check 19: Performance ───────────────────────────────────────
    games_per_sec = summary.get('games_per_sec', 0)
    if games_per_sec > 0:
        report.check(
            'Performance > 0.5 games/sec',
            games_per_sec >= 0.5,
            f"{games_per_sec} games/sec"
        )

    return report


def main():
    parser = argparse.ArgumentParser(
        description='Validate TFT simulation output quality'
    )
    parser.add_argument('output_dir', type=str,
                        help='Path to batch output directory')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show details for passing checks too')
    args = parser.parse_args()

    report = validate_output(args.output_dir, verbose=args.verbose)
    report.print_report(verbose=args.verbose)

    sys.exit(0 if report.all_passed else 1)


if __name__ == '__main__':
    main()
