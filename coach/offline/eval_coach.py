from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from coach.actions import DecisionType
from coach.coach import Coach
from coach.state import GameState, OpponentState, PlayerState, ShopUnit, UnitState
from coach.weights import CoachConfig, weights_for_stage


def _parse_json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return default
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, type(default)) else default
        except json.JSONDecodeError:
            return default
    return default


def _stage_from_round_num(round_num: int) -> str:
    # Brute-force invert the mapping used by coach.coach._round_num_from_stage.
    from coach.coach import _round_num_from_stage

    r = int(round_num)
    for stage_num in range(1, 9):
        for round_in_stage in range(1, 8):
            tag = f"{stage_num}-{round_in_stage}"
            if _round_num_from_stage(tag) == r:
                return tag
    return "4-2"


def _units_from_snapshot(units_value: Any, prefix: str) -> tuple[UnitState, ...]:
    units = _parse_json_value(units_value, [])
    out: list[UnitState] = []
    for idx, u in enumerate(units):
        if not isinstance(u, dict):
            continue
        cid = u.get("champion_id")
        if not isinstance(cid, str) or not cid:
            continue
        star = int(u.get("star_level") or 1)
        items = u.get("items") or []
        if not isinstance(items, list):
            items = []
        pos = u.get("position")
        if isinstance(pos, int):
            row = int(pos) // 7
            col = int(pos) % 7
            position = (row, col)
        else:
            position = None
        out.append(
            UnitState(
                instance_id=f"{prefix}_{idx}",
                champion_id=cid,
                star_level=star,
                items=tuple(str(x) for x in items),
                position=position,
                location="board",
            )
        )
    return tuple(out)


def coach_state_from_row(row: dict) -> GameState:
    stage = _stage_from_round_num(int(row.get("round") or 0))

    player = PlayerState(
        level=int(row.get("level") or 1),
        hp=int(row.get("hp") or 100),
        gold=int(row.get("gold") or 0),
        win_streak=int(row.get("win_streak") or 0),
        loss_streak=int(row.get("loss_streak") or 0),
    )

    board = _units_from_snapshot(row.get("units"), prefix="self")
    opp_board = _units_from_snapshot(row.get("opponent_units"), prefix="opp")
    opponents = ()
    if opp_board:
        opponents = (
            OpponentState(
                opponent_id="opp",
                board=opp_board,
                level=int(row.get("opponent_level") or 0) or None,
                hp=int(row.get("opponent_hp") or 0) or None,
                augments=tuple(_parse_json_value(row.get("opponent_augments"), [])),
            ),
        )

    augments = tuple(_parse_json_value(row.get("augments"), []))
    return GameState(
        stage=stage, player=player, board=board, augments=augments, opponents=opponents
    )


def _unit_from_dict(unit: Any, *, default_location: str) -> UnitState | None:
    if not isinstance(unit, dict):
        return None

    iid = unit.get("instance_id")
    if not isinstance(iid, str) or not iid:
        return None

    cid = unit.get("champion_id")
    if not isinstance(cid, str) or not cid:
        return None

    star = int(unit.get("star_level") or 1)
    location = unit.get("location") or default_location

    items = unit.get("items") or []
    if not isinstance(items, list):
        items = []

    pos = unit.get("position")
    position: tuple[int, int] | None = None
    if isinstance(pos, (list, tuple)) and len(pos) == 2:
        try:
            position = (int(pos[0]), int(pos[1]))
        except (ValueError, TypeError, IndexError):
            position = None

    return UnitState(
        instance_id=iid,
        champion_id=cid,
        star_level=star,
        items=tuple(str(x) for x in items),
        position=position,
        location=str(location),
    )


def _opponent_from_dict(opp: Any) -> OpponentState | None:
    if not isinstance(opp, dict):
        return None

    oid = opp.get("opponent_id") or "opp"
    if not isinstance(oid, str) or not oid:
        oid = "opp"

    board_in = _parse_json_value(opp.get("board"), [])
    board = tuple(
        u for u in (_unit_from_dict(x, default_location="board") for x in board_in) if u is not None
    )

    augments_in = _parse_json_value(opp.get("augments"), [])
    augments = tuple(str(x) for x in augments_in if isinstance(x, (str, int, float)))

    level = opp.get("level")
    if level is not None:
        level = int(level)
    hp = opp.get("hp")
    if hp is not None:
        hp = int(hp)

    return OpponentState(opponent_id=oid, board=board, augments=augments, level=level, hp=hp)


