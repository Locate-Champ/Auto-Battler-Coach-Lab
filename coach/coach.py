from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from coach.actions import (
    ActionPlan,
    DecisionType,
    EconDetails,
    HoldDetails,
)
from coach.encoding import encode_state_set_based
from coach.explain import (
    ArchetypeBreakdown,
    ArchetypeSummary,
    EconBreakdown,
    EvaluatorBreakdown,
    Explanation,
    Penalty,
    ScoreBreakdown,
    TempoBreakdown,
)
from coach.modules.econ.candidates import generate_candidates as econ_candidates
from coach.modules.econ.execute import execute as econ_execute
from coach.modules.items.candidates import generate_candidates as item_candidates
from coach.modules.items.execute import execute as item_execute
from coach.modules.items import explain as item_explain
from coach.modules.position.candidates import generate_candidates as position_candidates
from coach.modules.position.execute import execute as position_execute
from coach.modules.position import explain as position_explain
from coach.modules.shop.candidates import generate_candidates as shop_candidates
from coach.modules.shop.execute import execute as shop_execute
from coach.modules.shop import explain as shop_explain
from coach.modules.econ import explain as econ_explain
from coach.odds import estimate_upgrade_hit_prob
from coach.scoring.archetypes import ArchetypeLibrary
from coach.scoring.combat import CombatEstimate, CombatScorer
from coach.scoring.evaluator import BoardEvaluator, default_evaluator
from coach.scoring.features import plan_value_score, with_derived_traits
from coach.state import GameState
from coach.weights import CoachConfig, default_config_for_stage


@dataclass(frozen=True, slots=True)
class Recommendation:
    action: ActionPlan
    score: ScoreBreakdown
    explanation: Explanation


@dataclass(frozen=True, slots=True)
class DecisionTraceCandidate:
    action: ActionPlan
    score: ScoreBreakdown


@dataclass(frozen=True, slots=True)
class DecisionTraceStateSummary:
    stage: str
    level: int
    gold: int
    unit_id_to_champion_id: dict[str, str]


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    generated_at: str
    state_hash: str
    decision_type: str
    state_summary: DecisionTraceStateSummary
    baseline_total_score: float
    candidates: tuple[DecisionTraceCandidate, ...]
    chosen_action_id: str
    combat_base_seed: int
    budgets: tuple[int, ...]


def _round_num_from_stage(stage: str) -> int:
    try:
        stage_num = int(stage.split("-")[0])
        round_in_stage = int(stage.split("-")[1])
    except Exception:
        return 4

    if stage_num <= 1:
        return max(0, round_in_stage - 1)

    # Mapping aligned with simulator/game/game.py round tagging:
    # 2-1 -> 4, 3-1 -> 10, 4-1 -> 17, 5-1 -> 24, 6-1 -> 31 ...
    base = 4 + (stage_num - 2) * 7 + (round_in_stage - 1)
    if stage_num >= 3:
        base -= 1
    return max(0, int(base))


def _hash_state(state: GameState) -> str:
    encoded = encode_state_set_based(state, include_position=True)
    payload = asdict(encoded)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(text).hexdigest()[:12]


