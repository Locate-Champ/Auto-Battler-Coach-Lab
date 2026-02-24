from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from coach.actions import DecisionType, ItemSlamDetails, ShopBuyDetails
from coach.coach import Coach
from coach.modules.items.candidates import generate_candidates as item_candidates
from coach.modules.items.execute import execute as execute_item_action
from coach.modules.shop.candidates import generate_candidates as shop_candidates
from coach.modules.shop.execute import execute as execute_shop_action
from coach.odds import estimate_upgrade_hit_prob
from coach.offline.eval_coach import _compare_reports, _iter_eval_set_states
from coach.state import GameState, OpponentState, PlayerState, ShopUnit, UnitState
from coach.weights import CoachConfig, weights_for_stage


def _state_for_items() -> GameState:
    player = PlayerState(level=6, hp=78, gold=22, win_streak=0, loss_streak=2)
    board = (
        UnitState(
            instance_id="u0",
            champion_id="TFT16_Draven",
            star_level=2,
            items=(),
            position=(0, 6),
            location="board",
        ),
        UnitState(
            instance_id="u1",
            champion_id="TFT16_Leona",
            star_level=2,
            items=(),
            position=(3, 3),
            location="board",
        ),
    )
    opponent = OpponentState(
        opponent_id="opp",
        board=(
            UnitState(
                instance_id="o0",
                champion_id="TFT16_Sion",
                star_level=2,
                items=(),
                position=(3, 3),
                location="board",
            ),
        ),
    )
    return GameState(
        stage="3-2",
        player=player,
        board=board,
        items=("BF_Sword", "Recurve_Bow"),
        opponents=(opponent,),
    )


def _cfg_for_regression_gate(stage_number: int) -> CoachConfig:
    # Fixed seed/budget for CI-friendly regression gating.
    return CoachConfig(
        weights=weights_for_stage(stage_number=stage_number),
        combat_base_seed=123,
        max_candidates_items=20,
        max_candidates_position=20,
        max_candidates_econ=20,
        max_candidates_shop=20,
        top_k=1,
        sim_budget_pass1=24,
        sim_budget_pass2=0,
        sim_budget_pass3=0,
        topk_refine=0,
        max_total_sims=1024,
    )


def _cfg_for_position_regression_gate(stage_number: int) -> CoachConfig:
    # Position candidates are evaluator-tied; ensure we simulate enough actions to observe
    # the tempo delta rather than falling back to proxy-only scoring.
    return CoachConfig(
        weights=weights_for_stage(stage_number=stage_number),
        combat_base_seed=123,
        max_candidates_items=20,
        max_candidates_position=20,
        max_candidates_econ=20,
        max_candidates_shop=20,
        top_k=1,
        sim_budget_pass1=12,
        sim_budget_pass2=0,
        sim_budget_pass3=0,
        topk_refine=8,
        max_total_sims=1024,
    )


def _state_for_items_regression_gate() -> GameState:
    # A small, deterministic matchup where a slam should clearly swing the fight.
    # Calibrated for Rust engine: 1★ pair loses to 2★+1★ pair without items,
    # but GiantSlayer slam on Draven flips the matchup to 100% win.
    player = PlayerState(level=6, hp=78, gold=22, win_streak=0, loss_streak=2)
    board = (
        UnitState(
            instance_id="u0",
            champion_id="TFT16_Draven",
            star_level=1,
            items=(),
            position=(0, 6),
            location="board",
        ),
        UnitState(
            instance_id="u1",
            champion_id="TFT16_Leona",
            star_level=1,
            items=(),
            position=(3, 3),
            location="board",
        ),
    )
    opponent = OpponentState(
        opponent_id="opp",
        board=(
            UnitState(
                instance_id="o0",
                champion_id="TFT16_Sion",
                star_level=2,
                items=(),
                position=(3, 3),
                location="board",
            ),
            UnitState(
                instance_id="o1",
                champion_id="TFT16_Leona",
                star_level=1,
                items=(),
                position=(3, 0),
                location="board",
            ),
        ),
    )
    return GameState(
        stage="3-2",
        player=player,
        board=board,
        items=("BF_Sword", "Recurve_Bow"),
        opponents=(opponent,),
    )