def coach_state_from_dict(data: dict) -> GameState:
    stage = data.get("stage") or "4-2"
    if not isinstance(stage, str) or not stage:
        stage = "4-2"

    p = data.get("player") or {}
    if not isinstance(p, dict):
        p = {}

    player = PlayerState(
        level=int(p.get("level") or 1),
        hp=int(p.get("hp") or 100),
        gold=int(p.get("gold") or 0),
        xp=int(p["xp"]) if p.get("xp") is not None else None,
        win_streak=int(p.get("win_streak") or 0),
        loss_streak=int(p.get("loss_streak") or 0),
    )

    board_in = _parse_json_value(data.get("board"), [])
    board = tuple(
        u for u in (_unit_from_dict(x, default_location="board") for x in board_in) if u is not None
    )
    bench_in = _parse_json_value(data.get("bench"), [])
    bench = tuple(
        u for u in (_unit_from_dict(x, default_location="bench") for x in bench_in) if u is not None
    )

    shop_units: list[ShopUnit] = []
    shop_in = _parse_json_value(data.get("shop"), [])
    if isinstance(shop_in, list):
        for su in shop_in:
            if not isinstance(su, dict):
                continue
            cid = su.get("champion_id")
            if not isinstance(cid, str) or not cid:
                continue
            cost = int(su.get("cost") or 0)
            shop_units.append(ShopUnit(champion_id=cid, cost=cost))

    items_in = _parse_json_value(data.get("items"), [])
    items = tuple(str(x) for x in items_in if isinstance(x, (str, int, float)))

    augments_in = _parse_json_value(data.get("augments"), [])
    augments = tuple(str(x) for x in augments_in if isinstance(x, (str, int, float)))

    traits_out: list[tuple[str, int]] = []
    traits_in = _parse_json_value(data.get("traits"), [])
    if isinstance(traits_in, list):
        for t in traits_in:
            if isinstance(t, dict):
                name = t.get("name")
                count = t.get("count")
            elif isinstance(t, (list, tuple)) and len(t) == 2:
                name = t[0]
                count = t[1]
            else:
                continue
            if not isinstance(name, str) or not name:
                continue
            traits_out.append((name, int(count or 0)))
    traits = tuple(traits_out)

    opponents_in = _parse_json_value(data.get("opponents"), [])
    opponents = tuple(o for o in (_opponent_from_dict(x) for x in opponents_in) if o is not None)

    notes_in = _parse_json_value(data.get("notes"), [])
    notes = tuple(str(x) for x in notes_in if isinstance(x, (str, int, float)))

    schema_version = int(data.get("schema_version") or 1)
    return GameState(
        stage=stage,
        player=player,
        board=board,
        bench=bench,
        shop=tuple(shop_units),
        items=items,
        augments=augments,
        traits=traits,
        opponents=opponents,
        notes=notes,
        schema_version=schema_version,
    )


def _iter_parquet_rows(paths: Iterable[Path]) -> Iterable[dict]:
    try:
        import pyarrow.parquet as pq
    except (ImportError, OSError) as e:
        raise RuntimeError(
            "pyarrow is required to read parquet inputs; install it or use --eval-set"
        ) from e

    for p in paths:
        table = pq.read_table(p)
        df = table.to_pandas()
        for row in df.to_dict(orient="records"):
            yield row


