"""Core combat loop utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

CubeCoord = Tuple[int, int, int]

CUBE_DIRECTIONS: Tuple[CubeCoord, ...] = (
    (1, -1, 0),
    (1, 0, -1),
    (0, 1, -1),
    (-1, 1, 0),
    (-1, 0, 1),
    (0, -1, 1),
)


@dataclass
class Unit:
    unit_id: str
    team: str
    position: CubeCoord
    attack_range: int
    move_speed: float = 1.0
    health: float = 100.0
    target: Optional["Unit"] = None
    move_progress: float = 0.0

    @property
    def alive(self) -> bool:
        return self.health > 0


@dataclass
class CombatLoop:
    units: List[Unit] = field(default_factory=list)

    def tick(self) -> None:
        self._refresh_targets()
        self._move_units()

    def _refresh_targets(self) -> None:
        for unit in self.units:
            if not unit.alive:
                unit.target = None
                continue
            if self._needs_retarget(unit):
                unit.target = self._acquire_target(unit)

    def _needs_retarget(self, unit: Unit) -> bool:
        if unit.target is None:
            return True
        if not unit.target.alive:
            return True
        if self._out_of_range(unit, unit.target):
            return True
        return False

    def _acquire_target(self, unit: Unit) -> Optional[Unit]:
        enemies = [
            enemy
            for enemy in self.units
            if enemy.alive and enemy.team != unit.team
        ]
        if not enemies:
            return None
        return min(enemies, key=lambda enemy: (cube_distance(unit.position, enemy.position), enemy.unit_id))

    def _move_units(self) -> None:
        for unit in self.units:
            if not unit.alive or unit.target is None:
                continue
            if self._in_range(unit, unit.target):
                continue
            self._advance_towards_target(unit, unit.target)

    def _advance_towards_target(self, unit: Unit, target: Unit) -> None:
        unit.move_progress += unit.move_speed
        while unit.move_progress >= 1 and not self._in_range(unit, target):
            next_step = choose_step_towards(unit.position, target.position)
            if next_step is None:
                break
            unit.position = next_step
            unit.move_progress -= 1

    @staticmethod
    def _in_range(unit: Unit, target: Unit) -> bool:
        return cube_distance(unit.position, target.position) <= unit.attack_range

    @staticmethod
    def _out_of_range(unit: Unit, target: Unit) -> bool:
        return cube_distance(unit.position, target.position) > unit.attack_range


def cube_distance(a: CubeCoord, b: CubeCoord) -> int:
    return int((abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) / 2)


def cube_neighbors(position: CubeCoord) -> Iterable[CubeCoord]:
    for direction in CUBE_DIRECTIONS:
        yield (
            position[0] + direction[0],
            position[1] + direction[1],
            position[2] + direction[2],
        )


def choose_step_towards(start: CubeCoord, target: CubeCoord) -> Optional[CubeCoord]:
    current_distance = cube_distance(start, target)
    best_step: Optional[CubeCoord] = None
    best_distance = current_distance
    for neighbor in cube_neighbors(start):
        distance = cube_distance(neighbor, target)
        if distance < best_distance:
            best_distance = distance
            best_step = neighbor
    return best_step
