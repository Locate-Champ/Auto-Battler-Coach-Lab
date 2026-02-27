"""Numeric constants for TFT feature engineering.

Each field on :class:`NumericFeatureConfig` replaces a domain-meaningful magic
number formerly inlined in :mod:`models.feature_engineering`.  Default values
match the original inline constants.

Use ``dataclasses.replace(DEFAULT_CONFIG, field=new_value)`` to create
modified copies for testing without mutating the shared default.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumericFeatureConfig:
    """Frozen numeric constants consumed by :class:`TFTFeatureEngineer`.

    Frozen to prevent runtime mutation of shared defaults.
    Use :func:`dataclasses.replace` to create modified copies for testing.
    """

    # --- Item classification thresholds ---
    attack_speed_weight: float = 50.0  # Weight for AS in offensive signal calculation
    hp_divisor: float = 100.0  # Divisor to normalize HP to a 0-1 scale
    armor_divisor: float = 20.0  # Divisor to normalize armor contribution
    mr_divisor: float = 20.0  # Divisor to normalize magic resist contribution
    classification_threshold: float = 0.2  # Minimum signal gap to classify offensive vs defensive

    # --- Economy ---
    interest_gold_divisor: float = 10.0  # Gold per interest bracket (TFT rule: 1 gold per 10 saved)
    max_interest: float = 5.0  # Maximum interest gold per round (TFT cap at 50 gold)

    # --- Scoring ---
    default_avg_placement: float = 4.5  # Neutral average placement (midpoint of 1-8 player lobby)
    personal_score_placement_divisor: float = 8.0  # Normalizes placement delta to ~0-1 range
    carry_item_score_weight: float = 0.01  # Small bonus for carry item count in personal scoring

    # --- Composition ---
    trait_ap_proxy_per_trait: float = 5.0  # Estimated AP contribution per active trait
    bis_item_threshold: float = 3.0  # Items needed on carry to count as best-in-slot equipped

    # --- Matchup ---
    stage_hp_pressure_multiplier: float = 10.0  # HP pressure scaling factor per stage number
    share_to_percent_multiplier: float = 100.0  # Converts 0-1 share ratio to 0-100 percentage scale

    # --- Team summary ---
    dps_weight_in_physical_proxy: float = 0.01  # Small DPS contribution to physical damage share
    attack_speed_pct_threshold: float = 1.0  # AS values above this are percentage-based (Riot data)


DEFAULT_CONFIG = NumericFeatureConfig()
