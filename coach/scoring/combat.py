from __future__ import annotations

import random
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional

from coach.rules import is_valid_board_pos
from coach.state import GameState, UnitState
from simulator.core.combat_engine import CombatEngine
from simulator.game.constants import BOARD_COLS, BOARD_ROWS, get_round_damage


@dataclass(frozen=True, slots=True)
class CombatEstimate:
    win_prob: float
    expected_hp_delta: float
    n_sims: int
    ci95: Optional[tuple[float, float]] = None
    opponent_policy: str = "proxy_only"  # "next_opponent" | "scouted_set" | "proxy_only"


def _team_signature(units: tuple[UnitState, ...]) -> tuple:
    sig = []
    for u in units:
        if u.location != "board":
            continue
        sig.append((u.champion_id, int(u.star_level), tuple(u.items), u.position))
    sig.sort()
    return tuple(sig)


def _default_positions_for_team(num_units: int) -> list[tuple[int, int]]:
    order: list[tuple[int, int]] = []
    for row in (3, 2, 1, 0):
        for col in range(BOARD_COLS):
            order.append((row, col))
    return order[:num_units]


def _assign_positions_deterministically(units: tuple[UnitState, ...]) -> tuple[UnitState, ...]:
    board_units = [u for u in units if u.location == "board"]
    taken: set[tuple[int, int]] = set()
    defaults = _default_positions_for_team(len(board_units))

    out: list[UnitState] = []
    default_idx = 0
    for u in units:
        if u.location != "board":
            out.append(u)
            continue

        pos = u.position
        if pos is not None and is_valid_board_pos(pos[0], pos[1]) and pos not in taken:
            taken.add(pos)
            out.append(u)
            continue

        while default_idx < len(defaults) and defaults[default_idx] in taken:
            default_idx += 1
        new_pos = defaults[default_idx] if default_idx < len(defaults) else None
        if new_pos is not None:
            taken.add(new_pos)
        out.append(u.with_position(new_pos, location="board"))
        default_idx += 1

    return tuple(out)


