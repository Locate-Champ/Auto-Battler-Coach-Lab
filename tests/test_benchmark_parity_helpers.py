from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from simulator import benchmark, cloud_runner


def _row(
    round_num: int,
    player_id: int,
    units: list[dict],
    opponent_units: list[dict],
    *,
    hp: int = 100,
    opponent_hp: int = 100,
    traits: dict | None = None,
    opponent_traits: dict | None = None,
    combat_result: int | None = 1,
    damage_dealt: float = 3.0,
    damage_taken: float = 0.0,
) -> dict:
    return {
        "round": round_num,
        "player_id": player_id,
        "hp": hp,
        "gold": 0,
        "level": 5,
        "streak": 0,
        "board_count": len(units),
        "win_streak": 0,
        "loss_streak": 0,
        "num_augments": 0,
        "num_traits": len(traits or {}),
        "alive_count": 8,
        "combat_result": combat_result,
        "damage_dealt": damage_dealt,
        "damage_taken": damage_taken,
        "opponent_hp": opponent_hp,
        "traits": traits or {},
        "opponent_traits": opponent_traits or {},
        "augments": [],
        "units": units,
        "opponent_units": opponent_units,
    }


def _unit(champion_id: str, position: int) -> dict:
    return {
        "champion_id": champion_id,
        "star_level": 2,
        "items": [],
        "position": position,
    }


def test_matchup_context_infers_exact_opponents() -> None:
    rows = [
        _row(
            1,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 21)],
            hp=100,
            opponent_hp=97,
            traits={"Conqueror": 2},
            opponent_traits={"Bastion": 2},
        ),
        _row(
            1,
            1,
            [_unit("TFT16_Leona", 21)],
            [_unit("TFT16_Draven", 0)],
            hp=97,
            opponent_hp=100,
            traits={"Bastion": 2},
            opponent_traits={"Conqueror": 2},
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=3.0,
        ),
    ]

    rows_by_key = benchmark._rows_by_round_player(rows)
    context = benchmark._build_matchup_context_map(rows_by_key)

    assert context[(1, 0)]["inferred_opponent_id"] == 1
    assert context[(1, 0)]["matchup_inference"] == "exact"
    assert context[(1, 1)]["inferred_opponent_id"] == 0
    assert context[(1, 1)]["matchup_inference"] == "exact"


def test_divergence_context_identifies_board_transform() -> None:
    baseline = benchmark._normalize_training_row(
        _row(1, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
    )
    candidate = benchmark._normalize_training_row(
        _row(1, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 0)])
    )

    field_diffs = [
        {
            "field": "opponent_units",
            "baseline": baseline["opponent_units"],
            "candidate": candidate["opponent_units"],
        }
    ]
    context = benchmark._build_divergence_context(
        baseline_row=baseline,
        candidate_row=candidate,
        baseline_context=None,
        candidate_context=None,
        field_diffs=field_diffs,
    )

    assert context["origin_hint"] == "board_transform"
    assert context["mirror_alignment"] == "mirrored_positions"


def test_divergence_context_identifies_combat_resolution() -> None:
    rows = [
        _row(2, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)]),
        _row(
            2,
            1,
            [_unit("TFT16_Leona", 21)],
            [_unit("TFT16_Draven", 0)],
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=3.0,
        ),
    ]
    rows_by_key = benchmark._rows_by_round_player(rows)
    context_map = benchmark._build_matchup_context_map(rows_by_key)

    baseline = rows_by_key[(2, 0)]
    candidate = dict(baseline)
    candidate["combat_result"] = 0
    candidate["damage_dealt"] = 0.0
    candidate["damage_taken"] = 3.0

    field_diffs = [
        {"field": "combat_result", "baseline": 1, "candidate": 0},
        {"field": "damage_dealt", "baseline": 3.0, "candidate": 0.0},
        {"field": "damage_taken", "baseline": 0.0, "candidate": 3.0},
    ]
    context = benchmark._build_divergence_context(
        baseline_row=baseline,
        candidate_row=candidate,
        baseline_context=context_map[(2, 0)],
        candidate_context=context_map[(2, 0)],
        field_diffs=field_diffs,
    )

    assert context["origin_hint"] == "combat_resolution"


