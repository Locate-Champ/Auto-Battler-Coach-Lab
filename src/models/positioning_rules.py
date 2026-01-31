"""Baseline positioning heuristics and placeholders for special tech."""

from __future__ import annotations

from typing import Dict, List

BASELINE_RULES: List[str] = [
    "Frontline tanks/defenders in the first two rows; ranged carries in the backline.",
    "Melee carries generally belong in the second row behind primary tanks.",
    "Use high-armor/MR and defensive-ability units as your frontline anchors.",
    "Place strongest tanks on the outside to intercept corner-focused threats.",
    "Keep the strongest tank near your primary carry for protection.",
    "Early game: modest clumping can focus-fire targets faster.",
    "Late game: spread to reduce AoE/CC vulnerability.",
    "Scout opponents and counter-position to minimize their primary threats.",
    "Protect against hook effects by avoiding isolated backline carries.",
]

SINGED_POSITIONING_STATUS: Dict[str, str] = {
    "status": "pending_transcript_review",
    "reason": "Awaiting verified transcript or clip breakdown for Singed positioning tech.",
}


def get_baseline_rules() -> List[str]:
    return list(BASELINE_RULES)


def get_singed_positioning_status() -> Dict[str, str]:
    return dict(SINGED_POSITIONING_STATUS)
