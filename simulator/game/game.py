"""Main TFT game loop.

Orchestrates an 8-player TFT game: rounds, economy, combat, elimination.
Uses the existing combat engine for fight resolution.
"""

from __future__ import annotations

import random
import sys
import os
from typing import Any, List, Dict, Optional, Tuple, Callable

from .types import RoundResult, GamePhase, ChampionInstance
from .player import Player
from .champion_pool import ChampionPool
from .shop import generate_shop, _return_shop_to_pool
from .actions import random_agent_actions, fast_random_agent, execute_action
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

# Joint probability table for augment tier sequences (source: tftodds.com Set 16).
# Each entry is (stage_1_tier, stage_2_tier, stage_3_tier, percent).
# The 18 entries sum to 100%. Tiers are dependent across stages.
_AUGMENT_TIER_SEQUENCES = [
    ('silver', 'silver', 'gold', 5),
    ('silver', 'silver', 'prismatic', 5),
    ('silver', 'gold', 'gold', 12),
    ('silver', 'gold', 'prismatic', 5),
    ('silver', 'prismatic', 'prismatic', 1),
    ('gold', 'silver', 'gold', 18),
    ('gold', 'silver', 'prismatic', 2),
    ('gold', 'gold', 'gold', 22),
    ('gold', 'gold', 'prismatic', 3),
    ('gold', 'prismatic', 'silver', 6),
    ('gold', 'prismatic', 'gold', 10),
    ('gold', 'prismatic', 'prismatic', 1),
    ('prismatic', 'silver', 'gold', 4),
    ('prismatic', 'silver', 'prismatic', 1),
    ('prismatic', 'gold', 'gold', 2),
    ('prismatic', 'gold', 'prismatic', 1),
    ('prismatic', 'prismatic', 'gold', 1),
    ('prismatic', 'prismatic', 'prismatic', 1),
]

# Marginal probabilities for stage 1 (derived from joint table)
_TIER_ODDS_STAGE_1 = {'silver': 28, 'gold': 62, 'prismatic': 10}

# Tier ordering for tier-shift augments
_TIER_ORDER = ['silver', 'gold', 'prismatic']

