from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from coach.actions import (
    ActionPlan,
    EconDetails,
    HoldDetails,
    ItemEquipDetails,
    ItemSlamDetails,
    PositioningDetails,
    ShopBuyDetails,
)
from coach.scoring.features import champion_name


@dataclass(frozen=True, slots=True)
class Penalty:
    reason: str
    amount: float


@dataclass(frozen=True, slots=True)
class TempoBreakdown:
    win_prob: float
    win_prob_delta: float
    expected_hp_delta: float
    n_sims: int
    ci95: Optional[tuple[float, float]] = None
    opponent_policy: str = "proxy_only"  # "next_opponent" | "scouted_set" | "proxy_only"


@dataclass(frozen=True, slots=True)
class EvaluatorBreakdown:
    board_score: float
    matchup_score: Optional[float] = None
    uncertainty: Optional[float] = None


@dataclass(frozen=True, slots=True)
class EconBreakdown:
    gold_delta: int
    interest_delta: int
    level_delta: int
    roll_delta: int
    hp_risk: float
    upgrade_hit_prob: Optional[float] = None
    upgrade_top_targets: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True, slots=True)
class ArchetypeSummary:
    name: str
    similarity: float


@dataclass(frozen=True, slots=True)
class ArchetypeBreakdown:
    top_archetypes: tuple[ArchetypeSummary, ...]
    alignment_delta: float


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    total_score: float
    tempo: TempoBreakdown
    evaluator: EvaluatorBreakdown
    econ: EconBreakdown
    archetype: ArchetypeBreakdown
    penalties: tuple[Penalty, ...] = ()


@dataclass(frozen=True, slots=True)
class Explanation:
    confidence: str  # "high" | "medium" | "coin_flip" | "low"
    lines: tuple[str, ...]
    numbers: dict[str, float | int]


def confidence_bucket(score: ScoreBreakdown) -> str:
    if score.tempo.opponent_policy == "proxy_only" or score.tempo.n_sims <= 0:
        return "low"

    delta = abs(float(score.tempo.win_prob_delta))
    if score.tempo.n_sims < 64:
        return "low"
    if delta >= 0.10:
        return "high"
    if delta >= 0.05:
        return "medium"
    if delta >= 0.02:
        return "coin_flip"
    return "low"


def explain_action(action: ActionPlan, score: ScoreBreakdown) -> Explanation:
    lines: list[str] = []

    if isinstance(action.details, HoldDetails):
        if action.details.note:
            lines.append(action.details.note)
        return Explanation(confidence="low", lines=tuple(lines), numbers={})

    # Tempo lines
    if score.tempo.opponent_policy != "proxy_only":
        lines.append(f"Tempo (in sims): {score.tempo.win_prob*100:.1f}% ({score.tempo.win_prob_delta:+.1%})")
        lines.append(f"Expected HP delta: {score.tempo.expected_hp_delta:+.1f}")
    else:
        lines.append("Tempo: opponent unknown (proxy score only)")

    # Action-specific headline
    if isinstance(action.details, ItemSlamDetails):
        lines.insert(0, f"Slam {action.details.resulting_item} on {action.details.target_unit_id}")
    elif isinstance(action.details, ItemEquipDetails):
        lines.insert(0, f"Equip {action.details.item} on {action.details.target_unit_id}")
    elif isinstance(action.details, PositioningDetails):
        lines.insert(0, f"Positioning: {action.details.name}")
    elif isinstance(action.details, EconDetails):
        lines.insert(0, f"Econ: {action.details.name}")
    elif isinstance(action.details, ShopBuyDetails):
        lines.insert(0, f"Shop: {action.details.name}")

    # Econ summary
    if score.econ.gold_delta or score.econ.interest_delta or score.econ.level_delta or score.econ.roll_delta:
        lines.append(
            f"Econ delta: gold {score.econ.gold_delta:+d}, interest {score.econ.interest_delta:+d}, "
            f"level {score.econ.level_delta:+d}, rolls {score.econ.roll_delta:+d}"
        )
    if isinstance(action.details, EconDetails) and score.econ.upgrade_hit_prob is not None and action.details.rolls > 0:
        lines.append(f"Lookahead: {score.econ.upgrade_hit_prob*100:.0f}% to hit a 1-copy upgrade in ~{action.details.rolls} rolls")
        if score.econ.upgrade_top_targets:
            cid, p = score.econ.upgrade_top_targets[0]
            lines.append(f"Top hit: {champion_name(cid)} ({p*100:.0f}%)")

    # Archetype summary (top-1)
    if score.archetype.top_archetypes:
        best = score.archetype.top_archetypes[0]
        lines.append(f"Archetype: {best.name} ({best.similarity*100:.0f}%)")

    # Penalties
    for p in score.penalties[:3]:
        lines.append(f"Penalty: {p.reason} ({p.amount:+.2f})")

    confidence = confidence_bucket(score)
    numbers: dict[str, float | int] = {
        "win_prob_delta": float(score.tempo.win_prob_delta),
        "expected_hp_delta": float(score.tempo.expected_hp_delta),
        "gold_delta": int(score.econ.gold_delta),
        "interest_delta": int(score.econ.interest_delta),
    }

    return Explanation(confidence=confidence, lines=tuple(lines), numbers=numbers)


def validate_coach_payload(payload: dict) -> list[str]:
    errors: list[str] = []

    if not isinstance(payload.get("coach_payload_version"), int):
        errors.append("coach_payload_version: missing/not int")
    if not isinstance(payload.get("generated_at"), str):
        errors.append("generated_at: missing/not str")
    if "recommendations" not in payload or not isinstance(payload.get("recommendations"), dict):
        errors.append("recommendations: missing/not dict")
        return errors

    recs_by_decision = payload.get("recommendations") or {}
    for decision, recs in recs_by_decision.items():
        if not isinstance(recs, list):
            errors.append(f"recommendations.{decision}: not a list")
            continue
        for idx, r in enumerate(recs[:10]):
            if not isinstance(r, dict):
                errors.append(f"recommendations.{decision}[{idx}]: not dict")
                continue
            if not isinstance(r.get("action"), dict):
                errors.append(f"recommendations.{decision}[{idx}].action: missing/not dict")
            if not isinstance(r.get("score"), dict):
                errors.append(f"recommendations.{decision}[{idx}].score: missing/not dict")
            if not isinstance(r.get("explanation"), dict):
                errors.append(f"recommendations.{decision}[{idx}].explanation: missing/not dict")

    return errors
