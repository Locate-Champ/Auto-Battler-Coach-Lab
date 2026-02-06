"""Main TFT game loop.

Orchestrates an 8-player TFT game: rounds, economy, combat, elimination.
Uses the existing combat engine for fight resolution.
"""

from __future__ import annotations

import random
import sys
import os
from typing import List, Dict, Optional, Tuple, Callable

from .types import RoundResult, GamePhase
from .player import Player
from .champion_pool import ChampionPool
from .shop import generate_shop, _return_shop_to_pool
from .actions import random_agent_actions, execute_action
from .constants import (
    get_round_damage, STARTING_ROUND_GOLD, BOARD_ROWS,
    ITEM_COMPONENTS_LIST, PVE_ITEM_DROPS, AUGMENT_ROUNDS,
    CAROUSEL_ROUNDS, CAROUSEL_CHAMPION_ODDS, CAROUSEL_ITEM_WEIGHTS,
    CAROUSEL_SIZE, CHAMPIONS_BY_COST, NAME_TO_API,
)

# Import combat engine
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from simulator.core.combat_engine import CombatEngine

# Load augment data for augment selection
import json
from pathlib import Path

_AUGMENT_PATH = Path(__file__).parent.parent.parent / "data" / "api" / "processed" / "augments_set16.json"
_AUGMENTS_BY_ROUND: Dict[str, List[str]] = {'2-1': [], '3-2': [], '4-2': []}
_AUGMENT_TRAITS: Dict[str, List[str]] = {}  # apiName -> associated trait names

# Augment tier inference from stage availability:
# - 2-1 only → Silver (weaker, early)
# - 3-2 only, 2-1+3-2 → Gold (mid-tier)
# - 4-2 only, 3-2+4-2 → Prismatic (powerful, late)
# - All stages → Gold (flexible)
_AUGMENT_TIERS: Dict[str, str] = {}  # apiName -> 'silver'|'gold'|'prismatic'

# Tier distribution per stage from tftodds.com (Set 16)
# At each stage, each of the 3 offered augments independently rolls a tier
_TIER_ODDS_BY_STAGE = {
    '2-1': {'silver': 0.28, 'gold': 0.62, 'prismatic': 0.10},
    '3-2': {'silver': 0.35, 'gold': 0.45, 'prismatic': 0.20},
    '4-2': {'silver': 0.06, 'gold': 0.74, 'prismatic': 0.20},
}

# Augments by tier within each round (for weighted selection)
_AUGMENTS_BY_ROUND_TIER: Dict[str, Dict[str, List[str]]] = {
    '2-1': {'silver': [], 'gold': [], 'prismatic': []},
    '3-2': {'silver': [], 'gold': [], 'prismatic': []},
    '4-2': {'silver': [], 'gold': [], 'prismatic': []},
}

try:
    if _AUGMENT_PATH.exists():
        with open(_AUGMENT_PATH, 'r', encoding='utf-8') as _f:
            _raw = json.load(_f)
        _round_tags = {'2-1', '3-2', '4-2'}
        for _aug in _raw:
            if _aug.get('disabled'):
                continue
            _api = _aug['apiName']
            _stages = sorted(t for t in _aug.get('tags', []) if t in _round_tags)

            # Store trait associations
            if _aug.get('associatedTraits'):
                _AUGMENT_TRAITS[_api] = _aug['associatedTraits']

            # Infer tier from stage availability
            _stage_key = tuple(_stages)
            if _stage_key == ('2-1',):
                _AUGMENT_TIERS[_api] = 'silver'
            elif _stage_key in (('3-2',), ('2-1', '3-2')):
                _AUGMENT_TIERS[_api] = 'gold'
            elif _stage_key in (('4-2',), ('3-2', '4-2')):
                _AUGMENT_TIERS[_api] = 'prismatic'
            elif _stage_key == ('2-1', '3-2', '4-2'):
                _AUGMENT_TIERS[_api] = 'gold'  # Flexible → default gold
            else:
                _AUGMENT_TIERS[_api] = 'gold'

            # Add to round + tier pools
            for _tag in _stages:
                _AUGMENTS_BY_ROUND[_tag].append(_api)
                _tier = _AUGMENT_TIERS[_api]
                _AUGMENTS_BY_ROUND_TIER[_tag][_tier].append(_api)