def _write_trace(trace: DecisionTrace, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = out_dir / f"coach_traces_{day}.jsonl"

    def _to_jsonable(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return obj

    row = json.dumps(_to_jsonable(trace), separators=(",", ":"), default=_to_jsonable)
    with path.open("a", encoding="utf-8") as f:
        f.write(row + "\n")


class Coach:
    def __init__(
        self,
        *,
        combat_scorer: Optional[CombatScorer] = None,
        evaluator: Optional[BoardEvaluator] = None,
        archetypes: Optional[ArchetypeLibrary] = None,
        trace_dir: Optional[Path] = None,
    ):
        self.combat_scorer = combat_scorer or CombatScorer()
        self.evaluator = evaluator or default_evaluator()
        self.archetypes = archetypes or ArchetypeLibrary()
        self._trace_dir = trace_dir

    def _candidates_executor_explainer(self, decision: DecisionType) -> tuple[Callable, Callable, Callable]:
        if decision == DecisionType.ITEMS:
            return item_candidates, item_execute, item_explain
        if decision == DecisionType.POSITION:
            return position_candidates, position_execute, position_explain
        if decision == DecisionType.ECON:
            return econ_candidates, econ_execute, econ_explain
        return shop_candidates, shop_execute, shop_explain

    def _max_candidates_for_decision(self, cfg: CoachConfig, decision: DecisionType) -> int:
        if decision == DecisionType.ITEMS:
            return int(cfg.max_candidates_items)
        if decision == DecisionType.POSITION:
            return int(cfg.max_candidates_position)
        if decision == DecisionType.ECON:
            return int(cfg.max_candidates_econ)
        return int(cfg.max_candidates_shop)

    def _tempo_for_state(
        self,
        state: GameState,
        *,
        round_num: int,
        num_seeds: int,
        base_seed: int,
    ) -> Optional[CombatEstimate]:
        return self.combat_scorer.tempo_for_state(
            state,
            round_num=int(round_num),
            num_seeds=int(num_seeds),
            base_seed=int(base_seed),
        )

    def _score(
        self,
        *,
        baseline: GameState,
        baseline_tempo: Optional[CombatEstimate],
        baseline_best_arch: Optional[ArchetypeSummary],
        candidate: GameState,
        action: ActionPlan,
        cfg: CoachConfig,
        num_seeds: int,
        did_change: bool,
        simulate_tempo: bool,
    ) -> ScoreBreakdown:
        candidate = with_derived_traits(candidate)

        tempo_metrics: Optional[CombatEstimate] = None
        if simulate_tempo:
            round_num = _round_num_from_stage(candidate.stage)
            tempo_metrics = self._tempo_for_state(
                candidate,
                round_num=round_num,
                num_seeds=num_seeds,
                base_seed=cfg.combat_base_seed,
            )

        baseline_win_prob = baseline_tempo.win_prob if baseline_tempo is not None else None

        if tempo_metrics is not None:
            tempo_win_prob = float(tempo_metrics.win_prob)
            tempo_win_prob_delta = tempo_win_prob - float(baseline_win_prob or 0.0)
            expected_hp_delta = float(tempo_metrics.expected_hp_delta)
            tempo = TempoBreakdown(
                win_prob=tempo_win_prob,
                win_prob_delta=tempo_win_prob_delta,
                expected_hp_delta=expected_hp_delta,
                n_sims=int(tempo_metrics.n_sims),
                ci95=tempo_metrics.ci95,
                opponent_policy=str(tempo_metrics.opponent_policy),
            )
            tempo_value = tempo_win_prob
        else:
            # Proxy-only: use evaluator as a tempo proxy when opponent boards aren't known.
            tempo_value = float(self.evaluator.score(candidate))
            tempo = TempoBreakdown(
                win_prob=tempo_value,
                win_prob_delta=0.0,
                expected_hp_delta=0.0,
                n_sims=0,
                ci95=None,
                opponent_policy="proxy_only",
            )

        eval_value = float(self.evaluator.score(candidate))
        evaluator = EvaluatorBreakdown(board_score=eval_value)

        arch_matches = self.archetypes.closest(candidate, top_n=3)
        top_arch = tuple(ArchetypeSummary(name=m.archetype.name, similarity=float(m.similarity)) for m in arch_matches)
        cand_best = top_arch[0] if top_arch else None
        baseline_sim = float(baseline_best_arch.similarity) if baseline_best_arch is not None else 0.0
        cand_sim = float(cand_best.similarity) if cand_best is not None else 0.0
        archetype = ArchetypeBreakdown(top_archetypes=top_arch, alignment_delta=cand_sim - baseline_sim)

        lookahead_value = 0.0
        lookahead_targets: tuple[tuple[str, float], ...] = ()
        if isinstance(action.details, EconDetails) and int(action.details.rolls or 0) > 0:
            seed = int(cfg.combat_base_seed) + 10007 + baseline.stage_number * 100 + baseline.round_number
            prob_any, per_target, _ = estimate_upgrade_hit_prob(
                baseline,
                level=candidate.player.level,
                rolls=int(action.details.rolls),
                seed=seed,
                num_trials=60,
            )
            lookahead_value = float(prob_any)
            lookahead_targets = tuple(sorted(per_target.items(), key=lambda kv: kv[1], reverse=True)[:3])

        econ_value = float(plan_value_score(candidate))
        gold_delta = int(candidate.player.gold) - int(baseline.player.gold)
        interest_delta = int(candidate.player.interest) - int(baseline.player.interest)
        level_delta = int(candidate.player.level) - int(baseline.player.level)
        roll_delta = int(action.details.rolls) if isinstance(action.details, EconDetails) else 0
        hp_risk = min(max(1.0 - float(tempo_value), 0.0), 1.0)
        econ = EconBreakdown(
            gold_delta=gold_delta,
            interest_delta=interest_delta,
            level_delta=level_delta,
            roll_delta=roll_delta,
            hp_risk=hp_risk,
            upgrade_hit_prob=lookahead_value if lookahead_value > 0 else None,
            upgrade_top_targets=lookahead_targets,
        )

        penalties: list[Penalty] = []
        if not did_change and not isinstance(action.details, HoldDetails):
            penalties.append(Penalty(reason="illegal_or_no_effect", amount=0.25))

        w = cfg.weights
        terms_total = (
            float(w.tempo) * float(tempo_value)
            + float(w.evaluator) * float(eval_value)
            + float(w.econ) * float(econ_value)
            + float(w.archetype) * float(cand_sim)
            + float(w.lookahead) * float(lookahead_value)
        )
        total_score = terms_total - sum(p.amount for p in penalties)

        return ScoreBreakdown(
            total_score=float(total_score),
            tempo=tempo,
            evaluator=evaluator,
            econ=econ,
            archetype=archetype,
            penalties=tuple(penalties),
        )

    def recommend(
        self,
        state: GameState,
        decision: DecisionType,
        *,
        top_k: Optional[int] = None,
        config: Optional[CoachConfig] = None,
        write_trace: bool = False,
    ) -> list[Recommendation]:
        baseline = with_derived_traits(state)
        cfg = config or default_config_for_stage(baseline.stage_number)
        k = int(top_k) if top_k is not None else int(cfg.top_k)

        gen, execute, explain = self._candidates_executor_explainer(decision)
        candidates = list(gen(baseline))

        # Ensure hold is always present and keep branching factor bounded.
        hold = next((a for a in candidates if isinstance(a.details, HoldDetails)), None)
        others = [a for a in candidates if not isinstance(a.details, HoldDetails)]
        if hold is None:
            hold = ActionPlan(
                decision_type=decision,
                action_id=f"{decision.value}:hold",
                title="Hold",
                details=HoldDetails(note="Hold"),
            )

        max_candidates = self._max_candidates_for_decision(cfg, decision)
        capped: list[ActionPlan] = [hold] + others[: max(0, int(max_candidates) - 1)]

        baseline_round_num = _round_num_from_stage(baseline.stage)
        budgets: list[int] = [int(cfg.sim_budget_pass1), int(cfg.sim_budget_pass2), int(cfg.sim_budget_pass3)]
        budgets = [b for b in budgets if b > 0]
        pass1 = budgets[0] if budgets else 0

        baseline_tempo_by_budget: dict[int, Optional[CombatEstimate]] = {}
        if pass1 > 0:
            baseline_tempo_by_budget[pass1] = self._tempo_for_state(
                baseline,
                round_num=baseline_round_num,
                num_seeds=pass1,
                base_seed=cfg.combat_base_seed,
            )

        baseline_arch_matches = self.archetypes.closest(baseline, top_n=1)
        baseline_best_arch = (
            ArchetypeSummary(name=baseline_arch_matches[0].archetype.name, similarity=float(baseline_arch_matches[0].similarity))
            if baseline_arch_matches
            else None
        )

        # Execute once per candidate to avoid re-running deterministic executors.
        next_state_by_action_id: dict[str, GameState] = {}
        for action in capped:
            next_state_by_action_id[action.action_id] = execute(baseline, action)

        # Pass 1: sim only a pruned set (fast evaluator pre-rank), score the rest via proxy.
        sim_top = max(int(cfg.topk_refine), int(k)) * 3
        eval_rank: list[tuple[float, ActionPlan]] = []
        for action in capped:
            if action.action_id == hold.action_id:
                continue
            s = next_state_by_action_id[action.action_id]
            eval_rank.append((float(self.evaluator.score(with_derived_traits(s))), action))
        eval_rank.sort(key=lambda x: x[0], reverse=True)
        sim_action_ids = {hold.action_id}
        sim_action_ids.update(a.action_id for _, a in eval_rank[: max(0, int(sim_top))])

        scored: list[tuple[ActionPlan, ScoreBreakdown]] = []
        for action in capped:
            next_state = next_state_by_action_id[action.action_id]
            breakdown = self._score(
                baseline=baseline,
                baseline_tempo=baseline_tempo_by_budget.get(pass1),
                baseline_best_arch=baseline_best_arch,
                candidate=next_state,
                action=action,
                cfg=cfg,
                num_seeds=pass1,
                did_change=(next_state != baseline),
                simulate_tempo=(action.action_id in sim_action_ids),
            )
            scored.append((action, breakdown))

        scored.sort(key=lambda x: x[1].total_score, reverse=True)

        # Pass 2/3 refinement for top candidates.
        total_sims_used = pass1 * max(0, len(capped))
        if len(budgets) >= 2:
            pass2 = budgets[1]
            if pass2 > pass1 and total_sims_used < int(cfg.max_total_sims):
                baseline_tempo_by_budget[pass2] = self._tempo_for_state(
                    baseline,
                    round_num=baseline_round_num,
                    num_seeds=pass2,
                    base_seed=cfg.combat_base_seed,
                )
                refine_n = min(int(cfg.topk_refine), len(scored))
                for i in range(refine_n):
                    action, _ = scored[i]
                    next_state = next_state_by_action_id[action.action_id]
                    breakdown = self._score(
                        baseline=baseline,
                        baseline_tempo=baseline_tempo_by_budget.get(pass2),
                        baseline_best_arch=baseline_best_arch,
                        candidate=next_state,
                        action=action,
                        cfg=cfg,
                        num_seeds=pass2,
                        did_change=(next_state != baseline),
                        simulate_tempo=True,
                    )
                    scored[i] = (action, breakdown)
                    total_sims_used += pass2
                scored.sort(key=lambda x: x[1].total_score, reverse=True)

        if len(budgets) >= 3 and len(scored) >= 2:
            pass3 = budgets[2]
            top_gap = float(scored[0][1].total_score) - float(scored[1][1].total_score)
            if pass3 > budgets[1] and abs(top_gap) <= float(cfg.tie_threshold) and total_sims_used < int(cfg.max_total_sims):
                baseline_tempo_by_budget[pass3] = self._tempo_for_state(
                    baseline,
                    round_num=baseline_round_num,
                    num_seeds=pass3,
                    base_seed=cfg.combat_base_seed,
                )
                for i in range(2):
                    action, _ = scored[i]
                    next_state = next_state_by_action_id[action.action_id]
                    breakdown = self._score(
                        baseline=baseline,
                        baseline_tempo=baseline_tempo_by_budget.get(pass3),
                        baseline_best_arch=baseline_best_arch,
                        candidate=next_state,
                        action=action,
                        cfg=cfg,
                        num_seeds=pass3,
                        did_change=(next_state != baseline),
                        simulate_tempo=True,
                    )
                    scored[i] = (action, breakdown)
                    total_sims_used += pass3
                scored.sort(key=lambda x: x[1].total_score, reverse=True)

        recs: list[Recommendation] = []
        for action, breakdown in scored[: max(1, k)]:
            explanation = explain(baseline, action, breakdown)
            recs.append(Recommendation(action=action, score=breakdown, explanation=explanation))

        if write_trace and self._trace_dir is not None:
            state_hash = _hash_state(baseline)
            hold_breakdown = next((b for a, b in scored if a.action_id == hold.action_id), None)
            baseline_total = float(hold_breakdown.total_score) if hold_breakdown is not None else 0.0
            unit_map = {u.instance_id: u.champion_id for u in (*baseline.board, *baseline.bench)}
            summary = DecisionTraceStateSummary(
                stage=str(baseline.stage),
                level=int(baseline.player.level),
                gold=int(baseline.player.gold),
                unit_id_to_champion_id=dict(sorted(unit_map.items(), key=lambda kv: kv[0])),
            )
            trace = DecisionTrace(
                generated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                state_hash=state_hash,
                decision_type=decision.value,
                state_summary=summary,
                baseline_total_score=baseline_total,
                candidates=tuple(DecisionTraceCandidate(action=a, score=s) for a, s in scored),
                chosen_action_id=recs[0].action.action_id if recs else "",
                combat_base_seed=int(cfg.combat_base_seed),
                budgets=tuple(budgets),
            )
            _write_trace(trace, self._trace_dir)

        return recs

    def recommend_all(
        self,
        state: GameState,
        *,
        top_k: int = 3,
        config: Optional[CoachConfig] = None,
        write_trace: bool = False,
    ) -> dict[str, list[Recommendation]]:
        return {
            DecisionType.ITEMS.value: self.recommend(state, DecisionType.ITEMS, top_k=top_k, config=config, write_trace=write_trace),
            DecisionType.POSITION.value: self.recommend(
                state, DecisionType.POSITION, top_k=top_k, config=config, write_trace=write_trace
            ),
            DecisionType.ECON.value: self.recommend(state, DecisionType.ECON, top_k=top_k, config=config, write_trace=write_trace),
            DecisionType.SHOP.value: self.recommend(state, DecisionType.SHOP, top_k=top_k, config=config, write_trace=write_trace),
        }
