"""Tests for simulation output validation policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from simulator.validate_output import validate_output


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _build_rows(num_games: int, severe_duplicate_games: set[int]) -> list[dict]:
    rows: list[dict] = []
    for game_id in range(num_games):
        if game_id in severe_duplicate_games:
            placements = [1, 2, 3, 4, 8, 8, 8, 8]
        else:
            placements = [1, 2, 3, 4, 5, 6, 7, 8]

        for round_num in range(1, 17):
            for player_id in range(8):
                champion_name = f"champ_{(game_id * 17 + player_id * 5 + round_num) % 120}"
                augment_name = f"aug_{(game_id * 11 + player_id * 3 + round_num) % 60}"
                rows.append(
                    {
                        "game_id": game_id,
                        "round": round_num,
                        "player_id": player_id,
                        "placement": placements[player_id],
                        "hp": max(1, 100 - (round_num * 2) - player_id),
                        "gold": (game_id + player_id + round_num) % 60,
                        "level": min(10, 3 + (round_num // 3)),
                        "board_count": min(10, 1 + (round_num // 2)),
                        "win_streak": 1 if (game_id + player_id + round_num) % 2 == 0 else 0,
                        "loss_streak": 0 if (game_id + player_id + round_num) % 2 == 0 else 1,
                        "board_names": [champion_name],
                        "board_stars": [2],
                        "trait_names": [f"trait_{(player_id + round_num) % 20}"],
                        "trait_counts": [1 + ((round_num + player_id) % 3)],
                        "augments": [augment_name],
                    }
                )
    return rows


def _write_summary(path: Path, num_games: int, total_rows: int) -> None:
    summary = {
        "num_games": num_games,
        "num_errors": 0,
        "num_workers": 8,
        "total_time_sec": float(num_games),
        "games_per_sec": 1.0,
        "avg_game_time_sec": 1.0,
        "avg_rounds": 16.0,
        "total_training_rows": total_rows,
        "total_chunks": 1,
    }
    path.write_text(json.dumps(summary), encoding="utf-8")


def _check(report, name: str) -> dict:
    return next(check for check in report.checks if check["name"] == name)


def test_validate_output_allows_rare_severe_duplicate_placements(tmp_path: Path) -> None:
    output_dir = tmp_path / "run_pass"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _build_rows(num_games=100, severe_duplicate_games={0})
    _write_jsonl(output_dir / "chunk_0000.jsonl", rows)
    _write_summary(output_dir / "summary.json", num_games=100, total_rows=len(rows))

    report = validate_output(str(output_dir))
    duplicate_check = _check(report, "No excessive placement duplicates")
    assert duplicate_check["passed"] is True
    assert report.all_passed is True


def test_validate_output_fails_when_severe_duplicate_rate_is_high(tmp_path: Path) -> None:
    output_dir = tmp_path / "run_fail"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = _build_rows(num_games=100, severe_duplicate_games={0, 1, 2})
    _write_jsonl(output_dir / "chunk_0000.jsonl", rows)
    _write_summary(output_dir / "summary.json", num_games=100, total_rows=len(rows))

    report = validate_output(str(output_dir))
    duplicate_check = _check(report, "No excessive placement duplicates")
    assert duplicate_check["passed"] is False
    assert report.all_passed is False
