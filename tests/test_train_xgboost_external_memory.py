"""Integration coverage for external-memory XGBoost training."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _make_rows(num_games: int = 40) -> list[dict]:
    rows: list[dict] = []
    for game_id in range(1, num_games + 1):
        for player_id in (0, 1):
            base_hp = 100 - ((game_id + player_id) % 15)
            placement = ((game_id + player_id) % 8) + 1
            for round_num in (2, 3, 4):
                combat_result = 1 if (game_id + player_id + round_num) % 2 == 0 else 0
                win_streak = 1 if combat_result == 1 else 0
                loss_streak = 1 if combat_result == 0 else 0
                rows.append(
                    {
                        "game_id": game_id,
                        "player_id": player_id,
                        "round": round_num,
                        "level": min(10, 3 + round_num),
                        "hp": max(1, base_hp - round_num * 3),
                        "gold": (game_id * round_num + player_id * 7) % 60,
                        "win_streak": win_streak,
                        "loss_streak": loss_streak,
                        "placement": placement,
                        "combat_result": combat_result,
                        "board_names": ["fiddlesticks", "jinx"]
                        if player_id == 0
                        else ["vayne", "ornn"],
                        "board_stars": [2, 1],
                        "trait_names": ["harvester", "gunslinger"],
                        "trait_counts": [1, 2],
                        "augments": ["TFT10_Augment_GoingLong", "TFT10_Augment_CrashTestDummies"],
                    }
                )
    return rows


def test_external_memory_xgboost_training(tmp_path: Path) -> None:
    pytest.importorskip("xgboost")

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(data_dir / "chunk_0000.jsonl", _make_rows())

    output_dir = tmp_path / "out"
    command = [
        sys.executable,
        "-m",
        "models.train_xgboost",
        "--data",
        str(data_dir),
        "--task",
        "fight",
        "--output",
        str(output_dir),
        "--n-estimators",
        "8",
        "--test-size",
        "0.3",
        "--external-memory",
        "--external-batch-size",
        "64",
        "--row-batch-size",
        "128",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, f"{completed.stdout}\n{completed.stderr}"

    model_path = output_dir / "fight_xgboost.json"
    report_path = output_dir / "fight_training_report.json"
    assert model_path.exists()
    assert report_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["training_mode"] == "external_memory"
    assert int(report["split_stats"]["train_examples"]) > 0
    assert int(report["split_stats"]["test_examples"]) > 0
    assert "accuracy" in report["metrics"]