def _iter_eval_set_states(path: Path) -> Iterable[GameState]:
    if not path.exists():
        raise SystemExit(f"Not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            yield coach_state_from_dict(row)


def _compare_reports(
    *,
    baseline: dict,
    current: dict,
    max_regress_mean_win_prob_delta: float,
    max_regress_pct_positive_win_prob_delta: float,
    max_regress_mean_expected_hp_delta: float,
) -> list[str]:
    base_decisions = baseline.get("decisions") or {}
    cur_decisions = current.get("decisions") or {}
    if not isinstance(base_decisions, dict) or not isinstance(cur_decisions, dict):
        return ["report.decisions: missing/invalid in baseline or current report"]

    failures: list[str] = []
    for decision, cur_metrics in cur_decisions.items():
        if not isinstance(cur_metrics, dict):
            continue
        base_metrics = base_decisions.get(decision) or {}
        if not isinstance(base_metrics, dict):
            continue

        base_n = int(base_metrics.get("n") or 0)
        cur_n = int(cur_metrics.get("n") or 0)
        if base_n <= 0 or cur_n <= 0:
            continue

        for metric, tol in (
            ("mean_win_prob_delta", float(max_regress_mean_win_prob_delta)),
            ("pct_positive_win_prob_delta", float(max_regress_pct_positive_win_prob_delta)),
            ("mean_expected_hp_delta", float(max_regress_mean_expected_hp_delta)),
        ):
            if metric not in base_metrics or metric not in cur_metrics:
                continue

            try:
                base_v = float(base_metrics[metric])
                cur_v = float(cur_metrics[metric])
            except (ValueError, TypeError):
                failures.append(f"{decision}.{metric}: non-numeric baseline/current value")
                continue

            if cur_v < (base_v - tol):
                failures.append(
                    f"{decision}.{metric}: {cur_v:.4f} < {base_v - tol:.4f} (baseline={base_v:.4f} max_regress={tol:.4f})"
                )

    return failures


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline coach evaluation harness (sample decision-time snapshots)"
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-dir", type=Path, default=None, help="Results dir containing chunk_*.parquet"
    )
    input_group.add_argument(
        "--eval-set",
        type=Path,
        default=None,
        help="JSONL file with coach GameState dicts (from --write-eval-set)",
    )
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument(
        "--output", type=Path, default=Path("outputs/coach/eval_reports/coach_eval_report.json")
    )
    parser.add_argument(
        "--write-eval-set",
        type=Path,
        default=None,
        help="Optional JSONL path to save sampled CoachState inputs",
    )
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=None,
        help="Optional report JSON to compare against for regression gating",
    )
    parser.add_argument("--max-regress-mean-win-prob-delta", type=float, default=0.01)
    parser.add_argument("--max-regress-pct-positive-win-prob-delta", type=float, default=0.05)
    parser.add_argument("--max-regress-mean-expected-hp-delta", type=float, default=0.5)
    args = parser.parse_args()

    coach = Coach()

    states: list[GameState] = []
    if args.eval_set is not None:
        for s in _iter_eval_set_states(args.eval_set):
            states.append(s)
            if len(states) >= int(args.limit):
                break
    else:
        assert args.input_dir is not None
        parquet_paths = sorted(args.input_dir.glob("chunk_*.parquet"))
        if not parquet_paths:
            raise SystemExit(f"No chunk_*.parquet files found in {args.input_dir}")

        rows = []
        for r in _iter_parquet_rows(parquet_paths):
            rows.append(r)
            if len(rows) >= int(args.limit):
                break
        states = [coach_state_from_row(r) for r in rows]

    if not states:
        src = str(args.eval_set) if args.eval_set is not None else str(args.input_dir)
        raise SystemExit(f"No states loaded from {src}")

    if args.write_eval_set is not None:
        args.write_eval_set.parent.mkdir(parents=True, exist_ok=True)
        with args.write_eval_set.open("w", encoding="utf-8") as f:
            for s in states:
                f.write(json.dumps(asdict(s), separators=(",", ":")) + "\n")

    EVAL_COMBAT_BASE_SEED = 1337
    EVAL_TOP_K = 1
    EVAL_SIM_BUDGET_PASS1 = 32
    EVAL_SIM_BUDGET_PASS2 = 0
    EVAL_SIM_BUDGET_PASS3 = 0
    EVAL_TOPK_REFINE = 0
    EVAL_MAX_TOTAL_SIMS = 1024
    EVAL_SEED_STRIDE_PER_OPPONENT = 1000

    def _cfg_for(s: GameState) -> CoachConfig:
        return CoachConfig(
            weights=weights_for_stage(s.stage_number),
            combat_base_seed=EVAL_COMBAT_BASE_SEED,
            top_k=EVAL_TOP_K,
            sim_budget_pass1=EVAL_SIM_BUDGET_PASS1,
            sim_budget_pass2=EVAL_SIM_BUDGET_PASS2,
            sim_budget_pass3=EVAL_SIM_BUDGET_PASS3,
            topk_refine=EVAL_TOPK_REFINE,
            max_total_sims=EVAL_MAX_TOTAL_SIMS,
        )

    per_decision: dict[str, list[dict[str, float]]] = {d.value: [] for d in DecisionType}
    per_decision_proxy_skipped: dict[str, int] = {d.value: 0 for d in DecisionType}
    per_decision_no_recs: dict[str, int] = {d.value: 0 for d in DecisionType}
    for s in states:
        cfg = _cfg_for(s)
        for d in DecisionType:
            recs = coach.recommend(s, d, top_k=1, config=cfg)
            if not recs:
                per_decision_no_recs[d.value] += 1
                continue
            r = recs[0]
            if r.score.tempo.opponent_policy == "proxy_only":
                per_decision_proxy_skipped[d.value] += 1
                continue
            per_decision[d.value].append(
                {
                    "win_prob_delta": float(r.score.tempo.win_prob_delta),
                    "expected_hp_delta": float(r.score.tempo.expected_hp_delta),
                }
            )

    summary = {}
    for d, xs in per_decision.items():
        if not xs:
            summary[d] = {
                "n": 0,
                "proxy_only_skipped": int(per_decision_proxy_skipped[d]),
                "no_recs": int(per_decision_no_recs[d]),
            }
            continue
        deltas = [x["win_prob_delta"] for x in xs]
        hp = [x["expected_hp_delta"] for x in xs]
        summary[d] = {
            "n": len(xs),
            "proxy_only_skipped": int(per_decision_proxy_skipped[d]),
            "no_recs": int(per_decision_no_recs[d]),
            "mean_win_prob_delta": sum(deltas) / len(deltas),
            "pct_positive_win_prob_delta": sum(1 for x in deltas if x > 0) / len(deltas),
            "mean_expected_hp_delta": sum(hp) / len(hp),
        }

    report = {
        "input_dir": str(args.input_dir) if args.input_dir is not None else None,
        "eval_set": str(args.eval_set) if args.eval_set is not None else None,
        "limit": int(args.limit),
        "states_loaded": len(states),
        "run_config": {
            "combat_base_seed": EVAL_COMBAT_BASE_SEED,
            "top_k": EVAL_TOP_K,
            "sim_budget_pass1": EVAL_SIM_BUDGET_PASS1,
            "sim_budget_pass2": EVAL_SIM_BUDGET_PASS2,
            "sim_budget_pass3": EVAL_SIM_BUDGET_PASS3,
            "topk_refine": EVAL_TOPK_REFINE,
            "max_total_sims": EVAL_MAX_TOTAL_SIMS,
            # CombatScorer uses base_seed + opp_idx*stride + i for i in [0, num_seeds).
            "seed_stride_per_opponent": EVAL_SEED_STRIDE_PER_OPPONENT,
        },
        "decisions": summary,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"[OK] Wrote report -> {args.output}")

    if args.baseline_report is not None:
        baseline = json.loads(args.baseline_report.read_text(encoding="utf-8"))
        failures = _compare_reports(
            baseline=baseline,
            current=report,
            max_regress_mean_win_prob_delta=float(args.max_regress_mean_win_prob_delta),
            max_regress_pct_positive_win_prob_delta=float(
                args.max_regress_pct_positive_win_prob_delta
            ),
            max_regress_mean_expected_hp_delta=float(args.max_regress_mean_expected_hp_delta),
        )
        if failures:
            print("[GATE] FAIL")
            for f in failures[:25]:
                print(f"[GATE]  - {f}")
            raise SystemExit(2)
        print("[GATE] PASS")


if __name__ == "__main__":
    main()
