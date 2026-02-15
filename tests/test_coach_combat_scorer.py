from __future__ import annotations

from coach.scoring.combat import CombatScorer
from coach.state import UnitState


def test_combat_scorer_is_deterministic_and_uses_cache() -> None:
    scorer = CombatScorer()

    my_units = (
        UnitState(
            instance_id="u0",
            champion_id="TFT16_Draven",
            star_level=2,
            items=(),
            position=(0, 6),
            location="board",
        ),
    )
    opp_units = (
        UnitState(
            instance_id="o0",
            champion_id="TFT16_Leona",
            star_level=2,
            items=(),
            position=(3, 3),
            location="board",
        ),
    )

    m1 = scorer.simulate_matchup(my_units, opp_units, round_num=18, num_seeds=6, base_seed=123)
    cache_len_1 = len(scorer._cache)
    m2 = scorer.simulate_matchup(my_units, opp_units, round_num=18, num_seeds=6, base_seed=123)
    cache_len_2 = len(scorer._cache)

    assert m1 == m2
    assert cache_len_2 == cache_len_1