def test_divergence_context_identifies_missing_snapshot_origin() -> None:
    candidate = benchmark._normalize_training_row(
        _row(3, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
    )
    context = benchmark._build_divergence_context(
        baseline_row=None,
        candidate_row=candidate,
        baseline_context=None,
        candidate_context=None,
        field_diffs=None,
    )

    assert context["origin_hint"] == "matchmaking_or_snapshot_presence"
    assert context["baseline"] is None
    assert context["candidate"] is not None


def test_parity_dump_payload_contains_required_context_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    baseline_rows = [
        _row(
            4,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 21)],
            hp=96,
            opponent_hp=92,
        ),
        _row(
            4,
            1,
            [_unit("TFT16_Leona", 21)],
            [_unit("TFT16_Draven", 0)],
            hp=92,
            opponent_hp=96,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=4.0,
        ),
    ]
    candidate_rows = [
        _row(
            4,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 0)],
            hp=92,
            opponent_hp=96,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=4.0,
        ),
    ]

    def _fake_run_single_full_game_with_rows(
        engine_name: str,
        game_seed: int,
        rust_sim_cache: dict,
    ) -> dict:
        del game_seed, rust_sim_cache
        if engine_name == "python":
            rows = baseline_rows
            placement_vector = (1, 2, 0, 0, 0, 0, 0, 0)
            rank_order = (0, 1)
            top4 = (0, 1)
            placements = [(0, 1), (1, 2)]
            round_num = 4
        else:
            rows = candidate_rows
            placement_vector = (2, 1, 0, 0, 0, 0, 0, 0)
            rank_order = (1, 0)
            top4 = (0, 1)
            placements = [(1, 1), (0, 2)]
            round_num = 4
        return {
            "placements": placements,
            "placement_vector": placement_vector,
            "rank_order": rank_order,
            "top4_set": top4,
            "round_num": round_num,
            "training_rows": rows,
            "combat_debug": [
                {
                    "round": 4,
                    "p1": 0,
                    "p2": 1,
                    "is_ghost": False,
                    "debug_takedowns": [
                        {
                            "killer_team": 0,
                            "killer_api_name": "TFT16_Draven",
                            "victim_team": 1,
                            "victim_api_name": "TFT16_Leona",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        benchmark,
        "_run_single_full_game_with_rows",
        _fake_run_single_full_game_with_rows,
    )

    output_path = tmp_path / "parity_dump_schema.json"
    payload = benchmark.run_parity_dump_seed(
        baseline_engine="python",
        candidate_engine="rust_full",
        seed=123,
        sample_limit=3,
        output_path=str(output_path),
    )

    assert payload["divergence_count"] > 0
    assert "divergence_origin_counts" in payload
    assert isinstance(payload["divergence_origin_counts"], dict)

    first = payload["first_divergence"]
    assert first is not None
    assert "origin_hint" in first
    assert "context" in first

    context = first["context"]
    for key in (
        "origin_hint",
        "matchup_alignment",
        "mirror_alignment",
        "last_hit_alignment",
        "baseline",
        "candidate",
        "baseline_combat_debug",
        "candidate_combat_debug",
    ):
        assert key in context

    baseline_ctx = context["baseline"]
    candidate_ctx = context["candidate"]
    if baseline_ctx is not None:
        assert "opponent_candidates_by_units" in baseline_ctx
        assert "player_units_mirrored" in baseline_ctx
        assert "opponent_units_mirrored" in baseline_ctx
    if candidate_ctx is not None:
        assert "opponent_candidates_by_units" in candidate_ctx
        assert "player_units_mirrored" in candidate_ctx
        assert "opponent_units_mirrored" in candidate_ctx

    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert "divergence_origin_counts" in written_payload
    assert "first_divergence" in written_payload


def test_parity_dump_signatures_only_omits_raw_takedown_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    baseline_rows = [
        _row(
            4,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 21)],
            hp=96,
            opponent_hp=92,
        ),
        _row(
            4,
            1,
            [_unit("TFT16_Leona", 21)],
            [_unit("TFT16_Draven", 0)],
            hp=92,
            opponent_hp=96,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=4.0,
        ),
    ]
    candidate_rows = [
        _row(
            4,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 0)],
            hp=92,
            opponent_hp=96,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=4.0,
        ),
    ]

    def _fake_run_single_full_game_with_rows(
        engine_name: str,
        game_seed: int,
        rust_sim_cache: dict,
    ) -> dict:
        del game_seed, rust_sim_cache
        rows = baseline_rows if engine_name == "python" else candidate_rows
        return {
            "placements": [(0, 1), (1, 2)],
            "placement_vector": (1, 2, 0, 0, 0, 0, 0, 0),
            "rank_order": (0, 1),
            "top4_set": (0, 1),
            "round_num": 4,
            "training_rows": rows,
            "combat_debug": [
                {
                    "round": 4,
                    "p1": 0,
                    "p2": 1,
                    "is_ghost": False,
                    "debug_takedowns": [
                        {
                            "killer_team": 0,
                            "killer_api_name": "TFT16_Draven",
                            "victim_team": 1,
                            "victim_api_name": "TFT16_Leona",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        benchmark,
        "_run_single_full_game_with_rows",
        _fake_run_single_full_game_with_rows,
    )

    payload = benchmark.run_parity_dump_seed(
        baseline_engine="python",
        candidate_engine="rust_full",
        seed=123,
        sample_limit=3,
        output_path=str(tmp_path / "parity_dump_signatures_only.json"),
        parity_dump_signatures_only=True,
    )

    assert payload["parity_dump_signatures_only"] is True
    first = payload["first_divergence"]
    assert first is not None
    context = first["context"]
    assert context["baseline_combat_debug"] is not None
    assert context["candidate_combat_debug"] is not None
    assert "debug_takedowns" not in context["baseline_combat_debug"]
    assert "debug_takedowns" not in context["candidate_combat_debug"]
    assert "player_last_hit_signature" in context["baseline_combat_debug"]
    assert "player_last_hit_signature" in context["candidate_combat_debug"]


def test_cli_parity_dump_signatures_only_artifact_is_smaller(
    tmp_path: Path,
    monkeypatch,
) -> None:
    baseline_rows = [
        _row(
            9,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 21)],
            hp=96,
            opponent_hp=92,
        ),
        _row(
            9,
            1,
            [_unit("TFT16_Leona", 21)],
            [_unit("TFT16_Draven", 0)],
            hp=92,
            opponent_hp=96,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=4.0,
        ),
    ]
    candidate_rows = [
        _row(
            9,
            0,
            [_unit("TFT16_Draven", 0)],
            [_unit("TFT16_Leona", 0)],
            hp=92,
            opponent_hp=96,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=4.0,
        ),
    ]
    verbose_takedowns = [
        {
            "killer_team": i % 2,
            "killer_api_name": "TFT16_Draven" if i % 2 == 0 else "TFT16_Leona",
            "victim_team": 1 if i % 2 == 0 else 0,
            "victim_api_name": "TFT16_Leona" if i % 2 == 0 else "TFT16_Draven",
        }
        for i in range(120)
    ]

    def _fake_run_single_full_game_with_rows(
        engine_name: str,
        game_seed: int,
        rust_sim_cache: dict,
    ) -> dict:
        del game_seed, rust_sim_cache
        rows = baseline_rows if engine_name == "python" else candidate_rows
        return {
            "placements": [(0, 1), (1, 2)],
            "placement_vector": (1, 2, 0, 0, 0, 0, 0, 0),
            "rank_order": (0, 1),
            "top4_set": (0, 1),
            "round_num": 9,
            "training_rows": rows,
            "combat_debug": [
                {
                    "round": 9,
                    "p1": 0,
                    "p2": 1,
                    "is_ghost": False,
                    "debug_takedowns": verbose_takedowns,
                }
            ],
        }

    monkeypatch.setattr(
        benchmark,
        "_run_single_full_game_with_rows",
        _fake_run_single_full_game_with_rows,
    )

    full_output = tmp_path / "parity_dump_full.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark.py",
            "--parity-only",
            "--parity-engines",
            "python,rust_full",
            "--parity-dump-seed",
            "9",
            "--parity-dump-output",
            str(full_output),
        ],
    )
    benchmark.main()

    compact_output = tmp_path / "parity_dump_signatures.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark.py",
            "--parity-only",
            "--parity-engines",
            "python,rust_full",
            "--parity-dump-seed",
            "9",
            "--parity-dump-output",
            str(compact_output),
            "--parity-dump-signatures-only",
        ],
    )
    benchmark.main()

    full_payload = json.loads(full_output.read_text(encoding="utf-8"))
    compact_payload = json.loads(compact_output.read_text(encoding="utf-8"))
    assert full_payload["parity_dump_signatures_only"] is False
    assert compact_payload["parity_dump_signatures_only"] is True
    assert compact_output.stat().st_size < full_output.stat().st_size