class CombatScorer:
    def __init__(self):
        self.engine = CombatEngine(logging_enabled=False)
        self._cache: OrderedDict[tuple, CombatEstimate] = OrderedDict()
        self._cache_max_entries = 4096

    def _build_team(self, units: tuple[UnitState, ...], team_id: int, mirror_rows: bool) -> list:
        units = _assign_positions_deterministically(units)
        out = []
        for u in units:
            if u.location != "board":
                continue
            if u.position is None:
                continue
            row, col = u.position
            if mirror_rows:
                row = BOARD_ROWS - 1 - row
            if not is_valid_board_pos(row, col):
                continue
            unit = self.engine.create_unit(
                api_name=u.champion_id,
                star_level=int(u.star_level),
                position=(row, col),
                team=team_id,
                items=list(u.items) if u.items else None,
            )
            if unit is not None:
                out.append(unit)
        return out

    @staticmethod
    def _ci95_for_win_prob(win_prob: float, n: int) -> Optional[tuple[float, float]]:
        if n <= 0:
            return None
        p = min(max(float(win_prob), 0.0), 1.0)
        se = (p * (1.0 - p) / n) ** 0.5
        lo = max(0.0, p - 1.96 * se)
        hi = min(1.0, p + 1.96 * se)
        return lo, hi

    def simulate_matchup(
        self,
        my_units: tuple[UnitState, ...],
        opp_units: tuple[UnitState, ...],
        *,
        round_num: int,
        num_seeds: int,
        base_seed: int,
    ) -> CombatEstimate:
        key = (
            _team_signature(my_units),
            _team_signature(opp_units),
            int(round_num),
            int(num_seeds),
            int(base_seed),
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        team0 = self._build_team(my_units, team_id=0, mirror_rows=False)
        team1 = self._build_team(opp_units, team_id=1, mirror_rows=True)

        if not team0 or not team1 or num_seeds <= 0:
            metrics = CombatEstimate(
                win_prob=0.0,
                expected_hp_delta=0.0,
                n_sims=0,
                ci95=None,
                opponent_policy="proxy_only",
            )
            self._cache[key] = metrics
            self._cache.move_to_end(key)
            return metrics

        wins = 0
        damage_taken = 0.0

        for i in range(int(num_seeds)):
            seed = int(base_seed) + i
            rng_state = random.getstate()
            try:
                result = self.engine.run_combat(team0, team1, seed=seed)
            finally:
                random.setstate(rng_state)

            winner = result.get("winner")
            if winner == 0:
                wins += 1
                dmg = 0
            else:
                survivors = int(result.get("team1_survivors", 0) or 0)
                dmg = int(get_round_damage(int(round_num), survivors))
            damage_taken += float(dmg)

        win_prob = wins / num_seeds
        expected_hp_delta = -(damage_taken / num_seeds)
        metrics = CombatEstimate(
            win_prob=win_prob,
            expected_hp_delta=expected_hp_delta,
            n_sims=int(num_seeds),
            ci95=self._ci95_for_win_prob(win_prob, int(num_seeds)),
            opponent_policy="next_opponent",
        )
        self._cache[key] = metrics
        self._cache.move_to_end(key)
        while len(self._cache) > int(self._cache_max_entries):
            self._cache.popitem(last=False)
        return metrics

    def simulate_matchup_seeds(
        self,
        my_units: tuple[UnitState, ...],
        opp_units: tuple[UnitState, ...],
        *,
        round_num: int,
        seeds: list[int],
    ) -> CombatEstimate:
        if not seeds:
            return CombatEstimate(
                win_prob=0.0,
                expected_hp_delta=0.0,
                n_sims=0,
                ci95=None,
                opponent_policy="proxy_only",
            )

        # Cache on the explicit seed list; callers can still use base_seed+num_seeds via simulate_matchup.
        key = (
            _team_signature(my_units),
            _team_signature(opp_units),
            int(round_num),
            tuple(int(s) for s in seeds),
        )
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached

        team0 = self._build_team(my_units, team_id=0, mirror_rows=False)
        team1 = self._build_team(opp_units, team_id=1, mirror_rows=True)

        if not team0 or not team1:
            metrics = CombatEstimate(
                win_prob=0.0,
                expected_hp_delta=0.0,
                n_sims=0,
                ci95=None,
                opponent_policy="proxy_only",
            )
            self._cache[key] = metrics
            self._cache.move_to_end(key)
            return metrics

        wins = 0
        damage_taken = 0.0

        for seed in seeds:
            rng_state = random.getstate()
            try:
                result = self.engine.run_combat(team0, team1, seed=int(seed))
            finally:
                random.setstate(rng_state)

            winner = result.get("winner")
            if winner == 0:
                wins += 1
                dmg = 0
            else:
                survivors = int(result.get("team1_survivors", 0) or 0)
                dmg = int(get_round_damage(int(round_num), survivors))
            damage_taken += float(dmg)

        n = len(seeds)
        win_prob = wins / n
        expected_hp_delta = -(damage_taken / n)
        metrics = CombatEstimate(
            win_prob=win_prob,
            expected_hp_delta=expected_hp_delta,
            n_sims=n,
            ci95=self._ci95_for_win_prob(win_prob, n),
            opponent_policy="next_opponent",
        )
        self._cache[key] = metrics
        self._cache.move_to_end(key)
        while len(self._cache) > int(self._cache_max_entries):
            self._cache.popitem(last=False)
        return metrics

    def tempo_for_state(
        self, state: GameState, *, round_num: int, num_seeds: int, base_seed: int
    ) -> Optional[CombatEstimate]:
        opponent_boards = [o for o in state.opponents if o.board]
        if not opponent_boards:
            return None

        sample = opponent_boards[:3]
        if not sample:
            return None

        total_sims = 0
        acc_win = 0.0
        acc_hp = 0.0
        min_win = 1.0
        min_hp = 0.0

        for idx, opp in enumerate(sample):
            metrics = self.simulate_matchup(
                state.board,
                opp.board,
                round_num=int(round_num),
                num_seeds=int(num_seeds),
                base_seed=int(base_seed) + idx * 1000,
            )
            total_sims += metrics.n_sims
            acc_win += metrics.win_prob
            acc_hp += metrics.expected_hp_delta
            min_win = min(min_win, metrics.win_prob)
            min_hp = min(min_hp, metrics.expected_hp_delta)

        n = len(sample)
        mean_win = acc_win / n
        mean_hp = acc_hp / n

        robust_win = 0.70 * mean_win + 0.30 * min_win
        robust_hp = 0.70 * mean_hp + 0.30 * min_hp

        policy = "next_opponent" if len(sample) == 1 else "scouted_set"
        return CombatEstimate(
            win_prob=robust_win,
            expected_hp_delta=robust_hp,
            n_sims=total_sims,
            ci95=self._ci95_for_win_prob(mean_win, total_sims) if total_sims > 0 else None,
            opponent_policy=policy,
        )
