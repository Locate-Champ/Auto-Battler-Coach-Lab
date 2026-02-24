from __future__ import annotations

from coach.actions import PositioningDetails
from coach.modules.position.candidates import generate_candidates
from coach.rules import is_valid_board_pos
from coach.state import GameState, PlayerState, UnitState


def _state_for_positioning() -> GameState:
    player = PlayerState(level=6, hp=78, gold=22, win_streak=0, loss_streak=0)
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
        UnitState(
            instance_id="u2",
            champion_id="TFT16_Ekko",
            star_level=1,
            items=(),
            position=(2, 2),
            location="board",
        ),
        UnitState(
            instance_id="u3",
            champion_id="TFT16_TwistedFate",
            star_level=1,
            items=(),
            position=(1, 3),
            location="board",
        ),
        UnitState(
            instance_id="u4",
            champion_id="TFT16_Vayne",
            star_level=1,
            items=(),
            position=(0, 3),
            location="board",
        ),
        UnitState(
            instance_id="u5",
            champion_id="TFT16_Sion",
            star_level=1,
            items=(),
            position=(3, 2),
            location="board",
        ),
    )
    return GameState(stage="3-2", player=player, board=board)


def test_position_candidates_are_legal_and_deterministic() -> None:
    state = _state_for_positioning()
    a1 = generate_candidates(state)
    a2 = generate_candidates(state)

    assert [x.action_id for x in a1] == [x.action_id for x in a2]

    for a in a1:
        if not isinstance(a.details, PositioningDetails):
            continue

        seen_pos: set[tuple[int, int]] = set()
        seen_units: set[str] = set()
        for unit_id, row, col in a.details.assignments:
            assert unit_id not in seen_units
            seen_units.add(unit_id)

            assert is_valid_board_pos(row, col)
            pos = (row, col)
            assert pos not in seen_pos
            seen_pos.add(pos)