def test_parity_dump_missing_candidate_snapshot_shape(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shared_row = _row(
        5,
        0,
        [_unit("TFT16_Draven", 0)],
        [_unit("TFT16_Leona", 21)],
        hp=95,
        opponent_hp=90,
    )
    baseline_rows = [
        shared_row,
        _row(
            5,
            1,
            [_unit("TFT16_Leona", 21)],
            [_unit("TFT16_Draven", 0)],
            hp=90,
            opponent_hp=95,
            combat_result=0,
            damage_dealt=0.0,
            damage_taken=5.0,
        ),
    ]
    candidate_rows = [shared_row]

    def _fake_run_single_full_game_with_rows(
        engine_name: str,
        game_seed: int,
        rust_sim_cache: dict,
    ) -> dict:
        del game_seed, rust_sim_cache
        rows = baseline_rows if engine_name == "python" else candidate_rows
        return {
            "placements": [(0, 1), (1, 2)],
            "placement_vector": (1, 2, 0, 0, 0, 0, 0, 0),
            "rank_order": (0, 1),
            "top4_set": (0, 1),
            "round_num": 5,
            "training_rows": rows,
            "combat_debug": [],
        }

    monkeypatch.setattr(
        benchmark,
        "_run_single_full_game_with_rows",
        _fake_run_single_full_game_with_rows,
    )

    output_path = tmp_path / "parity_dump_missing_candidate.json"
    payload = benchmark.run_parity_dump_seed(
        baseline_engine="python",
        candidate_engine="rust_full",
        seed=55,
        sample_limit=5,
        output_path=str(output_path),
    )

    first = payload["first_divergence"]
    assert first is not None
    assert first["type"] == "missing_candidate_snapshot"
    assert first["origin_hint"] == "matchmaking_or_snapshot_presence"

    context = first["context"]
    assert context["baseline"] is not None
    assert context["candidate"] is None
    assert context["origin_hint"] == "matchmaking_or_snapshot_presence"
    assert "matchup_alignment" in context
    assert "mirror_alignment" in context

    written_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert written_payload["first_divergence"]["type"] == "missing_candidate_snapshot"


def test_divergence_origin_counts_labels_are_known(
    tmp_path: Path,
    monkeypatch,
) -> None:
    baseline_rows = [
        _row(6, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)]),
        _row(6, 1, [_unit("TFT16_Leona", 21)], [_unit("TFT16_Draven", 0)]),
    ]
    candidate_rows = [
        _row(6, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 0)]),
    ]

    def _fake_run_single_full_game_with_rows(
        engine_name: str,
        game_seed: int,
        rust_sim_cache: dict,
    ) -> dict:
        del game_seed, rust_sim_cache
        rows = baseline_rows if engine_name == "python" else candidate_rows
        return {
            "placements": [(0, 1), (1, 2)],
            "placement_vector": (1, 2, 0, 0, 0, 0, 0, 0),
            "rank_order": (0, 1),
            "top4_set": (0, 1),
            "round_num": 6,
            "training_rows": rows,
            "combat_debug": [],
        }

    monkeypatch.setattr(
        benchmark,
        "_run_single_full_game_with_rows",
        _fake_run_single_full_game_with_rows,
    )

    payload = benchmark.run_parity_dump_seed(
        baseline_engine="python",
        candidate_engine="rust_full",
        seed=77,
        sample_limit=5,
        output_path=str(tmp_path / "parity_dump_origin_labels.json"),
    )

    known_labels = {
        "matchmaking_or_snapshot_presence",
        "matchmaking",
        "board_transform",
        "matchmaking_or_board_state",
        "combat_resolution",
        "combat_resolution_or_downstream",
        "last_hit_attribution_drift",
        "unknown",
    }
    observed_labels = set(payload["divergence_origin_counts"].keys())
    assert observed_labels
    assert observed_labels.issubset(known_labels)