# Augments that shift the NEXT augment tier for the player who chose them
_TIER_SHIFT_AUGMENTS = {
    'TFT_Augment_PowerUp': +1,          # "Augmented Power" - next tier higher
    'TFT_Augment_AdvancedLoan': -1,     # "Advanced Loan" (2-1) - next tier lower
    'TFT_Augment_AdvancedLoanPlus': -1, # "Advanced Loan+" (3-2) - next tier lower
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
                 agent_fn: Callable = None, verbose: bool = False,
                 logging_enabled: bool = True, collector=None,
                 engine: str = 'python'):
        """Initialize a new TFT game.

        Args:
            num_players: Number of players (default 8).
            seed: Random seed for deterministic games.
            agent_fn: Function(player, pool) -> list of Actions.
                      Defaults to fast_random_agent.
            verbose: Print round-by-round updates.
            logging_enabled: Enable combat event logging (disable for batch).
            collector: Optional GameCollector for data capture.
            engine: Combat engine backend ('python' or 'rust').
        """
        if seed is not None:
            random.seed(seed)

        self.num_players = num_players
        self.verbose = verbose
        self.agent_fn = agent_fn or fast_random_agent

        # Initialize shared state
        self.pool = ChampionPool()
        self.engine_name = engine
        self.engine: Any = self._create_combat_engine(logging_enabled)
        self.players = [Player(i) for i in range(num_players)]
        self._alive_cache: List[Player] = self.players[:]
        self.collector = collector
        self.round_num = 0
        self.placements: List[Tuple[int, int]] = []  # (player_id, placement)

        # Player augments: player_id -> list of chosen augment apiNames
        self.player_augments: Dict[int, List[str]] = {i: [] for i in range(num_players)}

        # Lobby-wide augment tier history (dependent probabilities)
        self.lobby_augment_tiers: List[str] = []  # e.g. ['gold', 'silver']

        # Per-player tier shift for next augment (from tier-shifting augments)
        self.player_tier_shifts: Dict[int, int] = {i: 0 for i in range(num_players)}

        # Matchmaking weights: tracks recent opponents to avoid repeats
        # weights[i][j] = weight for player i fighting player j
        self._matchmaking_weights = [
            [10] * num_players for _ in range(num_players)
        ]
        for i in range(num_players):
            self._matchmaking_weights[i][i] = 0  # Can't fight yourself

    def _create_combat_engine(self, logging_enabled: bool) -> Any:
        """Create the selected combat engine backend."""
        if self.engine_name == 'rust':
            try:
                from tft_combat_engine import RustCombatEngine
            except Exception as exc:
                raise RuntimeError(
                    "Rust engine selected but tft_combat_engine is unavailable. "
                    "Build/install it via maturin first."
                ) from exc

            combat_data_path = Path(__file__).parent.parent / 'data' / 'combat_data.json'
            return RustCombatEngine(str(combat_data_path))

        if self.engine_name != 'python':
            raise ValueError(f"Unknown engine '{self.engine_name}'. Expected 'python' or 'rust'.")

        return CombatEngine(logging_enabled=logging_enabled)

    @property
    def alive_players(self) -> List[Player]:
        return self._alive_cache

    def _refresh_alive_cache(self) -> None:
        self._alive_cache = [p for p in self.players if p.alive]

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

        if self.collector:
            self.collector.on_game_end(self)

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
            # Reset placeable structures (player re-places each round)
            player.soldier_positions = []
            player.tower_position = None  # Reset Freljord tower each round
            self.agent_fn(player, self.pool)
            player.auto_fill_board()

        # 3. Matchmaking
        matchups = self._matchmake()
        pre_combat_hp = {player.player_id: player.hp for player in self.alive_players}

        if self.collector:
            self.collector.on_round_start(self, self.round_num)

        # 4. Combat phase
        combat_results = []
        for p1_id, p2_id, is_ghost in matchups:
            p1 = self.players[p1_id]
            p2 = self.players[p2_id]
            if not p1.alive:
                continue

            result = self._resolve_combat(p1, p2)

            if self.collector:
                combat_results.append({
                    'p1': p1_id, 'p2': p2_id,
                    'is_ghost': is_ghost,
                    'winner': result.winner_id,
                    'damage': result.damage_to_loser,
                    'survivors': result.survivors,
                    'combat_time': result.combat_time,
                })

            if result.is_draw:
                # Both take base damage (ghost owner exempt)
                p1.take_damage(result.damage_to_loser)
                if not is_ghost:
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
        self._check_eliminations(pre_combat_hp)

        # 6. Collect round data
        if self.collector:
            self.collector.on_round_end(self, self.round_num, combat_results)

        if self.verbose:
            for p in self.players:
                status = "DEAD" if not p.alive else f"HP={p.hp}"
                print(f"  P{p.player_id}: {status}, gold={p.gold}, "
                      f"lvl={p.level}, board={p.board_count}")

    # ── Augment Selection ──────────────────────────────────────────────────

    # Map from game round number to augment tag in data
    _ROUND_TO_TAG = {4: '2-1', 11: '3-2', 18: '4-2'}

    def _augment_selection_phase(self):
        """Offer each player 3 augments of the same lobby-wide tier.

        Uses dependent conditional probabilities across stages:
        - Stage 1 (2-1): marginal probabilities (Silver 28%, Gold 62%, Prismatic 10%)
        - Stage 2 (3-2): conditional on stage 1 tier
        - Stage 3 (4-2): conditional on stages 1+2 tiers
        Source: tftodds.com Set 16 joint distribution table (18 entries).

        Tier-shifting augments (Augmented Power, Advanced Loan) override the
        lobby tier for that specific player.
        """
        tag = self._ROUND_TO_TAG.get(self.round_num)
        if not tag:
            return
        tier_pools = _AUGMENTS_BY_ROUND_TIER.get(tag, {})
        if not tier_pools:
            return

        # Determine which armory stage this is (0=2-1, 1=3-2, 2=4-2)
        stage_idx = len(self.lobby_augment_tiers)

        # Roll the lobby tier using dependent conditional probabilities
        lobby_tier = self._roll_lobby_tier(stage_idx)
        self.lobby_augment_tiers.append(lobby_tier)

        for player in self.alive_players:
            pid = player.player_id
            already_chosen = set(self.player_augments[pid])

            # Apply per-player tier shift from tier-shifting augments
            player_tier = lobby_tier
            shift = self.player_tier_shifts.get(pid, 0)
            if shift != 0:
                idx = _TIER_ORDER.index(player_tier)
                idx = max(0, min(len(_TIER_ORDER) - 1, idx + shift))
                player_tier = _TIER_ORDER[idx]
                self.player_tier_shifts[pid] = 0  # Consume the shift

            pool = [a for a in tier_pools.get(player_tier, [])
                    if a not in already_chosen]

            if not pool:
                # Fallback: try any augment available at this stage
                pool = [a for a in _AUGMENTS_BY_ROUND.get(tag, [])
                        if a not in already_chosen]

            if not pool:
                continue

            # Pick 3 distinct augments from the same tier pool
            choices = random.sample(pool, min(3, len(pool)))

            # Random agent picks randomly; a real agent_fn would use
            # a separate augment callback
            chosen = random.choice(choices)
            self.player_augments[pid].append(chosen)

            # Check if chosen augment shifts the next tier
            if chosen in _TIER_SHIFT_AUGMENTS:
                self.player_tier_shifts[pid] = _TIER_SHIFT_AUGMENTS[chosen]

            if self.verbose:
                tier_info = f"[{player_tier}]"
                if player_tier != lobby_tier:
                    tier_info += f" (shifted from {lobby_tier})"
                print(f"  P{pid} chose augment: {chosen} "
                      f"{tier_info} (from {len(choices)} options)")

    def _roll_lobby_tier(self, stage_idx: int) -> str:
        """Roll the lobby augment tier using dependent conditional probabilities.

        Args:
            stage_idx: 0 for first armory, 1 for second, 2 for third.

        Returns:
            The tier string ('silver', 'gold', or 'prismatic').
        """
        if stage_idx == 0:
            # First armory: use marginal probabilities
            tiers = list(_TIER_ODDS_STAGE_1.keys())
            weights = list(_TIER_ODDS_STAGE_1.values())
            return random.choices(tiers, weights=weights, k=1)[0]

        # Filter sequences matching the tiers we've already rolled
        matching = []
        for seq in _AUGMENT_TIER_SEQUENCES:
            match = True
            for i in range(stage_idx):
                if seq[i] != self.lobby_augment_tiers[i]:
                    match = False
                    break
            if match:
                matching.append((seq[stage_idx], seq[3]))  # (tier, weight)

        if not matching:
            # Fallback: uniform if no sequences match (shouldn't happen)
            return random.choice(_TIER_ORDER)

        # Build conditional distribution from matching sequences
        tier_weights: Dict[str, int] = {}
        for tier, weight in matching:
            tier_weights[tier] = tier_weights.get(tier, 0) + weight

        tiers = list(tier_weights.keys())
        weights = [tier_weights[t] for t in tiers]
        return random.choices(tiers, weights=weights, k=1)[0]

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
        use_rust_engine = self.engine_name == 'rust'
        team0 = p1.build_combat_team(self.engine, use_rust_engine=use_rust_engine)
        team1 = p2.build_combat_team(self.engine, use_rust_engine=use_rust_engine)

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
            if use_rust_engine:
                unit['team'] = 1
                row, col = unit['position']
                unit['position'] = [BOARD_ROWS - 1 - row, col]
            else:
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

    def _check_eliminations(self, pre_combat_hp: Dict[int, int]):
        """Check eliminated players and apply official end-of-round tie-breakers."""
        newly_dead = [p for p in self.players if not p.alive and p.placement == 0]
        if not newly_dead:
            return

        self._refresh_alive_cache()

        # Official order for same-round eliminations:
        # 1) least negative HP after lethal damage, 2) most HP before combat, 3) random.
        random.shuffle(newly_dead)
        newly_dead.sort(
            key=lambda player: (
                player.elimination_hp,
                pre_combat_hp.get(player.player_id, player.hp),
            ),
            reverse=True,
        )

        placement = len(self._alive_cache) + 1
        for player in newly_dead:
            player.placement = placement
            self.placements.append((player.player_id, placement))
            # Return champions to pool
            self.pool.return_player_champions(player.get_all_champions())
            placement += 1

            if self.verbose:
                print(f"  ** Player {player.player_id} eliminated "
                      f"(placement: {player.placement}) **")

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
