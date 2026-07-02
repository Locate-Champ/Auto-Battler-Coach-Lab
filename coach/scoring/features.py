from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Optional

from coach.state import GameState, UnitState

_CHAMPION_REF_CACHE: Optional[dict[str, dict]] = None
_CHAMPIONS_BY_COST_CACHE: Optional[dict[int, tuple[str, ...]]] = None


def _fallback_champion_ref() -> dict[str, dict]:
    """
    Build a best-effort champion ref from simulator constants when
    data/game_data/champions.jsonl is unavailable locally.
    """
    try:
        from simulator.game.constants import API_TO_NAME, NAME_TO_COST
    except (ImportError, OSError):
        return {}

    ref: dict[str, dict] = {}
    for api_name, short_name in API_TO_NAME.items():
        try:
            cost = int(NAME_TO_COST.get(short_name, 3) or 3)
        except (ValueError, TypeError):
            cost = 3
        ref[api_name] = {
            "name": str(short_name or api_name),
            "cost": cost,
            "traits": (),
        }
    return ref


def _load_champion_ref(data_dir: Optional[Path] = None) -> dict[str, dict]:
    global _CHAMPION_REF_CACHE
    if _CHAMPION_REF_CACHE is not None:
        return _CHAMPION_REF_CACHE

    root = data_dir or Path(__file__).resolve().parents[2]
    path = root / "data" / "game_data" / "champions.jsonl"
    ref: dict[str, dict] = {}
    if not path.exists():
        ref = _fallback_champion_ref()
        _CHAMPION_REF_CACHE = ref
        return ref

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            api = row.get("apiName")
            if not api:
                continue
            ref[api] = {
                "name": row.get("name", api),
                "cost": int(row.get("cost", 3) or 3),
                "traits": tuple(row.get("traits", []) or []),
            }

    if not ref:
        ref = _fallback_champion_ref()

    _CHAMPION_REF_CACHE = ref
    return ref


def champions_by_cost() -> dict[int, tuple[str, ...]]:
    global _CHAMPIONS_BY_COST_CACHE
    if _CHAMPIONS_BY_COST_CACHE is not None:
        return _CHAMPIONS_BY_COST_CACHE

    ref = _load_champion_ref()
    grouped: dict[int, list[str]] = {}
    for api_name, info in ref.items():
        try:
            cost = int(info.get("cost", 3) or 3)
        except (ValueError, TypeError):
            cost = 3
        grouped.setdefault(cost, []).append(api_name)

    out: dict[int, tuple[str, ...]] = {c: tuple(sorted(xs)) for c, xs in grouped.items()}
    _CHAMPIONS_BY_COST_CACHE = out
    return out


def champion_cost(champion_id: str) -> int:
    ref = _load_champion_ref()
    info = ref.get(champion_id)
    if info is None:
        return 3
    return int(info.get("cost", 3) or 3)


def champion_name(champion_id: str) -> str:
    ref = _load_champion_ref()
    info = ref.get(champion_id)
    if info is None:
        # TFT16_Ekko -> Ekko
        return champion_id.split("_", 1)[-1] if "_" in champion_id else champion_id
    return str(info.get("name", champion_id))


def champion_traits(champion_id: str) -> tuple[str, ...]:
    ref = _load_champion_ref()
    info = ref.get(champion_id)
    if info is None:
        return ()
    traits = info.get("traits") or ()
    return tuple(traits)


def derive_traits(units: tuple[UnitState, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for u in units:
        if u.location != "board":
            continue
        for t in champion_traits(u.champion_id):
            counts[t] = counts.get(t, 0) + 1
    return counts


def with_derived_traits(state: GameState) -> GameState:
    traits = derive_traits(state.board)
    traits_tuple = tuple(sorted(traits.items(), key=lambda kv: kv[0]))
    return replace(state, traits=traits_tuple)


def board_power(units: tuple[UnitState, ...]) -> float:
    # A simple, order-invariant baseline: cost * star multiplier plus small item value.
    total = 0.0
    for u in units:
        if u.location != "board":
            continue
        cost = champion_cost(u.champion_id)
        star_mult = {1: 1.0, 2: 3.0, 3: 9.0}.get(int(u.star_level), 1.0)
        total += float(cost) * star_mult
        total += 0.25 * len(u.items)
    return total


def detect_carry(units: tuple[UnitState, ...]) -> Optional[UnitState]:
    best: Optional[UnitState] = None
    best_key = None
    for u in units:
        if u.location != "board":
            continue
        key = (len(u.items), champion_cost(u.champion_id), u.star_level)
        if best_key is None or key > best_key:
            best = u
            best_key = key
    return best


def plan_value_score(state: GameState) -> float:
    # Lightweight econ score (0..1-ish): rewards interest, gold stability, and HP safety.
    interest = state.player.interest / 5.0
    gold = min(max(state.player.gold, 0), 50) / 50.0
    hp = min(max(state.player.hp, 0), 100) / 100.0

    # Small stage-aware pressure: low HP in late game is worse.
    stage = max(state.stage_number, 0)
    hp_weight = 0.35 if stage >= 4 else 0.25
    return 0.40 * interest + 0.35 * gold + hp_weight * hp


def squash01(x: float, midpoint: float, sharpness: float) -> float:
    # Numerically-stable logistic.
    z = max(min(sharpness * (x - midpoint), 60.0), -60.0)
    return 1.0 / (1.0 + math.exp(-z))


def _star_copies(star_level: int) -> int:
    return {1: 1, 2: 3, 3: 9}.get(int(star_level), 1)


def copy_counts(units: tuple[UnitState, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for u in units:
        counts[u.champion_id] = counts.get(u.champion_id, 0) + _star_copies(u.star_level)
    return counts


def lobby_copy_counts(state: GameState) -> dict[str, int]:
    # Best-effort pool tracker: self + any known opponent boards.
    counts: dict[str, int] = {}
    for u in (*state.board, *state.bench):
        counts[u.champion_id] = counts.get(u.champion_id, 0) + _star_copies(u.star_level)
    for opp in state.opponents:
        for u in opp.board:
            counts[u.champion_id] = counts.get(u.champion_id, 0) + _star_copies(u.star_level)
    return counts