def test_infer_divergence_origin_identifies_last_hit_attribution_drift() -> None:
    baseline = benchmark._normalize_training_row(
        _row(8, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
    )
    candidate = dict(baseline)
    candidate["combat_result"] = 0

    observed = benchmark._infer_divergence_origin(
        baseline_row=baseline,
        candidate_row=candidate,
        baseline_context={"inferred_opponent_id": 1},
        candidate_context={"inferred_opponent_id": 1},
        field_diffs=[{"field": "combat_result", "baseline": 1, "candidate": 0}],
        baseline_combat_debug={
            "player_last_hit_signature": (("TFT16_Draven", "TFT16_Leona", 1),),
        },
        candidate_combat_debug={
            "player_last_hit_signature": (("TFT16_Braum", "TFT16_Leona", 1),),
        },
    )

    assert observed == "last_hit_attribution_drift"


def test_infer_divergence_origin_missing_combat_debug_on_one_side_avoids_last_hit_drift() -> None:
    baseline = benchmark._normalize_training_row(
        _row(8, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
    )
    candidate = dict(baseline)
    candidate["combat_result"] = 0

    observed = benchmark._infer_divergence_origin(
        baseline_row=baseline,
        candidate_row=candidate,
        baseline_context={"inferred_opponent_id": 1},
        candidate_context={"inferred_opponent_id": 1},
        field_diffs=[{"field": "combat_result", "baseline": 1, "candidate": 0}],
        baseline_combat_debug={
            "player_last_hit_signature": (("TFT16_Draven", "TFT16_Leona", 1),),
        },
        candidate_combat_debug={
            "player_last_hit_signature": (),
        },
    )

    assert observed == "combat_resolution"


def test_infer_divergence_origin_zero_takedowns_both_sides_avoids_last_hit_drift() -> None:
    baseline = benchmark._normalize_training_row(
        _row(8, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
    )
    candidate = dict(baseline)
    candidate["combat_result"] = 0

    observed = benchmark._infer_divergence_origin(
        baseline_row=baseline,
        candidate_row=candidate,
        baseline_context={"inferred_opponent_id": 1},
        candidate_context={"inferred_opponent_id": 1},
        field_diffs=[{"field": "combat_result", "baseline": 1, "candidate": 0}],
        baseline_combat_debug={
            "player_last_hit_signature": (),
        },
        candidate_combat_debug={
            "player_last_hit_signature": (),
        },
    )

    assert observed == "combat_resolution"


@pytest.mark.parametrize(
    (
        "baseline_row",
        "candidate_row",
        "baseline_context",
        "candidate_context",
        "field_diffs",
        "expected",
    ),
    [
        pytest.param(
            None,
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            None,
            None,
            None,
            "matchmaking_or_snapshot_presence",
            id="matchmaking_or_snapshot_presence",
        ),
        pytest.param(
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            {"inferred_opponent_id": 1},
            {"inferred_opponent_id": 2},
            [{"field": "hp", "baseline": 100, "candidate": 99}],
            "matchmaking",
            id="matchmaking",
        ),
        pytest.param(
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 0)])
            ),
            {"inferred_opponent_id": 1},
            {"inferred_opponent_id": 1},
            [{"field": "opponent_units", "baseline": "x", "candidate": "y"}],
            "board_transform",
            id="board_transform",
        ),
        pytest.param(
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 14)])
            ),
            {"inferred_opponent_id": 1},
            {"inferred_opponent_id": None},
            [{"field": "opponent_units", "baseline": "x", "candidate": "z"}],
            "matchmaking_or_board_state",
            id="matchmaking_or_board_state",
        ),
        pytest.param(
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            {"inferred_opponent_id": 1},
            {"inferred_opponent_id": 1},
            [{"field": "combat_result", "baseline": 1, "candidate": 0}],
            "combat_resolution",
            id="combat_resolution",
        ),
        pytest.param(
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            {"inferred_opponent_id": 1},
            {"inferred_opponent_id": 1},
            [
                {"field": "combat_result", "baseline": 1, "candidate": 0},
                {"field": "hp", "baseline": 96, "candidate": 90},
            ],
            "combat_resolution_or_downstream",
            id="combat_resolution_or_downstream",
        ),
        pytest.param(
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            benchmark._normalize_training_row(
                _row(7, 0, [_unit("TFT16_Draven", 0)], [_unit("TFT16_Leona", 21)])
            ),
            {"inferred_opponent_id": 1},
            {"inferred_opponent_id": 1},
            [{"field": "gold", "baseline": 0, "candidate": 2}],
            "unknown",
            id="unknown",
        ),
    ],
)
def test_infer_divergence_origin_known_labels(
    baseline_row: dict | None,
    candidate_row: dict | None,
    baseline_context: dict | None,
    candidate_context: dict | None,
    field_diffs: list[dict] | None,
    expected: str,
) -> None:
    observed = benchmark._infer_divergence_origin(
        baseline_row=baseline_row,
        candidate_row=candidate_row,
        baseline_context=baseline_context,
        candidate_context=candidate_context,
        field_diffs=field_diffs,
    )
    assert observed == expected


