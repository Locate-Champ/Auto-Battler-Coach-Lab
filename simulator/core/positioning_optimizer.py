#!/usr/bin/env python3
"""
TFT Positioning Optimizer

Given a team composition (units with items), find optimal board positions
by running combat simulations against various opponent configurations.

Usage:
    from core.positioning_optimizer import PositioningOptimizer

    optimizer = PositioningOptimizer()

    # Define your comp
    my_comp = [
        {'champion': 'TFT16_Draven', 'star': 2, 'items': ['BF_Sword', 'BF_Sword']},
        {'champion': 'TFT16_Leona', 'star': 2, 'items': ['Chain_Vest']},
        {'champion': 'TFT16_Lux', 'star': 2, 'items': []},
    ]

    # Find optimal positions
    result = optimizer.optimize(my_comp, num_simulations=100)
    print(result['best_positions'])
"""

import random
import itertools
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.combat_engine import CombatEngine, Unit


# TFT board is 7 columns x 4 rows (28 hexes)
BOARD_WIDTH = 7
BOARD_HEIGHT = 4
ALL_POSITIONS = [(x, y) for y in range(BOARD_HEIGHT) for x in range(BOARD_WIDTH)]


@dataclass
class PositionConfig:
    """A specific positioning configuration for a team."""
    positions: Tuple[Tuple[int, int], ...]  # Position for each unit

    def __hash__(self):
        return hash(self.positions)

    def __eq__(self, other):
        return self.positions == other.positions


@dataclass
class EvaluationResult:
    """Result of evaluating a position configuration."""
    config: PositionConfig
    win_rate: float
    avg_damage_dealt: float
    avg_survivors: float
    num_simulations: int

    def __lt__(self, other):
        """Sort by win rate descending."""
        return self.win_rate > other.win_rate


