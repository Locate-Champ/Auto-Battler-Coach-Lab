from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    tempo: float
    evaluator: float
    econ: float
    archetype: float
    lookahead: float = 0.0


@dataclass(frozen=True, slots=True)
class CoachConfig:
    weights: ScoreWeights

    combat_base_seed: int = 1337

    # Hard caps to keep branching factor bounded (per decision type).
    max_candidates_items: int = 80
    max_candidates_position: int = 60
    max_candidates_econ: int = 40
    max_candidates_shop: int = 40

    top_k: int = 3

    # Adaptive sim budgets (coarse -> refine).
    sim_budget_pass1: int = 96
    sim_budget_pass2: int = 256
    sim_budget_pass3: int = 512
    topk_refine: int = 8
    tie_threshold: float = 0.02
    max_total_sims: int = 4096


def weights_for_stage(stage_number: int) -> ScoreWeights:
    # Stage-aware tuning: early game values econ/interest more; late game values tempo more.
    if stage_number <= 2:
        return ScoreWeights(tempo=0.45, evaluator=0.20, econ=0.25, archetype=0.10, lookahead=0.08)
    if stage_number == 3:
        return ScoreWeights(tempo=0.50, evaluator=0.20, econ=0.20, archetype=0.10, lookahead=0.08)
    if stage_number == 4:
        return ScoreWeights(tempo=0.55, evaluator=0.25, econ=0.10, archetype=0.10, lookahead=0.06)
    return ScoreWeights(tempo=0.60, evaluator=0.25, econ=0.05, archetype=0.10, lookahead=0.04)


def default_config_for_stage(stage_number: int) -> CoachConfig:
    # Keep latency low early game; allocate more sims later when fights matter more.
    if stage_number <= 2:
        return CoachConfig(
            weights=weights_for_stage(stage_number),
            sim_budget_pass1=64,
            sim_budget_pass2=128,
            sim_budget_pass3=256,
            topk_refine=6,
            max_total_sims=1536,
        )
    if stage_number == 3:
        return CoachConfig(
            weights=weights_for_stage(stage_number),
            sim_budget_pass1=96,
            sim_budget_pass2=256,
            sim_budget_pass3=512,
            topk_refine=8,
            max_total_sims=3072,
        )
    return CoachConfig(weights=weights_for_stage(stage_number))