def test_cloud_runner_parquet_guard_missing_method_includes_rebuild_hint() -> None:
    class MissingMethodSimulator:
        pass

    validated = set()
    with pytest.raises(RuntimeError) as exc:
        cloud_runner._ensure_rust_parquet_method_support(
            MissingMethodSimulator(),
            "run_games_batch_parquet_to_file",
            validated,
        )

    message = str(exc.value)
    assert "missing 'run_games_batch_parquet_to_file'" in message
    assert "maturin build --release" in message
    assert str(Path(sys.executable)) in message


def test_cloud_runner_parquet_guard_missing_kwargs_reports_names() -> None:
    class LegacySimulator:
        def run_games_batch_parquet_to_file(
            self,
            game_ids,
            seeds,
            output_path,
            compression=None,
            use_dictionary=False,
            write_statistics=False,
        ):
            del game_ids, seeds, output_path, compression, use_dictionary, write_statistics
            return None

    validated = set()
    with pytest.raises(RuntimeError) as exc:
        cloud_runner._ensure_rust_parquet_method_support(
            LegacySimulator(),
            "run_games_batch_parquet_to_file",
            validated,
        )

    message = str(exc.value)
    assert "missing expected kwargs" in message
    assert "row_group_size" in message
    assert "write_batch_size" in message