class PositioningOptimizer:
    """
    Finds optimal board positions for a team composition.

    Strategy:
    1. Generate candidate position configurations (sampling or exhaustive)
    2. For each config, run N combat simulations against opponent boards
    3. Rank configurations by win rate
    4. Return best positions
    """

    def __init__(self, engine: CombatEngine = None):
        """Initialize optimizer with a combat engine."""
        self.engine = engine or CombatEngine()

        # Default opponent configurations for evaluation
        self.default_opponents = self._create_default_opponents()

        # Load MetaTFT position data if available
        self.metatft_positions = self._load_metatft_positions()

    def _load_metatft_positions(self) -> Optional[Dict]:
        """Load MetaTFT position heatmap data if available."""
        data_path = Path(__file__).parent.parent / "data" / "metatft_positions.json"
        if data_path.exists():
            try:
                with open(data_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def get_metatft_best_positions(self, champion_id: str, n: int = 5) -> List[Tuple[int, int]]:
        """
        Get the N best positions for a champion from MetaTFT data.

        Returns list of (col, row) tuples sorted by win rate.
        """
        if not self.metatft_positions:
            return []

        champ_data = self.metatft_positions.get(champion_id, {})
        best_positions = champ_data.get('best_positions', [])

        # Convert to tuples if stored as lists
        return [tuple(p) if isinstance(p, list) else p for p in best_positions[:n]]

    def get_metatft_role(self, champion_id: str) -> Optional[str]:
        """Get the MetaTFT-derived role for a champion (frontline/backline/flexible)."""
        if not self.metatft_positions:
            return None

        champ_data = self.metatft_positions.get(champion_id, {})
        return champ_data.get('role')

    def _create_default_opponents(self) -> List[List[Dict]]:
        """
        Create a diverse set of opponent boards for evaluation.

        These represent common board states you might face.
        """
        opponents = []

        # Opponent 1: Frontline + backline (standard)
        opponents.append([
            {'champion': 'TFT16_Leona', 'star': 2, 'items': [], 'position': (1, 0)},
            {'champion': 'TFT16_Leona', 'star': 2, 'items': [], 'position': (5, 0)},
            {'champion': 'TFT16_Draven', 'star': 2, 'items': [], 'position': (3, 3)},
        ])

        # Opponent 2: Corner stack (assassin-style)
        opponents.append([
            {'champion': 'TFT16_Yasuo', 'star': 2, 'items': [], 'position': (0, 3)},
            {'champion': 'TFT16_Yasuo', 'star': 2, 'items': [], 'position': (1, 3)},
            {'champion': 'TFT16_Lux', 'star': 2, 'items': [], 'position': (0, 2)},
        ])

        # Opponent 3: Spread formation
        opponents.append([
            {'champion': 'TFT16_Draven', 'star': 2, 'items': [], 'position': (0, 2)},
            {'champion': 'TFT16_Draven', 'star': 2, 'items': [], 'position': (6, 2)},
            {'champion': 'TFT16_Leona', 'star': 2, 'items': [], 'position': (3, 0)},
        ])

        # Opponent 4: Clumped (AOE bait)
        opponents.append([
            {'champion': 'TFT16_Leona', 'star': 2, 'items': [], 'position': (3, 0)},
            {'champion': 'TFT16_Lux', 'star': 2, 'items': [], 'position': (3, 1)},
            {'champion': 'TFT16_Draven', 'star': 2, 'items': [], 'position': (4, 1)},
        ])

        return opponents

    def generate_positions_exhaustive(self, num_units: int) -> List[PositionConfig]:
        """
        Generate ALL possible position configurations for N units.

        Warning: This grows factorially! Only use for small teams.
        - 3 units: 28 * 27 * 26 = 19,656 configurations
        - 4 units: 28 * 27 * 26 * 25 = 491,400 configurations
        - 5 units: ~12 million configurations
        """
        configs = []
        for positions in itertools.permutations(ALL_POSITIONS, num_units):
            configs.append(PositionConfig(positions=positions))
        return configs

    def generate_positions_sampled(self, num_units: int,
                                   num_samples: int = 1000,
                                   seed: int = None) -> List[PositionConfig]:
        """
        Generate a random sample of position configurations.

        More efficient for larger teams.
        """
        if seed is not None:
            random.seed(seed)

        configs = set()
        attempts = 0
        max_attempts = num_samples * 10

        while len(configs) < num_samples and attempts < max_attempts:
            positions = tuple(random.sample(ALL_POSITIONS, num_units))
            configs.add(PositionConfig(positions=positions))
            attempts += 1

        return list(configs)

    def classify_unit_role(self, champion_id: str) -> str:
        """
        Classify a unit as 'frontline', 'backline', or 'flexible'.

        Based on traits, range, and HP.
        """
        champ_data = self.engine.champions.get(champion_id, {})
        traits = champ_data.get('traits', [])
        stats = champ_data.get('stats', {})
        range_val = stats.get('range', 1)
        hp = stats.get('hp', 600)

        # Frontline traits (tanks)
        frontline_traits = {'Defender', 'Bruiser', 'Warden', 'Juggernaut', 'Colossus', 'Bastion'}

        # Backline traits (carries/mages)
        backline_traits = {'Gunslinger', 'Longshot', 'Arcanist', 'Invoker', 'Star Forger',
                          'Sorcerer', 'Eternal', 'Sage', 'Disruptor', 'Emperor'}

        # Check traits
        has_frontline = any(t in frontline_traits for t in traits)
        has_backline = any(t in backline_traits for t in traits)

        if has_frontline and not has_backline:
            return 'frontline'
        if has_backline and not has_frontline:
            return 'backline'

        # Fall back to range + HP
        if range_val <= 1:
            return 'frontline'
        elif range_val >= 4:
            return 'backline'
        elif hp >= 900:  # Tanky unit
            return 'frontline'
        else:
            return 'flexible'

    def _get_adjacent_positions(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all adjacent hex positions (6 neighbors in hex grid)."""
        x, y = pos
        # Hex grid adjacency depends on row parity
        if y % 2 == 0:  # Even row
            neighbors = [
                (x-1, y), (x+1, y),      # Left, Right
                (x-1, y-1), (x, y-1),    # Bottom-left, Bottom-right
                (x-1, y+1), (x, y+1),    # Top-left, Top-right
            ]
        else:  # Odd row
            neighbors = [
                (x-1, y), (x+1, y),      # Left, Right
                (x, y-1), (x+1, y-1),    # Bottom-left, Bottom-right
                (x, y+1), (x+1, y+1),    # Top-left, Top-right
            ]
        return [(nx, ny) for nx, ny in neighbors
                if 0 <= nx < BOARD_WIDTH and 0 <= ny < BOARD_HEIGHT]

    def _is_spread(self, positions: List[Tuple[int, int]]) -> bool:
        """Check if no units are adjacent to each other."""
        pos_set = set(positions)
        for pos in positions:
            for adj in self._get_adjacent_positions(pos):
                if adj in pos_set:
                    return False
        return True

    def generate_solo_tank_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'solo tank' configurations.

        Strategy: Put the tankiest unit alone in front row, everyone else in back 2 rows.
        This forces enemies to focus on the tank while carries deal damage safely.
        """
        configs = set()
        num_units = len(comp)

        # Find the tankiest unit (highest HP with frontline traits)
        tank_indices = []
        for i, unit_def in enumerate(comp):
            role = self.classify_unit_role(unit_def['champion'])
            if role == 'frontline':
                champ_data = self.engine.champions.get(unit_def['champion'], {})
                hp = champ_data.get('stats', {}).get('hp', 0)
                tank_indices.append((i, hp))

        # Sort by HP descending
        tank_indices.sort(key=lambda x: -x[1])

        if not tank_indices:
            return []  # No tanks found

        # Front row positions (row 0)
        front_row = [(x, 0) for x in range(BOARD_WIDTH)]
        # Back positions (rows 2-3)
        back_positions = [(x, y) for y in [2, 3] for x in range(BOARD_WIDTH)]

        for _ in range(num_samples):
            positions = [None] * num_units

            # Place the main tank in front row (center preferred)
            main_tank_idx = tank_indices[0][0]
            tank_pos = random.choice(front_row)
            positions[main_tank_idx] = tank_pos

            # Place everyone else in back
            available_back = [p for p in back_positions]
            random.shuffle(available_back)

            back_idx = 0
            for i in range(num_units):
                if positions[i] is None:
                    if back_idx < len(available_back):
                        positions[i] = available_back[back_idx]
                        back_idx += 1
                    else:
                        # Fallback if we run out of back positions
                        remaining = [p for p in ALL_POSITIONS if p not in positions]
                        positions[i] = random.choice(remaining) if remaining else (0, 0)

            if None not in positions:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_spread_configs(self, num_units: int, num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'spread' configurations (anti-AOE).

        Strategy: No units adjacent to each other. Like zone defense in basketball.
        Counters AOE abilities and clumped-targeting spells.
        """
        configs = set()
        attempts = 0
        max_attempts = num_samples * 50  # Spread is harder to generate

        while len(configs) < num_samples and attempts < max_attempts:
            positions = []
            available = list(ALL_POSITIONS)
            random.shuffle(available)

            for _ in range(num_units):
                # Find positions that aren't adjacent to any placed unit
                valid = []
                for pos in available:
                    adjacent_to_existing = False
                    for placed in positions:
                        if pos in self._get_adjacent_positions(placed):
                            adjacent_to_existing = True
                            break
                    if not adjacent_to_existing:
                        valid.append(pos)

                if valid:
                    pos = random.choice(valid)
                    positions.append(pos)
                    available.remove(pos)
                else:
                    break  # Can't place more units without adjacency

            if len(positions) == num_units and self._is_spread(positions):
                configs.add(PositionConfig(positions=tuple(positions)))

            attempts += 1

        return list(configs)

    def generate_corner_stack_configs(self, num_units: int, num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'corner stack' configurations.

        Strategy: All units clumped in one corner. Used for:
        - Assassin protection (they jump to opposite corner)
        - Clumped buff synergies
        - Forcing enemy pathing
        """
        configs = set()

        # Define corner regions (3x3 areas in each corner)
        corners = {
            'bottom_left': [(x, y) for x in range(3) for y in range(2)],
            'bottom_right': [(x, y) for x in range(4, 7) for y in range(2)],
            'top_left': [(x, y) for x in range(3) for y in range(2, 4)],
            'top_right': [(x, y) for x in range(4, 7) for y in range(2, 4)],
        }

        samples_per_corner = max(1, num_samples // 4)

        for corner_name, corner_positions in corners.items():
            if len(corner_positions) < num_units:
                continue  # Skip if corner can't fit all units

            for _ in range(samples_per_corner):
                positions = tuple(random.sample(corner_positions, num_units))
                configs.add(PositionConfig(positions=positions))

        return list(configs)

    def generate_diagonal_configs(self, num_units: int, num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate diagonal line configurations.

        Strategy: Units on diagonals to control enemy pathing and spread damage.
        """
        configs = set()

        # Diagonal patterns (bottom-left to top-right)
        diagonals = [
            [(0, 0), (1, 1), (2, 2), (3, 3)],
            [(1, 0), (2, 1), (3, 2), (4, 3)],
            [(2, 0), (3, 1), (4, 2), (5, 3)],
            [(3, 0), (4, 1), (5, 2), (6, 3)],
            # Reverse diagonals
            [(6, 0), (5, 1), (4, 2), (3, 3)],
            [(5, 0), (4, 1), (3, 2), (2, 3)],
        ]

        for _ in range(num_samples):
            # Pick a random diagonal and fill from it
            diag = random.choice(diagonals)
            positions = []
            available = list(ALL_POSITIONS)

            # Start with diagonal positions
            for pos in diag:
                if len(positions) < num_units and pos in available:
                    positions.append(pos)
                    available.remove(pos)

            # Fill remaining from nearby positions
            while len(positions) < num_units and available:
                pos = random.choice(available)
                positions.append(pos)
                available.remove(pos)

            if len(positions) == num_units:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_bait_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'bait' configurations.

        Strategy: Put a weak/sacrificial unit in front corner to pull enemy aggro,
        while the real carry is protected in the opposite corner.
        """
        configs = set()
        num_units = len(comp)

        # Find weakest unit (lowest HP non-carry) and main carry (highest cost backline)
        unit_info = []
        for i, unit_def in enumerate(comp):
            role = self.classify_unit_role(unit_def['champion'])
            champ_data = self.engine.champions.get(unit_def['champion'], {})
            hp = champ_data.get('stats', {}).get('hp', 0)
            cost = champ_data.get('cost', 1)
            unit_info.append({'idx': i, 'role': role, 'hp': hp, 'cost': cost})

        # Find bait (lowest HP) and carry (highest cost backline)
        bait_candidates = sorted(unit_info, key=lambda x: x['hp'])
        carry_candidates = sorted([u for u in unit_info if u['role'] == 'backline'],
                                  key=lambda x: -x['cost'])

        if not bait_candidates or not carry_candidates:
            return []

        bait_idx = bait_candidates[0]['idx']
        carry_idx = carry_candidates[0]['idx']

        # Bait positions (front corners)
        bait_positions = [(0, 0), (6, 0), (0, 1), (6, 1)]
        # Carry positions (back corners, opposite side)
        carry_positions_map = {
            (0, 0): [(5, 3), (6, 3), (6, 2)],
            (6, 0): [(0, 3), (1, 3), (0, 2)],
            (0, 1): [(5, 3), (6, 3), (6, 2)],
            (6, 1): [(0, 3), (1, 3), (0, 2)],
        }

        for _ in range(num_samples):
            positions = [None] * num_units

            # Place bait
            bait_pos = random.choice(bait_positions)
            positions[bait_idx] = bait_pos

            # Place carry in opposite corner
            carry_options = carry_positions_map.get(bait_pos, [(3, 3)])
            positions[carry_idx] = random.choice(carry_options)

            # Place remaining units in back rows, away from bait
            back_positions = [(x, y) for y in [2, 3] for x in range(BOARD_WIDTH)]
            available = [p for p in back_positions if p not in positions]
            random.shuffle(available)

            idx = 0
            for i in range(num_units):
                if positions[i] is None:
                    if idx < len(available):
                        positions[i] = available[idx]
                        idx += 1
                    else:
                        remaining = [p for p in ALL_POSITIONS if p not in positions]
                        positions[i] = random.choice(remaining) if remaining else (3, 2)

            if None not in positions:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_anti_zephyr_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'anti-Zephyr' configurations.

        Strategy: Keep main carry away from common Zephyr positions (corners, front-center).
        Zephyr typically targets: front corners, backline corners, or highest AS unit.
        Put decoy/tank in Zephyr bait positions, carry in unpredictable spots.
        """
        configs = set()
        num_units = len(comp)

        # Common Zephyr target positions (where enemies typically aim)
        zephyr_bait_positions = [
            (0, 0), (6, 0),  # Front corners (most common)
            (0, 3), (6, 3),  # Back corners
            (3, 0),          # Front center
        ]

        # Safe positions (less commonly Zephyred)
        safe_carry_positions = [
            (2, 3), (4, 3),  # Back row but not corners
            (1, 2), (5, 2),  # Mid-back, off-center
            (3, 2),          # Center back
        ]

        # Find carry (highest cost backline) and a tank for bait
        unit_info = []
        for i, unit_def in enumerate(comp):
            role = self.classify_unit_role(unit_def['champion'])
            champ_data = self.engine.champions.get(unit_def['champion'], {})
            cost = champ_data.get('cost', 1)
            hp = champ_data.get('stats', {}).get('hp', 0)
            unit_info.append({'idx': i, 'role': role, 'cost': cost, 'hp': hp})

        carry_candidates = sorted([u for u in unit_info if u['role'] == 'backline'],
                                  key=lambda x: -x['cost'])
        tank_candidates = sorted([u for u in unit_info if u['role'] == 'frontline'],
                                 key=lambda x: -x['hp'])

        if not carry_candidates:
            return []

        carry_idx = carry_candidates[0]['idx']
        tank_idx = tank_candidates[0]['idx'] if tank_candidates else None

        for _ in range(num_samples):
            positions = [None] * num_units

            # Place carry in safe position
            positions[carry_idx] = random.choice(safe_carry_positions)

            # Place tank in Zephyr bait position if we have one
            if tank_idx is not None:
                available_bait = [p for p in zephyr_bait_positions if p != positions[carry_idx]]
                if available_bait:
                    positions[tank_idx] = random.choice(available_bait)

            # Fill remaining positions
            all_used = [p for p in positions if p is not None]
            available = [p for p in ALL_POSITIONS if p not in all_used]
            random.shuffle(available)

            idx = 0
            for i in range(num_units):
                if positions[i] is None:
                    if idx < len(available):
                        positions[i] = available[idx]
                        idx += 1

            if None not in positions:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_clump_for_buffs_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'clump for buffs' configurations.

        Strategy: Group carries together to benefit from item auras (Locket, Zeke's, Chalice).
        Place buff-holder adjacent to multiple carries.
        Also good for: Protector trait, Warden aura, etc.
        """
        configs = set()
        num_units = len(comp)

        # Find carries and support units
        unit_info = []
        for i, unit_def in enumerate(comp):
            role = self.classify_unit_role(unit_def['champion'])
            champ_data = self.engine.champions.get(unit_def['champion'], {})
            cost = champ_data.get('cost', 1)
            unit_info.append({'idx': i, 'role': role, 'cost': cost})

        carries = sorted([u for u in unit_info if u['role'] == 'backline'],
                        key=lambda x: -x['cost'])
        tanks = [u for u in unit_info if u['role'] == 'frontline']

        if len(carries) < 2:
            return []

        # Clump positions (adjacent hexes in back rows)
        clump_centers = [
            [(2, 3), (3, 3), (2, 2), (3, 2)],  # Left-center back
            [(4, 3), (5, 3), (4, 2), (5, 2)],  # Right-center back
            [(3, 3), (4, 3), (3, 2), (4, 2)],  # Center back
        ]

        for _ in range(num_samples):
            positions = [None] * num_units

            # Pick a clump area
            clump = random.choice(clump_centers)

            # Place carries in clump
            clump_positions = list(clump)
            random.shuffle(clump_positions)

            for i, carry in enumerate(carries[:len(clump_positions)]):
                positions[carry['idx']] = clump_positions[i]

            # Place tanks in front
            front_positions = [(x, 0) for x in range(BOARD_WIDTH)]
            random.shuffle(front_positions)

            for i, tank in enumerate(tanks[:len(front_positions)]):
                if positions[tank['idx']] is None:
                    positions[tank['idx']] = front_positions[i]

            # Fill remaining
            all_used = [p for p in positions if p is not None]
            available = [p for p in ALL_POSITIONS if p not in all_used]
            random.shuffle(available)

            idx = 0
            for i in range(num_units):
                if positions[i] is None and idx < len(available):
                    positions[i] = available[idx]
                    idx += 1

            if None not in positions:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_v_shape_frontline_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'V-shape frontline' configurations.

        Strategy: Tanks form a V shape to funnel enemies toward a kill zone.
        Enemies path around the V point, grouping up for AOE.
        """
        configs = set()
        num_units = len(comp)

        # V-shape patterns (point facing enemy)
        v_patterns = [
            # V pointing forward (enemies funnel to center)
            {'tanks': [(3, 0), (2, 1), (4, 1)], 'carries': [(2, 3), (3, 3), (4, 3)]},
            # Wide V
            {'tanks': [(3, 0), (1, 1), (5, 1)], 'carries': [(2, 3), (3, 3), (4, 3)]},
            # Offset V left
            {'tanks': [(2, 0), (1, 1), (3, 1)], 'carries': [(4, 3), (5, 3), (6, 3)]},
            # Offset V right
            {'tanks': [(4, 0), (3, 1), (5, 1)], 'carries': [(0, 3), (1, 3), (2, 3)]},
        ]

        unit_info = []
        for i, unit_def in enumerate(comp):
            role = self.classify_unit_role(unit_def['champion'])
            unit_info.append({'idx': i, 'role': role})

        tanks = [u['idx'] for u in unit_info if u['role'] == 'frontline']
        carries = [u['idx'] for u in unit_info if u['role'] == 'backline']

        for _ in range(num_samples):
            positions = [None] * num_units

            pattern = random.choice(v_patterns)

            # Place tanks in V
            tank_spots = list(pattern['tanks'])
            random.shuffle(tank_spots)
            for i, tank_idx in enumerate(tanks[:len(tank_spots)]):
                positions[tank_idx] = tank_spots[i]

            # Place carries in back
            carry_spots = list(pattern['carries'])
            random.shuffle(carry_spots)
            for i, carry_idx in enumerate(carries[:len(carry_spots)]):
                positions[carry_idx] = carry_spots[i]

            # Fill remaining
            all_used = [p for p in positions if p is not None]
            available = [p for p in ALL_POSITIONS if p not in all_used]
            random.shuffle(available)

            idx = 0
            for i in range(num_units):
                if positions[i] is None and idx < len(available):
                    positions[i] = available[idx]
                    idx += 1

            if None not in positions:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_split_carry_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate 'split carry' configurations.

        Strategy: Put two carries on opposite sides of the board.
        Counters single-target burst (assassins target one, other survives).
        Also forces enemies to split attention.
        """
        configs = set()
        num_units = len(comp)

        unit_info = []
        for i, unit_def in enumerate(comp):
            role = self.classify_unit_role(unit_def['champion'])
            champ_data = self.engine.champions.get(unit_def['champion'], {})
            cost = champ_data.get('cost', 1)
            unit_info.append({'idx': i, 'role': role, 'cost': cost})

        carries = sorted([u for u in unit_info if u['role'] == 'backline'],
                        key=lambda x: -x['cost'])

        if len(carries) < 2:
            return []

        # Split positions (opposite corners/sides)
        split_pairs = [
            ((0, 3), (6, 3)),   # Back corners
            ((0, 2), (6, 2)),   # Mid-back sides
            ((1, 3), (5, 3)),   # Near-corner back
        ]

        for _ in range(num_samples):
            positions = [None] * num_units

            # Place top 2 carries on opposite sides
            pair = random.choice(split_pairs)
            positions[carries[0]['idx']] = pair[0]
            positions[carries[1]['idx']] = pair[1]

            # Fill remaining
            all_used = [p for p in positions if p is not None]
            available = [p for p in ALL_POSITIONS if p not in all_used]
            random.shuffle(available)

            idx = 0
            for i in range(num_units):
                if positions[i] is None and idx < len(available):
                    positions[i] = available[idx]
                    idx += 1

            if None not in positions:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_metatft_guided_configs(self, comp: List[Dict], num_samples: int = 100) -> List[PositionConfig]:
        """
        Generate configurations guided by MetaTFT real-world positioning data.

        Strategy: Use the highest win-rate positions from actual high-elo games
        for each champion. This leverages community-discovered optimal positions.
        """
        if not self.metatft_positions:
            return []

        configs = set()
        num_units = len(comp)

        # Get best positions for each champion from MetaTFT data
        unit_best_positions = []
        for unit_def in comp:
            champion_id = unit_def['champion']
            best_pos = self.get_metatft_best_positions(champion_id, n=8)  # Get top 8 positions
            if best_pos:
                unit_best_positions.append(best_pos)
            else:
                # Fall back to role-based positions
                role = self.classify_unit_role(champion_id)
                if role == 'frontline':
                    unit_best_positions.append([(x, y) for y in [0, 1] for x in range(BOARD_WIDTH)])
                elif role == 'backline':
                    unit_best_positions.append([(x, y) for y in [2, 3] for x in range(BOARD_WIDTH)])
                else:
                    unit_best_positions.append(list(ALL_POSITIONS))

        for _ in range(num_samples):
            positions = []
            used_positions = set()

            for i in range(num_units):
                # Get available positions from this unit's preferred positions
                candidates = [p for p in unit_best_positions[i] if p not in used_positions]

                if not candidates:
                    # Fall back to any available position
                    candidates = [p for p in ALL_POSITIONS if p not in used_positions]

                if candidates:
                    # Weight selection toward better positions (first in list = higher win rate)
                    weights = [1.0 / (j + 1) for j in range(len(candidates))]
                    pos = random.choices(candidates, weights=weights[:len(candidates)])[0]
                    positions.append(pos)
                    used_positions.add(pos)
                else:
                    break

            if len(positions) == num_units:
                configs.add(PositionConfig(positions=tuple(positions)))

        return list(configs)

    def generate_positions_strategic(self, num_units: int,
                                     num_samples: int = 500,
                                     comp: List[Dict] = None) -> List[PositionConfig]:
        """
        Generate position configurations using multiple strategic approaches.

        Combines conventional and unconventional strategies:
        - Standard (tanks front, carries back)
        - Solo tank (1 tank front, rest back)
        - Spread (anti-AOE, no adjacent units)
        - Corner stack (clumped in corner)
        - Diagonal lines
        - Bait positioning
        - Anti-Zephyr (carry in unpredictable positions)
        - Clump for buffs (group carries for item auras)
        - V-shape frontline (funnel enemies)
        - Split carry (carries on opposite sides)
        - MetaTFT-guided (real-world high-elo positioning data)
        """
        configs = set()

        # Allocate samples across strategies
        if comp:
            # Check if MetaTFT data is available
            has_metatft = self.metatft_positions is not None

            if has_metatft:
                # With MetaTFT data, give it priority
                samples_metatft = int(num_samples * 0.20)        # 20% MetaTFT-guided
                samples_standard = int(num_samples * 0.18)       # 18% standard
                samples_solo_tank = int(num_samples * 0.08)      # 8% solo tank
                samples_spread = int(num_samples * 0.08)         # 8% spread
                samples_corner = int(num_samples * 0.06)         # 6% corner
                samples_diagonal = int(num_samples * 0.06)       # 6% diagonal
                samples_bait = int(num_samples * 0.07)           # 7% bait
                samples_anti_zephyr = int(num_samples * 0.07)    # 7% anti-zephyr
                samples_clump = int(num_samples * 0.07)          # 7% clump for buffs
                samples_v_shape = int(num_samples * 0.07)        # 7% V-shape
                samples_split = int(num_samples * 0.06)          # 6% split carry
            else:
                # Without MetaTFT, use original distribution
                samples_metatft = 0
                samples_standard = int(num_samples * 0.25)       # 25% standard
                samples_solo_tank = int(num_samples * 0.10)      # 10% solo tank
                samples_spread = int(num_samples * 0.10)         # 10% spread
                samples_corner = int(num_samples * 0.08)         # 8% corner
                samples_diagonal = int(num_samples * 0.07)       # 7% diagonal
                samples_bait = int(num_samples * 0.08)           # 8% bait
                samples_anti_zephyr = int(num_samples * 0.08)    # 8% anti-zephyr
                samples_clump = int(num_samples * 0.08)          # 8% clump for buffs
                samples_v_shape = int(num_samples * 0.08)        # 8% V-shape
                samples_split = int(num_samples * 0.08)          # 8% split carry
        else:
            # Without comp, skip role-dependent strategies
            samples_metatft = 0
            samples_standard = int(num_samples * 0.4)
            samples_solo_tank = 0
            samples_spread = int(num_samples * 0.2)
            samples_corner = int(num_samples * 0.15)
            samples_diagonal = int(num_samples * 0.15)
            samples_bait = 0
            samples_anti_zephyr = 0
            samples_clump = 0
            samples_v_shape = 0
            samples_split = int(num_samples * 0.1)

        # Generate MetaTFT-guided configs (highest priority if available)
        if comp and samples_metatft > 0:
            configs.update(self.generate_metatft_guided_configs(comp, samples_metatft))

        # Generate standard configs (tanks front, carries back)
        configs.update(self._generate_standard_configs(num_units, samples_standard, comp))

        # Generate unconventional configs
        if comp and samples_solo_tank > 0:
            configs.update(self.generate_solo_tank_configs(comp, samples_solo_tank))

        if samples_spread > 0:
            configs.update(self.generate_spread_configs(num_units, samples_spread))

        if samples_corner > 0:
            configs.update(self.generate_corner_stack_configs(num_units, samples_corner))

        if samples_diagonal > 0:
            configs.update(self.generate_diagonal_configs(num_units, samples_diagonal))

        if comp and samples_bait > 0:
            configs.update(self.generate_bait_configs(comp, samples_bait))

        if comp and samples_anti_zephyr > 0:
            configs.update(self.generate_anti_zephyr_configs(comp, samples_anti_zephyr))

        if comp and samples_clump > 0:
            configs.update(self.generate_clump_for_buffs_configs(comp, samples_clump))

        if comp and samples_v_shape > 0:
            configs.update(self.generate_v_shape_frontline_configs(comp, samples_v_shape))

        if comp and samples_split > 0:
            configs.update(self.generate_split_carry_configs(comp, samples_split))

        return list(configs)

    def _generate_standard_configs(self, num_units: int, num_samples: int,
                                   comp: List[Dict] = None) -> set:
        """Generate standard tank-front, carry-back configurations."""
        configs = set()

        # Define position rows
        front_rows = [(x, 0) for x in range(BOARD_WIDTH)] + [(x, 1) for x in range(BOARD_WIDTH)]
        back_rows = [(x, 3) for x in range(BOARD_WIDTH)] + [(x, 2) for x in range(BOARD_WIDTH)]

        # Classify units if comp provided
        unit_roles = []
        if comp:
            for unit_def in comp:
                role = self.classify_unit_role(unit_def['champion'])
                unit_roles.append(role)

        for _ in range(num_samples):
            positions = []
            available = list(ALL_POSITIONS)

            for i in range(num_units):
                if unit_roles and i < len(unit_roles):
                    role = unit_roles[i]
                    if role == 'frontline':
                        candidates = [p for p in front_rows if p in available]
                        if not candidates or random.random() < 0.1:
                            candidates = available
                    elif role == 'backline':
                        candidates = [p for p in back_rows if p in available]
                        if not candidates or random.random() < 0.1:
                            candidates = available
                    else:
                        candidates = available
                else:
                    if i < num_units // 2 and random.random() < 0.6:
                        candidates = [p for p in front_rows if p in available]
                    elif random.random() < 0.6:
                        candidates = [p for p in back_rows if p in available]
                    else:
                        candidates = available

                if not candidates:
                    candidates = available

                pos = random.choice(candidates)
                positions.append(pos)
                available.remove(pos)

            configs.add(PositionConfig(positions=tuple(positions)))

        return configs

    def _create_team(self, comp: List[Dict], positions: PositionConfig,
                     team_id: int) -> List[Unit]:
        """Create a list of Unit objects from comp definition and positions."""
        units = []
        for i, unit_def in enumerate(comp):
            pos = positions.positions[i]
            unit = self.engine.create_unit(
                api_name=unit_def['champion'],
                star_level=unit_def.get('star', 1),
                team=team_id,
                position=pos,
                items=unit_def.get('items', [])
            )
            if unit:
                units.append(unit)
        return units

    def _create_opponent_team(self, opponent_def: List[Dict], team_id: int) -> List[Unit]:
        """Create opponent team from definition."""
        units = []
        for unit_def in opponent_def:
            unit = self.engine.create_unit(
                api_name=unit_def['champion'],
                star_level=unit_def.get('star', 1),
                team=team_id,
                position=unit_def['position'],
                items=unit_def.get('items', [])
            )
            if unit:
                units.append(unit)
        return units

    def evaluate_config(self, comp: List[Dict], config: PositionConfig,
                       opponents: List[List[Dict]] = None,
                       sims_per_opponent: int = 10,
                       seed: int = None) -> EvaluationResult:
        """
        Evaluate a single position configuration.

        Runs combat simulations against each opponent board and aggregates results.
        """
        opponents = opponents or self.default_opponents

        total_wins = 0
        total_damage = 0
        total_survivors = 0
        total_sims = 0

        for opp_idx, opponent_def in enumerate(opponents):
            for sim_idx in range(sims_per_opponent):
                # Create teams
                my_team = self._create_team(comp, config, team_id=0)
                opp_team = self._create_opponent_team(opponent_def, team_id=1)

                # Calculate seed for this specific simulation
                sim_seed = None
                if seed is not None:
                    sim_seed = seed + opp_idx * sims_per_opponent + sim_idx

                # Run combat
                result = self.engine.run_combat(
                    my_team, opp_team,
                    verbose=False,
                    seed=sim_seed
                )

                # Aggregate results
                if result['winner'] == 0:
                    total_wins += 1
                total_damage += result['total_damage_dealt']['team0']
                total_survivors += result['team0_survivors']
                total_sims += 1

        return EvaluationResult(
            config=config,
            win_rate=total_wins / total_sims if total_sims > 0 else 0,
            avg_damage_dealt=total_damage / total_sims if total_sims > 0 else 0,
            avg_survivors=total_survivors / total_sims if total_sims > 0 else 0,
            num_simulations=total_sims
        )

    def optimize(self, comp: List[Dict],
                 opponents: List[List[Dict]] = None,
                 strategy: str = 'strategic',
                 num_configs: int = 500,
                 sims_per_opponent: int = 10,
                 seed: int = None,
                 verbose: bool = True) -> Dict:
        """
        Find optimal positions for a team composition.

        Args:
            comp: List of unit definitions with champion, star, items
            opponents: List of opponent board configurations (or use defaults)
            strategy: 'exhaustive', 'sampled', or 'strategic'
            num_configs: Number of configurations to evaluate (for sampled/strategic)
            sims_per_opponent: Simulations per opponent board
            seed: Random seed for reproducibility
            verbose: Print progress

        Returns:
            Dict with best_positions, all_results, and statistics
        """
        num_units = len(comp)

        if verbose:
            print(f"Optimizing positions for {num_units} units...")
            print(f"Strategy: {strategy}, Configs: {num_configs}, Sims/opponent: {sims_per_opponent}")

        # Generate position configurations
        if strategy == 'exhaustive':
            if num_units > 4:
                print(f"Warning: Exhaustive search with {num_units} units is very slow!")
            configs = self.generate_positions_exhaustive(num_units)
            if verbose:
                print(f"Generated {len(configs)} exhaustive configurations")
        elif strategy == 'sampled':
            configs = self.generate_positions_sampled(num_units, num_configs, seed)
            if verbose:
                print(f"Generated {len(configs)} sampled configurations")
        else:  # strategic
            configs = self.generate_positions_strategic(num_units, num_configs, comp=comp)
            if verbose:
                print(f"Generated {len(configs)} strategic configurations")

        # Evaluate each configuration
        results = []
        for i, config in enumerate(configs):
            if verbose and (i + 1) % 100 == 0:
                print(f"  Evaluated {i + 1}/{len(configs)} configurations...")

            eval_result = self.evaluate_config(
                comp, config,
                opponents=opponents,
                sims_per_opponent=sims_per_opponent,
                seed=seed
            )
            results.append(eval_result)

        # Sort by win rate
        results.sort()

        # Extract best result
        best = results[0]

        # Format positions for output
        best_positions = {}
        for i, unit_def in enumerate(comp):
            pos = best.config.positions[i]
            best_positions[unit_def['champion']] = {
                'position': pos,
                'row': pos[1],
                'col': pos[0]
            }

        if verbose:
            print(f"\nBest configuration:")
            print(f"  Win rate: {best.win_rate:.1%}")
            print(f"  Avg damage: {best.avg_damage_dealt:.0f}")
            print(f"  Avg survivors: {best.avg_survivors:.2f}")
            print(f"\nPositions:")
            for champ, pos_info in best_positions.items():
                print(f"  {champ}: col={pos_info['col']}, row={pos_info['row']}")

        return {
            'best_positions': best_positions,
            'best_result': {
                'win_rate': best.win_rate,
                'avg_damage': best.avg_damage_dealt,
                'avg_survivors': best.avg_survivors,
                'positions': best.config.positions
            },
            'all_results': results[:100],  # Top 100 results
            'statistics': {
                'configs_evaluated': len(configs),
                'total_simulations': sum(r.num_simulations for r in results),
                'win_rate_range': (results[-1].win_rate, results[0].win_rate),
                'avg_win_rate': sum(r.win_rate for r in results) / len(results)
            }
        }

    def visualize_board(self, positions: Dict[str, Dict],
                        title: str = "Board Position") -> str:
        """
        Create ASCII visualization of board positions.

        Args:
            positions: Dict mapping champion names to position info
            title: Title for the visualization

        Returns:
            ASCII string representation
        """
        # Create empty board
        board = [['.  ' for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]

        # Place units
        for champ, pos_info in positions.items():
            col, row = pos_info['col'], pos_info['row']
            # Use first 3 chars of champion name (strip TFT16_ prefix)
            name = champ.replace('TFT16_', '')[:3]
            board[row][col] = f'{name}'

        # Build output
        lines = [title, '=' * 30]
        lines.append('    ' + '  '.join(str(i) for i in range(BOARD_WIDTH)))
        lines.append('   ' + '-' * 22)

        for row_idx in range(BOARD_HEIGHT - 1, -1, -1):  # Top to bottom
            row_str = f'{row_idx} | ' + ' '.join(f'{cell:3}' for cell in board[row_idx])
            lines.append(row_str)

        lines.append('')
        lines.append('Legend: Row 0 = front, Row 3 = back')

        return '\n'.join(lines)


def demo():
    """Demonstrate positioning optimizer."""
    print("=" * 60)
    print("TFT Positioning Optimizer Demo")
    print("=" * 60)
    print()

    optimizer = PositioningOptimizer()

    # Define a sample comp
    comp = [
        {'champion': 'TFT16_Leona', 'star': 2, 'items': []},      # Tank
        {'champion': 'TFT16_Draven', 'star': 2, 'items': []},     # Carry
        {'champion': 'TFT16_Lux', 'star': 2, 'items': []},        # Support
    ]

    print("Comp:")
    for unit in comp:
        print(f"  - {unit['champion']} ({unit['star']}*)")
    print()

    # Run optimization
    result = optimizer.optimize(
        comp,
        strategy='strategic',
        num_configs=200,
        sims_per_opponent=5,
        seed=42,
        verbose=True
    )

    # Visualize result
    print()
    print(optimizer.visualize_board(result['best_positions'], "Optimal Positions"))

    # Show top 5 configurations
    print()
    print("Top 5 Configurations:")
    print("-" * 50)
    for i, res in enumerate(result['all_results'][:5]):
        positions_str = ', '.join(f'({p[0]},{p[1]})' for p in res.config.positions)
        print(f"{i+1}. Win rate: {res.win_rate:.1%} - Positions: {positions_str}")

    return result


if __name__ == "__main__":
    demo()
