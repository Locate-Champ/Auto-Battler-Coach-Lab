from __future__ import annotations

from coach.actions import DecisionType
from coach.coach import Coach
from coach.state import GameState, OpponentState, PlayerState, UnitState


def _sample_state() -> GameState:
    player = PlayerState(level=7, hp=62, gold=28, win_streak=2, loss_streak=0)
    board = (
        UnitState(
            instance_id="u_sion",
            champion_id="TFT16_Sion",
            star_level=2,
            items=("TFT_Item_BrambleVest", "TFT_Item_DragonsClaw"),
            position=(3, 3),
            location="board",
        ),
        UnitState(
            instance_id="u_leona",
            champion_id="TFT16_Leona",
            star_level=2,
            items=(),
            position=(3, 2),
            location="board",
        ),
        UnitState(
            instance_id="u_draven",
            champion_id="TFT16_Draven",
            star_level=2,
            items=("TFT_Item_GuinsoosRageblade",),
            position=(0, 6),
            location="board",
        ),
        UnitState(
            instance_id="u_twistedfate",
            champion_id="TFT16_TwistedFate",
            star_level=1,
            items=(),
            position=(0, 3),
            location="board",
        ),
    )

    opponent_board = (
        UnitState(
            instance_id="o_sion",
            champion_id="TFT16_Sion",
            star_level=2,
            items=("TFT_Item_WarmogsArmor",),
            position=(3, 3),
            location="board",
        ),
        UnitState(
            instance_id="o_vayne",
            champion_id="TFT16_Vayne",
            star_level=2,
            items=("TFT_Item_LastWhisper",),
            position=(0, 6),
            location="board",
        ),
    )

    opponents = (
        OpponentState(opponent_id="opp_0", board=opponent_board, level=7, hp=74),
    )

    items = (
        "BF_Sword",
        "Recurve_Bow",
        "Needlessly_Large_Rod",
        "Tear_of_the_Goddess",
    )

    return GameState(
        stage="4-2",
        player=player,
        board=board,
        items=items,
        augments=(),
        opponents=opponents,
    )


def main() -> None:
    state = _sample_state()
    coach = Coach()

    print("=" * 72)
    print("COACH DEMO: planning with a critic (items + positioning + econ)")
    print("=" * 72)
    print()

    for decision in (DecisionType.ITEMS, DecisionType.POSITION, DecisionType.ECON):
        recs = coach.recommend(state, decision, top_k=3)
        print(f"[{decision.value.upper()}] Top recommendations")
        for r in recs:
            print(f"  - score={r.score.total_score:.3f} action_id={r.action.action_id} title={r.action.title}")
            print(f"    confidence={r.explanation.confidence}")
            for line in r.explanation.lines:
                print(f"      {line}")
        print()


if __name__ == "__main__":
    main()