def _state_for_shop_regression_gate() -> GameState:
    # Buying the 3rd copy should upgrade Ekko -> 2★ and swing the fight.
    # Calibrated for Rust engine: 1★ Ekko+Leona lose to 1★ Sion+Leona pair,
    # but buying Ekko → 2★ upgrade flips the matchup (delta ≈ 0.85).
    player = PlayerState(level=6, hp=64, gold=10, win_streak=0, loss_streak=0)
    board = (
        UnitState(
            instance_id="u0",
            champion_id="TFT16_Ekko",
            star_level=1,
            items=(),
            position=(3, 0),
            location="board",
        ),
        UnitState(
            instance_id="u1",
            champion_id="TFT16_Leona",
            star_level=1,
            items=(),
            position=(3, 3),
            location="board",
        ),
    )
    bench = (UnitState(instance_id="b0", champion_id="TFT16_Ekko", star_level=1, location="bench"),)
    opponent = OpponentState(
        opponent_id="opp",
        board=(
            UnitState(
                instance_id="o0",
                champion_id="TFT16_Sion",
                star_level=1,
                items=(),
                position=(3, 3),
                location="board",
            ),
            UnitState(
                instance_id="o1",
                champion_id="TFT16_Leona",
                star_level=1,
                items=(),
                position=(3, 0),
                location="board",
            ),
        ),
    )
    return GameState(
        stage="3-2",
        player=player,
        board=board,
        bench=bench,
        shop=(ShopUnit(champion_id="TFT16_Ekko", cost=2),),
        items=(),
        opponents=(opponent,),
    )


def _state_for_position_regression_gate() -> GameState:
    player = PlayerState(level=8, hp=60, gold=20, win_streak=0, loss_streak=0)
    board = (
        UnitState(
            instance_id="carry",
            champion_id="TFT16_Draven",
            star_level=2,
            items=("TFT_Item_InfinityEdge",),
            position=(2, 2),
            location="board",
        ),
        UnitState(
            instance_id="tank1",
            champion_id="TFT16_Leona",
            star_level=2,
            items=(),
            position=(2, 3),
            location="board",
        ),
        UnitState(
            instance_id="tank2",
            champion_id="TFT16_Sion",
            star_level=2,
            items=(),
            position=(2, 4),
            location="board",
        ),
    )
    opponent = OpponentState(
        opponent_id="opp",
        board=(
            UnitState(
                instance_id="oc",
                champion_id="TFT16_Draven",
                star_level=2,
                items=("TFT_Item_InfinityEdge", "TFT_Item_GiantSlayer"),
                position=(3, 2),
                location="board",
            ),
            UnitState(
                instance_id="ot1",
                champion_id="TFT16_Leona",
                star_level=2,
                items=(),
                position=(3, 3),
                location="board",
            ),
            UnitState(
                instance_id="ot2",
                champion_id="TFT16_Sion",
                star_level=2,
                items=(),
                position=(3, 4),
                location="board",
            ),
        ),
    )
    return GameState(stage="3-2", player=player, board=board, opponents=(opponent,))


def _state_for_econ_regression_gate() -> GameState:
    player = PlayerState(level=5, hp=35, gold=20, win_streak=0, loss_streak=0)
    bench = (
        UnitState(instance_id="a0", champion_id="TFT16_Ashe", star_level=1, location="bench"),
        UnitState(instance_id="a1", champion_id="TFT16_Ashe", star_level=1, location="bench"),
    )
    return GameState(stage="4-2", player=player, board=(), bench=bench, opponents=())


def test_item_slam_generation_and_execute_consumes_components() -> None:
    state = _state_for_items()
    actions = item_candidates(state)
    slam = next(
        (a for a in actions if isinstance(getattr(a, "details", None), ItemSlamDetails)), None
    )
    assert slam is not None

    next_state = execute_item_action(state, slam)
    assert len(next_state.items) == len(state.items) - 2

    target = next(u for u in next_state.board if u.instance_id == slam.details.target_unit_id)
    assert slam.details.resulting_item in target.items


def test_coach_recommend_items_returns_sorted_topk() -> None:
    state = _state_for_items()
    coach = Coach()
    cfg = CoachConfig(
        weights=weights_for_stage(stage_number=state.stage_number),
        combat_base_seed=1,
        max_candidates_items=20,
        max_candidates_position=20,
        max_candidates_econ=20,
        max_candidates_shop=20,
        top_k=2,
        sim_budget_pass1=4,
        sim_budget_pass2=0,
        sim_budget_pass3=0,
        topk_refine=0,
        max_total_sims=256,
    )
    recs = coach.recommend(state, DecisionType.ITEMS, config=cfg)
    assert len(recs) == 2
    assert recs[0].score.total_score >= recs[1].score.total_score


def test_coach_regression_gate_items_slam_improves_tempo() -> None:
    state = _state_for_items_regression_gate()
    coach = Coach()
    cfg = _cfg_for_regression_gate(stage_number=state.stage_number)
    recs = coach.recommend(state, DecisionType.ITEMS, config=cfg, top_k=1)
    assert len(recs) == 1

    top = recs[0]
    assert top.action.action_id.startswith("items:slam:")
    assert top.score.tempo.opponent_policy == "next_opponent"
    assert top.score.tempo.n_sims > 0
    assert top.score.tempo.win_prob_delta >= 0.80