def test_cloud_runner_parquet_guard_accepts_current_signature() -> None:
    class CurrentSimulator:
        def run_games_batch_parquet_to_file(
            self,
            game_ids,
            seeds,
            output_path,
            agent_mix=None,
            include_training_rows=True,
            rayon_threads=None,
            compression=None,
            use_dictionary=False,
            write_statistics=False,
            row_group_size=None,
            write_batch_size=None,
        ):
            del (
                game_ids,
                seeds,
                output_path,
                agent_mix,
                include_training_rows,
                rayon_threads,
                compression,
                use_dictionary,
                write_statistics,
                row_group_size,
                write_batch_size,
            )
            return None

    validated = set()
    simulator = CurrentSimulator()
    cloud_runner._ensure_rust_parquet_method_support(
        simulator,
        "run_games_batch_parquet_to_file",
        validated,
    )
    cloud_runner._ensure_rust_parquet_method_support(
        simulator,
        "run_games_batch_parquet_to_file",
        validated,
    )
    assert "run_games_batch_parquet_to_file" in validated


def test_cloud_runner_extract_signature_uses_text_signature_fallback(
    monkeypatch,
) -> None:
    def _raise_type_error(_method):
        raise TypeError("no signature available")

    monkeypatch.setattr(cloud_runner.inspect, "signature", _raise_type_error)

    class TextSignatureMethod:
        __text_signature__ = (
            "($self, game_ids, seeds, output_path, compression=None, "
            "use_dictionary=False, write_statistics=False, row_group_size=None, write_batch_size=None)"
        )

    names = cloud_runner._extract_signature_parameter_names(TextSignatureMethod())
    assert "self" in names
    assert "compression" in names
    assert "use_dictionary" in names
    assert "write_statistics" in names
    assert "row_group_size" in names
    assert "write_batch_size" in names
