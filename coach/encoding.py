from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .state import GameState


@dataclass(frozen=True, slots=True)
class UnitToken:
    champion_id: str
    star_level: int
    items: tuple[str, ...]
    position: Optional[tuple[int, int]]


@dataclass(frozen=True, slots=True)
class EncodedState:
    units: tuple[UnitToken, ...]
    augments: tuple[str, ...]
    traits: tuple[tuple[str, int], ...]
    scalars: tuple[tuple[str, float], ...]


def encode_state_set_based(state: GameState, include_position: bool = False) -> EncodedState:
    # Set-based: token order is not semantically meaningful; keep stable for hashing/debugging.
    tokens: list[UnitToken] = []
    for u in state.board:
        tokens.append(
            UnitToken(
                champion_id=u.champion_id,
                star_level=u.star_level,
                items=u.items,
                position=u.position if include_position else None,
            )
        )

    tokens.sort(key=lambda t: (t.champion_id, t.star_level, t.items))

    scalars = (
        ("stage", float(state.stage_number)),
        ("round", float(state.round_number)),
        ("level", float(state.player.level)),
        ("hp", float(state.player.hp)),
        ("gold", float(state.player.gold)),
        ("interest", float(state.player.interest)),
        ("streak", float(state.player.streak)),
    )
    return EncodedState(
        units=tuple(tokens),
        augments=tuple(state.augments),
        traits=tuple(state.traits),
        scalars=tuple(scalars),
    )