def test_shop_buy_action_spends_gold_and_adds_unit() -> None:
    player = PlayerState(level=6, hp=78, gold=10, win_streak=0, loss_streak=0)
    state = GameState(
        stage="3-2",
        player=player,
        board=(),
        bench=(),
        shop=(ShopUnit(champion_id="TFT16_Ekko", cost=2),),
        items=(),
        opponents=(),
    )

    actions = shop_candidates(state)
    buy = next(
        (
            a
            for a in actions
            if isinstance(getattr(a, "details", None), ShopBuyDetails)
            and a.details.champion_id == "TFT16_Ekko"
        ),
        None,
    )
    assert buy is not None

    next_state = execute_shop_action(state, buy)
    assert next_state.player.gold == 8
    assert any(u.champion_id == "TFT16_Ekko" for u in next_state.bench)


def test_coach_regression_gate_shop_buy_upgrade_improves_tempo() -> None:
    state = _state_for_shop_regression_gate()
    coach = Coach()
    cfg = _cfg_for_regression_gate(stage_number=state.stage_number)
    recs = coach.recommend(state, DecisionType.SHOP, config=cfg, top_k=1)
    assert len(recs) == 1

    top = recs[0]
    assert top.action.action_id == "shop:buy:TFT16_Ekko"
    assert top.score.tempo.opponent_policy == "next_opponent"
    assert top.score.tempo.n_sims > 0
    assert top.score.tempo.win_prob_delta >= 0.80


def test_coach_regression_gate_positioning_improves_tempo() -> None:
    state = _state_for_position_regression_gate()
    coach = Coach()
    cfg = _cfg_for_position_regression_gate(stage_number=state.stage_number)
    recs = coach.recommend(state, DecisionType.POSITION, config=cfg, top_k=1)
    assert len(recs) == 1

    top = recs[0]
    assert top.action.action_id != "position:hold"
    assert top.score.tempo.opponent_policy == "next_opponent"
    assert top.score.tempo.n_sims > 0
    assert top.score.tempo.win_prob_delta >= 0.10


def test_monte_carlo_upgrade_lookahead_returns_prob_and_targets() -> None:
    player = PlayerState(level=1, hp=100, gold=10, win_streak=0, loss_streak=0)
    state = GameState(
        stage="1-2",
        player=player,
        board=(),
        bench=(
            UnitState(instance_id="a0", champion_id="TFT16_Ashe", star_level=1, location="bench"),
            UnitState(instance_id="a1", champion_id="TFT16_Ashe", star_level=1, location="bench"),
        ),
        shop=(),
        items=(),
        opponents=(),
    )

    prob_any, per_target, targets = estimate_upgrade_hit_prob(
        state, level=1, rolls=2, seed=1, num_trials=50
    )
    assert 0.0 <= prob_any <= 1.0
    assert "TFT16_Ashe" in targets
    assert "TFT16_Ashe" in per_target


def test_coach_regression_gate_econ_roll_includes_upgrade_prob() -> None:
    state = _state_for_econ_regression_gate()
    coach = Coach()
    cfg = _cfg_for_regression_gate(stage_number=state.stage_number)
    recs = coach.recommend(state, DecisionType.ECON, config=cfg, top_k=1)
    assert len(recs) == 1

    top = recs[0]
    assert top.action.title == "Stabilize: roll to 10g (~5x)"
    assert top.score.econ.upgrade_hit_prob is not None
    assert top.score.econ.upgrade_hit_prob >= 0.25
    assert any(cid == "TFT16_Ashe" for cid, _ in (top.score.econ.upgrade_top_targets or ()))


def test_eval_coach_can_load_eval_set_jsonl(tmp_path: Path) -> None:
    state = _state_for_shop_regression_gate()
    p = tmp_path / "eval_set.jsonl"
    p.write_text(json.dumps(asdict(state), separators=(",", ":")) + "\n", encoding="utf-8")

    loaded = list(_iter_eval_set_states(p))
    assert loaded == [state]


def test_eval_coach_report_gate_detects_regression() -> None:
    baseline = {
        "decisions": {
            "items": {
                "n": 10,
                "mean_win_prob_delta": 0.10,
                "pct_positive_win_prob_delta": 0.60,
                "mean_expected_hp_delta": -2.0,
            }
        }
    }
    current = {
        "decisions": {
            "items": {
                "n": 10,
                "mean_win_prob_delta": 0.05,
                "pct_positive_win_prob_delta": 0.60,
                "mean_expected_hp_delta": -2.0,
            }
        }
    }

    failures = _compare_reports(
        baseline=baseline,
        current=current,
        max_regress_mean_win_prob_delta=0.01,
        max_regress_pct_positive_win_prob_delta=0.05,
        max_regress_mean_expected_hp_delta=0.5,
    )
    assert any("items.mean_win_prob_delta" in f for f in failures)