except Exception:
    pass


class TFTGame:
    """Runs a full 8-player TFT game.

    Usage:
        game = TFTGame(seed=42)
        placements = game.play()
        # placements = [(player_id, placement), ...]
    """

    def __init__(self, num_players: int = 8, seed: int = None,
                 agent_fn: Callable = None, verbose: bool = False):
        """Initialize a new TFT game.

        Args:
            num_players: Number of players (default 8).
            seed: Random seed for deterministic games.
            agent_fn: Function(player, pool) -> list of Actions.
                      Defaults to random_agent_actions.
            verbose: Print round-by-round updates.
        """
        if seed is not None:
            random.seed(seed)

        self.num_players = num_players
        self.verbose = verbose
        self.agent_fn = agent_fn or random_agent_actions

        # Initialize shared state
        self.pool = ChampionPool()
        self.engine = CombatEngine()
        self.players = [Player(i) for i in range(num_players)]
        self.round_num = 0
        self.placements: List[Tuple[int, int]] = []  # (player_id, placement)

        # Player augments: player_id -> list of chosen augment apiNames
        self.player_augments: Dict[int, List[str]] = {i: [] for i in range(num_players)}

        # Matchmaking weights: tracks recent opponents to avoid repeats
        # weights[i][j] = weight for player i fighting player j
        self._matchmaking_weights = [
            [10] * num_players for _ in range(num_players)
        ]
        for i in range(num_players):
            self._matchmaking_weights[i][i] = 0  # Can't fight yourself

    @property
    def alive_players(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def play(self) -> List[Tuple[int, int]]:
        """Run the full game and return placements.

        Returns:
            List of (player_id, placement) tuples, sorted by placement.
            Placement 1 = winner, num_players = first eliminated.
        """
        # Rounds 0-3: PvE / early game (simplified: just grant gold)
        for r in range(min(4, len(STARTING_ROUND_GOLD))):
            self.round_num = r
            if r in CAROUSEL_ROUNDS:
                # Round 3: first carousel
                if self.verbose:
                    print(f"\n--- Round {r} (Carousel) ---")
                self._carousel_phase()
            self._pve_round()

        # Main game loop
        self.round_num = 4
        while len(self.alive_players) > 1:
            if self.round_num in CAROUSEL_ROUNDS:
                if self.verbose:
                    print(f"\n--- Round {self.round_num} (Carousel) ---")
                self._carousel_phase()
            self._pvp_round()
            self.round_num += 1

            # Safety valve
            if self.round_num > 60:
                break

        # Record winner
        for p in self.alive_players:
            self.placements.append((p.player_id, 1))
            p.placement = 1

        self.placements.sort(key=lambda x: x[1])
        return self.placements

    # ── PvE Rounds (Simplified) ───────────────────────────────────────────

    def _pve_round(self):
        """Simplified PvE round: grant income, drop items, let players shop."""
        if self.verbose:
            print(f"\n--- Round {self.round_num} (PvE) ---")

        for player in self.alive_players:
            player.add_income(self.round_num)

            # Drop item components
            drop_range = PVE_ITEM_DROPS.get(self.round_num, (0, 0))
            num_drops = random.randint(drop_range[0], drop_range[1])
            for _ in range(num_drops):
                component = random.choice(ITEM_COMPONENTS_LIST)
                player.add_item_to_bench(component)

            # Generate shop
            _return_shop_to_pool(player, self.pool)
            player.shop = generate_shop(self.pool, player.level)
            # Let agent take actions
            self.agent_fn(player, self.pool)
            player.auto_fill_board()

    # ── PvP Rounds ────────────────────────────────────────────────────────

    def _pvp_round(self):
        """Full PvP round: income → augments → planning → combat → damage."""
        if self.verbose:
            print(f"\n--- Round {self.round_num} (PvP) ---")

        # 0. Augment selection (at rounds 4, 11, 18)
        if self.round_num in AUGMENT_ROUNDS:
            self._augment_selection_phase()

        # 1. Income phase
        for player in self.alive_players:
            player.add_income(self.round_num)

        # 2. Planning phase (shop + actions)
        for player in self.alive_players:
            _return_shop_to_pool(player, self.pool)
            player.shop = generate_shop(self.pool, player.level)
            self.agent_fn(player, self.pool)
            player.auto_fill_board()

        # 3. Matchmaking
        matchups = self._matchmake()

        # 4. Combat phase
        for p1_id, p2_id, is_ghost in matchups:
            p1 = self.players[p1_id]
            p2 = self.players[p2_id]
            if not p1.alive:
                continue

            result = self._resolve_combat(p1, p2)

            if result.is_draw:
                # Both take base damage
                p1.take_damage(result.damage_to_loser)
                p2.take_damage(result.damage_to_loser)
            elif result.winner_id == p1.player_id:
                p1.win_round()
                if not is_ghost:
                    p2.lose_round(result.damage_to_loser)
            else:
                if not is_ghost:
                    p2.win_round()
                p1.lose_round(result.damage_to_loser)

        # 5. Check eliminations
        self._check_eliminations()

        if self.verbose:
            for p in self.players:
                status = "DEAD" if not p.alive else f"HP={p.hp}"
                print(f"  P{p.player_id}: {status}, gold={p.gold}, "
                      f"lvl={p.level}, board={p.board_count}")

    # ── Augment Selection ──────────────────────────────────────────────────

    # Map from game round number to augment tag in data
    _ROUND_TO_TAG = {4: '2-1', 11: '3-2', 18: '4-2'}

    def _augment_selection_phase(self):
        """Offer each player 3 augments with proper tier distribution.

        Uses Silver/Gold/Prismatic odds from tftodds.com per stage,
        and boosts trait-synergistic augments in the pool.
        """
        tag = self._ROUND_TO_TAG.get(self.round_num)
        if not tag:
            return
        tier_pools = _AUGMENTS_BY_ROUND_TIER.get(tag, {})
        tier_odds = _TIER_ODDS_BY_STAGE.get(tag, {})
        if not tier_pools or not tier_odds:
            return

        tiers = list(tier_odds.keys())
        weights = [tier_odds[t] for t in tiers]

        for player in self.alive_players:
            already_chosen = set(self.player_augments[player.player_id])
            active_traits = set(player.get_active_traits().keys())

            choices = []
            for _ in range(3):
                # Roll a tier using Silver/Gold/Prismatic distribution
                tier = random.choices(tiers, weights=weights, k=1)[0]
                pool = [a for a in tier_pools.get(tier, [])
                        if a not in already_chosen and a not in choices]

                if not pool:
                    # Fallback: try any tier
                    pool = [a for a in _AUGMENTS_BY_ROUND.get(tag, [])
                            if a not in already_chosen and a not in choices]

                if not pool:
                    continue

                # Weight augments: trait-synergistic augments get 3x weight
                aug_weights = []
                for aug in pool:
                    w = 1.0
                    aug_traits = _AUGMENT_TRAITS.get(aug, [])
                    if aug_traits and active_traits:
                        # Boost if any associated trait matches player's board
                        if active_traits & set(aug_traits):
                            w = 3.0
                    aug_weights.append(w)

                chosen_aug = random.choices(pool, weights=aug_weights, k=1)[0]
                choices.append(chosen_aug)

            if not choices:
                continue

            # Random agent picks randomly; a real agent_fn would use
            # a separate augment callback
            chosen = random.choice(choices)
            self.player_augments[player.player_id].append(chosen)

            if self.verbose:
                tier_str = _AUGMENT_TIERS.get(chosen, '?')
                print(f"  P{player.player_id} chose augment: {chosen} "
                      f"[{tier_str}] (from {len(choices)} options)")

    # ── Carousel ──────────────────────────────────────────────────────────

    def _carousel_phase(self):
        """Shared draft: players pick a champion with an item.

        Pick order is based on HP (lowest HP picks first).
        Each carousel champion has a random component item.
        """
        # Sort players by HP ascending (lowest picks first)
        pick_order = sorted(self.alive_players, key=lambda p: (p.hp, p.player_id))

        # Generate carousel champions with items
        cost_odds = CAROUSEL_CHAMPION_ODDS.get(self.round_num, [0.5, 0.3, 0.2, 0, 0])
        item_names = list(CAROUSEL_ITEM_WEIGHTS.keys())
        item_weights = list(CAROUSEL_ITEM_WEIGHTS.values())

        carousel = []
        for _ in range(CAROUSEL_SIZE):
            # Roll champion cost tier
            cost = random.choices([1, 2, 3, 4, 5], weights=cost_odds, k=1)[0]
            champs = CHAMPIONS_BY_COST.get(cost, {})
            if not champs:
                continue
            champ_name = random.choice(list(champs.keys()))
            # Roll an item component
            item = random.choices(item_names, weights=item_weights, k=1)[0]
            carousel.append((champ_name, cost, item))

        if not carousel:
            return

        # Each player picks one champion (lowest HP first)
        for player in pick_order:
            if not carousel:
                break

            # Simple AI: pick randomly (a real agent would prefer items/champs)
            pick_idx = random.randrange(len(carousel))
            champ_name, cost, item = carousel.pop(pick_idx)

            # Try to add to bench
            from .types import ChampionInstance
            champ = ChampionInstance(
                name=champ_name,
                api_name=NAME_TO_API.get(champ_name, f'TFT16_{champ_name.capitalize()}'),
                cost=cost,
                star_level=1,
                items=[item],
            )
            bench_idx = player._find_empty_bench()
            if bench_idx is not None:
                player.bench[bench_idx] = champ
                # Take from pool
                self.pool.take(champ_name)
                # Check for upgrade
                player._check_upgrade(champ_name, self.pool)

            if self.verbose:
                print(f"  P{player.player_id} (HP={player.hp}) picks "
                      f"{champ_name} [{item}]")

    # ── Combat Resolution ─────────────────────────────────────────────────

    def _resolve_combat(self, p1: Player, p2: Player) -> RoundResult:
        """Resolve combat between two players using the combat engine."""
        team0 = p1.build_combat_team(self.engine)
        team1 = p2.build_combat_team(self.engine)

        # Handle empty boards
        if not team0 and not team1:
            base_damage = get_round_damage(self.round_num, 0)
            return RoundResult(
                winner_id=p1.player_id, loser_id=p2.player_id,
                survivors=0, combat_time=0, damage_to_loser=base_damage,
                is_draw=True,
            )
        if not team0:
            damage = get_round_damage(self.round_num, len(team1))
            return RoundResult(
                winner_id=p2.player_id, loser_id=p1.player_id,
                survivors=len(team1), combat_time=0,
                damage_to_loser=damage,
            )
        if not team1:
            damage = get_round_damage(self.round_num, len(team0))
            return RoundResult(
                winner_id=p1.player_id, loser_id=p2.player_id,
                survivors=len(team0), combat_time=0,
                damage_to_loser=damage,
            )

        # Mirror team1 positions (flip rows) for opponent side
        for unit in team1:
            unit.team = 1
            row, col = unit.position
            unit.position = (BOARD_ROWS - 1 - row, col)

        # Pass player augments to combat engine
        p1_augments = self.player_augments.get(p1.player_id, [])
        p2_augments = self.player_augments.get(p2.player_id, [])
        result = self.engine.run_combat(
            team0, team1,
            team0_augments=p1_augments if p1_augments else None,
            team1_augments=p2_augments if p2_augments else None,
        )

        if result['winner'] == 0:
            damage = get_round_damage(self.round_num, result['team0_survivors'])
            return RoundResult(
                winner_id=p1.player_id, loser_id=p2.player_id,
                survivors=result['team0_survivors'],
                combat_time=result['combat_time'],
                damage_to_loser=damage,
            )
        else:
            damage = get_round_damage(self.round_num, result['team1_survivors'])
            return RoundResult(
                winner_id=p2.player_id, loser_id=p1.player_id,
                survivors=result['team1_survivors'],
                combat_time=result['combat_time'],
                damage_to_loser=damage,
            )

    # ── Matchmaking ───────────────────────────────────────────────────────

    def _matchmake(self) -> List[Tuple[int, int, bool]]:
        """Pair alive players for combat. Returns (p1_id, p2_id, is_ghost).

        Uses weighted random matchmaking to avoid repeat opponents.
        If odd number of players, one fights a "ghost" (copy of another's board).
        """
        alive = [p for p in self.alive_players]
        random.shuffle(alive)

        matchups = []
        paired = set()

        for player in alive:
            if player.player_id in paired:
                continue

            # Find best opponent based on weights
            candidates = [
                p for p in alive
                if p.player_id != player.player_id
                and p.player_id not in paired
            ]

            if not candidates:
                # Odd player out: fight a ghost
                ghost_opponent = random.choice(
                    [p for p in alive if p.player_id != player.player_id]
                )
                matchups.append(
                    (player.player_id, ghost_opponent.player_id, True)
                )
                paired.add(player.player_id)
                continue

            # Weight-based selection
            weights = [
                self._matchmaking_weights[player.player_id][c.player_id]
                for c in candidates
            ]
            total = sum(weights)
            if total == 0:
                weights = [1] * len(candidates)

            opponent = random.choices(candidates, weights=weights, k=1)[0]
            matchups.append(
                (player.player_id, opponent.player_id, False)
            )
            paired.add(player.player_id)
            paired.add(opponent.player_id)

            # Update weights: fought each other → reset to 0, others increase
            self._matchmaking_weights[player.player_id][opponent.player_id] = 0
            self._matchmaking_weights[opponent.player_id][player.player_id] = 0
            for p in alive:
                pid = p.player_id
                if pid != player.player_id and pid != opponent.player_id:
                    self._matchmaking_weights[player.player_id][pid] += 3
                    self._matchmaking_weights[opponent.player_id][pid] += 3

        return matchups

    # ── Elimination ───────────────────────────────────────────────────────

    def _check_eliminations(self):
        """Check for eliminated players and record placements."""
        newly_dead = [p for p in self.players if not p.alive and p.placement == 0]
        if not newly_dead:
            return

        # All players dying this round get the same placement
        placement = len(self.alive_players) + 1
        for player in newly_dead:
            player.placement = placement
            self.placements.append((player.player_id, placement))
            # Return champions to pool
            self.pool.return_player_champions(player.get_all_champions())

            if self.verbose:
                print(f"  ** Player {player.player_id} eliminated "
                      f"(placement: {placement}) **")

    # ── State Inspection ──────────────────────────────────────────────────

    def get_state(self, player_id: int) -> Dict:
        """Get observable game state for a player (for RL agents)."""
        player = self.players[player_id]
        return {
            'round': self.round_num,
            'phase': 'combat',
            'player': {
                'id': player.player_id,
                'hp': player.hp,
                'gold': player.gold,
                'level': player.level,
                'xp': player.xp,
                'win_streak': player.win_streak,
                'loss_streak': player.loss_streak,
                'board': {
                    f"{r},{c}": {
                        'name': ch.name,
                        'star': ch.star_level,
                        'items': ch.items,
                    }
                    for (r, c), ch in player.board.items()
                },
                'bench': [
                    {'name': ch.name, 'star': ch.star_level, 'items': ch.items}
                    if ch else None
                    for ch in player.bench
                ],
                'shop': player.shop,
                'item_bench': player.item_bench[:],
                'augments': self.player_augments.get(player.player_id, []),
                'traits': player.get_active_traits(),
            },
            'opponents': [
                {
                    'id': p.player_id,
                    'hp': p.hp,
                    'level': p.level,
                    'board_count': p.board_count,
                    'traits': p.get_active_traits(),
                }
                for p in self.players if p.alive and p.player_id != player_id
            ],
            'alive_count': len(self.alive_players),
        }


# ── CLI Entry Point ───────────────────────────────────────────────────────

def main():
    """Run a sample game and print results."""
    print("Starting TFT Game Simulation (Set 16)...")
    print("=" * 50)

    game = TFTGame(num_players=8, seed=42, verbose=True)
    placements = game.play()

    print("\n" + "=" * 50)
    print("FINAL PLACEMENTS:")
    print("=" * 50)
    for player_id, placement in placements:
        p = game.players[player_id]
        print(f"  #{placement}: Player {player_id} "
              f"(HP={p.hp}, Level={p.level}, Board={p.board_count})")

    print(f"\nGame ended after {game.round_num} rounds")


if __name__ == '__main__':
    main()
