"""Deterministic combat loop scaffold for TFT-style simulations.

This module implements a minimal tick-based combat loop with:
- Hex distance math (cube coordinates)
- Deterministic RNG
- Unit state machine (idle -> windup -> resolve)
- Basic targeting and damage resolution

It is intentionally conservative: the goal is a stable kernel to extend
with ability scripts, items, and augments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Tuple


class StateType(str, Enum):
    IDLE = "IDLE"
    ACQUIRING_TARGET = "ACQUIRING_TARGET"
    MOVING = "MOVING"
    ATTACK_WINDUP = "ATTACK_WINDUP"
    ATTACK_RESOLVE = "ATTACK_RESOLVE"
    CASTING = "CASTING"


@dataclass(frozen=True)
class Position:
    """Cube coordinates for hex grids."""

    x: int
    y: int
    z: int

    def distance(self, other: "Position") -> int:
        return (abs(self.x - other.x) + abs(self.y - other.y) + abs(self.z - other.z)) // 2


@dataclass
class Stats:
    hp: float
    max_hp: float
    ad: float
    attack_speed: float
    attack_range: int
    armor: float
    mr: float
    crit_chance: float = 0.25
    crit_multiplier: float = 1.5
    mana: float = 0.0
    max_mana: float = 100.0


@dataclass
class UnitState:
    state: StateType = StateType.IDLE
    target: Optional[int] = None
    windup_timer: float = 0.0
    recovery_timer: float = 0.0


@dataclass
class CombatLogEvent:
    tick: int
    source: int
    target: int
    damage: float
    crit: bool


@dataclass
class CombatResult:
    winner: Optional[str]
    duration: float
    log: List[CombatLogEvent] = field(default_factory=list)


class CombatRNG:
    """Xorshift RNG for deterministic combat."""

    def __init__(self, seed: int = 1):
        self.state = seed & 0xFFFFFFFF

    def random(self) -> float:
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17) & 0xFFFFFFFF
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state / 0xFFFFFFFF


class World:
    """Minimal ECS-like container for combat entities."""

    def __init__(self) -> None:
        self.positions: Dict[int, Position] = {}
        self.stats: Dict[int, Stats] = {}
        self.states: Dict[int, UnitState] = {}
        self.teams: Dict[int, str] = {}
        self._next_entity_id = 1

    def add_unit(self, team: str, position: Position, stats: Stats) -> int:
        entity_id = self._next_entity_id
        self._next_entity_id += 1
        self.positions[entity_id] = position
        self.stats[entity_id] = stats
        self.states[entity_id] = UnitState()
        self.teams[entity_id] = team
        return entity_id

    def living_entities(self) -> Iterable[int]:
        for entity_id, stats in self.stats.items():
            if stats.hp > 0:
                yield entity_id

    def enemies_of(self, entity_id: int) -> Iterable[int]:
        team = self.teams[entity_id]
        for other_id in self.living_entities():
            if other_id != entity_id and self.teams[other_id] != team:
                yield other_id

    def allies_of(self, entity_id: int) -> Iterable[int]:
        team = self.teams[entity_id]
        for other_id in self.living_entities():
            if other_id != entity_id and self.teams[other_id] == team:
                yield other_id


def _select_target(world: World, attacker: int) -> Optional[int]:
    candidates = list(world.enemies_of(attacker))
    if not candidates:
        return None

    attacker_pos = world.positions[attacker]
    candidates.sort(key=lambda eid: attacker_pos.distance(world.positions[eid]))
    return candidates[0]


def _in_range(world: World, attacker: int, target: int) -> bool:
    attacker_pos = world.positions[attacker]
    target_pos = world.positions[target]
    return attacker_pos.distance(target_pos) <= world.stats[attacker].attack_range


def _attack_interval(stats: Stats) -> float:
    if stats.attack_speed <= 0:
        return 999.0
    return 1.0 / stats.attack_speed


def _apply_damage(world: World, rng: CombatRNG, source: int, target: int) -> Tuple[float, bool]:
    source_stats = world.stats[source]
    target_stats = world.stats[target]

    crit = rng.random() < source_stats.crit_chance
    damage = source_stats.ad
    if crit:
        damage *= source_stats.crit_multiplier

    if target_stats.armor >= 0:
        damage *= 100 / (100 + target_stats.armor)
    else:
        damage *= 2 - 100 / (100 - target_stats.armor)

    target_stats.hp = max(0.0, target_stats.hp - damage)
    return damage, crit


def run_combat(
    world: World,
    rng: Optional[CombatRNG] = None,
    max_time: float = 30.0,
    tick_rate: float = 30.0,
    windup_ratio: float = 0.3,
) -> CombatResult:
    """Run a deterministic combat loop until one team remains or time runs out."""

    if rng is None:
        rng = CombatRNG(1)

    dt = 1.0 / tick_rate
    total_ticks = int(max_time * tick_rate)
    log: List[CombatLogEvent] = []

    for tick in range(total_ticks):
        alive = list(world.living_entities())
        if not alive:
            return CombatResult(winner=None, duration=tick * dt, log=log)

        teams_alive = {world.teams[eid] for eid in alive}
        if len(teams_alive) <= 1:
            winner = next(iter(teams_alive)) if teams_alive else None
            return CombatResult(winner=winner, duration=tick * dt, log=log)

        for entity_id in alive:
            state = world.states[entity_id]
            stats = world.stats[entity_id]

            if (
                state.target is None
                or state.target not in world.stats
                or world.stats[state.target].hp <= 0
            ):
                state.target = _select_target(world, entity_id)
                state.state = StateType.ACQUIRING_TARGET

            if state.target is None:
                continue

            if state.state in (StateType.IDLE, StateType.ACQUIRING_TARGET):
                if _in_range(world, entity_id, state.target):
                    state.state = StateType.ATTACK_WINDUP
                    state.windup_timer = _attack_interval(stats) * windup_ratio
                else:
                    state.state = StateType.MOVING

            if state.state == StateType.MOVING:
                if _in_range(world, entity_id, state.target):
                    state.state = StateType.ATTACK_WINDUP
                    state.windup_timer = _attack_interval(stats) * windup_ratio

            if state.state == StateType.ATTACK_WINDUP:
                state.windup_timer -= dt
                if state.windup_timer <= 0:
                    state.state = StateType.ATTACK_RESOLVE

            if state.state == StateType.ATTACK_RESOLVE:
                if world.stats[state.target].hp > 0 and _in_range(world, entity_id, state.target):
                    damage, crit = _apply_damage(world, rng, entity_id, state.target)
                    log.append(
                        CombatLogEvent(
                            tick=tick,
                            source=entity_id,
                            target=state.target,
                            damage=damage,
                            crit=crit,
                        )
                    )
                state.state = StateType.IDLE

    return CombatResult(winner=None, duration=max_time, log=log)
