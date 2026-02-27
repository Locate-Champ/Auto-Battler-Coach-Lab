from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from coach.scoring.features import champion_name


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (ValueError, TypeError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def _fmt_float(value: Any, *, digits: int = 3) -> str:
    v = _as_float(value)
    if v is None or math.isnan(v) or math.isinf(v):
        return "--"
    return f"{v:.{int(digits)}f}"


def _fmt_signed(value: Any, *, digits: int = 3) -> str:
    v = _as_float(value)
    if v is None or math.isnan(v) or math.isinf(v):
        return "--"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{int(digits)}f}"


def _fmt_pct(value: Any, *, digits: int = 1) -> str:
    v = _as_float(value)
    if v is None or math.isnan(v) or math.isinf(v):
        return "--"
    return f"{v * 100.0:.{int(digits)}f}%"


def _fmt_signed_pct(value: Any, *, digits: int = 1) -> str:
    v = _as_float(value)
    if v is None or math.isnan(v) or math.isinf(v):
        return "--"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v * 100.0:.{int(digits)}f}%"


def _get(d: Any, *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _candidate_score_total(c: Any) -> float:
    score = _as_float(_get(c, "score", "total_score"))
    return score if score is not None else float("-inf")


def _unit_display_name(unit_id: Any, unit_map: dict[str, str]) -> str:
    if not isinstance(unit_id, str) or not unit_id:
        return "--"
    cid = unit_map.get(unit_id)
    if isinstance(cid, str) and cid:
        return champion_name(cid)
    return unit_id


def _candidate_title(action: Any, unit_map: dict[str, str]) -> str:
    if not isinstance(action, dict):
        return "--"

    details = action.get("details") or {}
    if isinstance(details, dict) and "target_unit_id" in details:
        target = _unit_display_name(details.get("target_unit_id"), unit_map)
        if "item" in details and details.get("item"):
            return f"Equip {details.get('item')} on {target}"
        if "resulting_item" in details and details.get("resulting_item"):
            return f"Slam {details.get('resulting_item')} on {target}"

    if isinstance(details, dict) and "champion_id" in details and details.get("champion_id"):
        cid = details.get("champion_id")
        cost = _as_int(details.get("cost"))
        cost_str = f" ({cost}g)" if cost is not None else ""
        return f"Buy {champion_name(str(cid))}{cost_str}"

    if (
        isinstance(details, dict)
        and "assignments" in details
        and isinstance(details.get("assignments"), (list, tuple))
    ):
        name = details.get("name") or action.get("title") or "Positioning"
        assignments = details.get("assignments") or ()
        shown: list[str] = []
        for a in list(assignments)[:3]:
            if isinstance(a, (list, tuple)) and len(a) == 3:
                uid = a[0]
                row = _as_int(a[1])
                col = _as_int(a[2])
                unit = _unit_display_name(uid, unit_map)
                if row is not None and col is not None:
                    shown.append(f"{unit}@({row},{col})")
                else:
                    shown.append(unit)
        if shown:
            suffix = ", ".join(shown)
            extra = len(assignments) - len(shown)
            if extra > 0:
                suffix = f"{suffix}, +{extra} more"
            return f"{name}: {suffix}"

    title = action.get("title")
    return str(title) if title is not None else "--"


def _iter_traces(path: Path) -> Any:
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
            yield row


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a readable view of coach DecisionTrace JSONL"
    )
    parser.add_argument("--input", type=Path, required=True, help="Path to coach_traces_*.jsonl")
    parser.add_argument("--limit", type=int, default=5, help="Number of traces to print")
    parser.add_argument("--top", type=int, default=5, help="Top candidates per trace")
    parser.add_argument(
        "--decision", type=str, default=None, help="Optional filter: items|position|econ|shop"
    )
    parser.add_argument(
        "--state", type=str, default=None, help="Optional filter: state_hash (prefix ok)"
    )
    parser.add_argument(
        "--chosen-only",
        action="store_true",
        help="Only print the chosen candidate breakdown (no top table)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Not found: {args.input}")

    printed = 0
    for t in _iter_traces(args.input):
        decision_type = str(t.get("decision_type") or "")
        state_hash = str(t.get("state_hash") or "")

        state_summary = t.get("state_summary") or {}
        if not isinstance(state_summary, dict):
            state_summary = {}
        unit_map = state_summary.get("unit_id_to_champion_id") or {}
        if not isinstance(unit_map, dict):
            unit_map = {}

        if args.decision and decision_type != str(args.decision):
            continue
        if args.state and not state_hash.startswith(str(args.state)):
            continue

        print("=" * 100)
        stage = state_summary.get("stage")
        level = _as_int(state_summary.get("level"))
        gold = _as_int(state_summary.get("gold"))
        if stage or level is not None or gold is not None:
            stage_s = str(stage) if stage is not None else "--"
            level_s = str(level) if level is not None else "--"
            gold_s = str(gold) if gold is not None else "--"
            print(
                f"DecisionTrace decision={decision_type} stage={stage_s} level={level_s} gold={gold_s} state={state_hash} at={t.get('generated_at')}"
            )
        else:
            print(
                f"DecisionTrace decision={decision_type} state={state_hash} at={t.get('generated_at')}"
            )

        base_seed = _as_int(t.get("combat_base_seed"))
        budgets = t.get("budgets") or []
        if not isinstance(budgets, list):
            budgets = []
        budgets_int = [int(x) for x in budgets if _as_int(x) is not None]

        baseline_total = _as_float(t.get("baseline_total_score")) or 0.0
        chosen_action_id = str(t.get("chosen_action_id") or "")

        seed_str = f"{base_seed}" if base_seed is not None else "--"
        print(
            f"seed_base={seed_str} budgets={budgets_int} baseline_total={baseline_total:.3f} chosen={chosen_action_id}"
        )
        if base_seed is not None and budgets_int:
            b = budgets_int[0]
            hi = base_seed + max(0, int(b) - 1)
            print(
                f"seed_spec(pass1): per-opponent range = base+opp_idx*1000 .. base+opp_idx*1000+{b - 1} ({base_seed}..{hi})"
            )

        candidates = t.get("candidates") or []
        if not isinstance(candidates, list) or not candidates:
            print("(no candidates in trace)")
            printed += 1
            if printed >= int(args.limit):
                break
            continue

        ranked = sorted(
            ((c, _candidate_score_total(c)) for c in candidates), key=lambda x: x[1], reverse=True
        )
        chosen = next(
            (
                c
                for c, _ in ranked
                if str(_get(c, "action", "action_id", default="")) == chosen_action_id
            ),
            None,
        )
        if chosen is None:
            chosen = ranked[0][0] if ranked else None

        if chosen is not None:
            a = _get(chosen, "action", default={}) or {}
            s = _get(chosen, "score", default={}) or {}
            tempo = _get(s, "tempo", default={}) or {}
            econ = _get(s, "econ", default={}) or {}
            archetype = _get(s, "archetype", default={}) or {}
            evaluator = _get(s, "evaluator", default={}) or {}
            penalties = _get(s, "penalties", default=[]) or []

            chosen_total = _as_float(_get(s, "total_score")) or float("-inf")
            total_delta = chosen_total - float(baseline_total)
            print("chosen:")
            print(f"  id={a.get('action_id')} title={_candidate_title(a, unit_map)}")
            print(f"  total={chosen_total:.3f} (delta_vs_hold={total_delta:+.3f})")
            print(
                "  tempo: win="
                + _fmt_pct(tempo.get("win_prob"))
                + " (delta="
                + _fmt_signed_pct(tempo.get("win_prob_delta"))
                + "), ehp="
                + _fmt_signed(tempo.get("expected_hp_delta"), digits=2)
                + ", sims="
                + str(_as_int(tempo.get("n_sims")) or 0)
                + ", policy="
                + str(tempo.get("opponent_policy") or "--")
            )
            if tempo.get("ci95"):
                ci = tempo.get("ci95")
                if isinstance(ci, list) and len(ci) == 2:
                    print(f"  tempo_ci95: [{_fmt_pct(ci[0])}, {_fmt_pct(ci[1])}]")
            print(f"  evaluator: board_score={_fmt_float(evaluator.get('board_score'))}")
            print(
                "  econ: gold="
                + str(_as_int(econ.get("gold_delta")) or 0)
                + ", interest="
                + str(_as_int(econ.get("interest_delta")) or 0)
                + ", level="
                + str(_as_int(econ.get("level_delta")) or 0)
                + ", rolls="
                + str(_as_int(econ.get("roll_delta")) or 0)
                + ", hp_risk="
                + _fmt_float(econ.get("hp_risk"), digits=2)
            )
            if econ.get("upgrade_hit_prob") is not None:
                print(
                    f"  lookahead: upgrade_hit_prob={_fmt_pct(econ.get('upgrade_hit_prob'), digits=0)}"
                )
            upgrade_targets = econ.get("upgrade_top_targets")
            if isinstance(upgrade_targets, list) and upgrade_targets:
                top = upgrade_targets[0]
                if isinstance(top, list) and len(top) == 2:
                    cid = top[0]
                    name = champion_name(str(cid)) if cid is not None else "--"
                    print(f"  lookahead_top: {name} ({_fmt_pct(top[1], digits=0)})")

            best_arch = None
            top_arches = archetype.get("top_archetypes")
            if isinstance(top_arches, list) and top_arches:
                best_arch = top_arches[0]
            if isinstance(best_arch, dict):
                name = best_arch.get("name")
                sim = best_arch.get("similarity")
                print(
                    "  archetype: best="
                    + str(name or "--")
                    + " (sim="
                    + _fmt_pct(sim, digits=0)
                    + "), align_delta="
                    + _fmt_signed(archetype.get("alignment_delta"), digits=3)
                )

            if isinstance(penalties, list) and penalties:
                reasons = []
                for p in penalties[:3]:
                    if not isinstance(p, dict):
                        continue
                    reasons.append(f"{p.get('reason')}({_fmt_signed(p.get('amount'), digits=2)})")
                if reasons:
                    print("  penalties: " + ", ".join(reasons))

            tags = a.get("tags") or []
            if isinstance(tags, list) and tags:
                print("  tags: " + ", ".join(str(x) for x in tags[:8]))

            constraints = a.get("constraints") or []
            if isinstance(constraints, list) and constraints:
                print("  constraints: " + ", ".join(str(x) for x in constraints[:8]))

        if not args.chosen_only:
            print("top candidates:")
            for idx, (c, score_total) in enumerate(ranked[: max(0, int(args.top))], start=1):
                a = _get(c, "action", default={}) or {}
                s = _get(c, "score", default={}) or {}
                tempo = _get(s, "tempo", default={}) or {}
                econ = _get(s, "econ", default={}) or {}

                aid = str(a.get("action_id") or "")
                marker = "*" if aid == chosen_action_id else " "
                win_d = _fmt_signed_pct(tempo.get("win_prob_delta"))
                ehp = _fmt_signed(tempo.get("expected_hp_delta"), digits=1)
                gold = _as_int(econ.get("gold_delta")) or 0
                rolls = _as_int(econ.get("roll_delta")) or 0
                print(
                    f"  {idx:2d}. {marker} {aid} :: {_candidate_title(a, unit_map)} :: total={score_total:.3f} tempo_d={win_d} ehp={ehp} gold={gold:+d} rolls={rolls:+d}"
                )

        printed += 1
        if printed >= int(args.limit):
            break


if __name__ == "__main__":
    main()
