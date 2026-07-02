"""Hex grid geometry: distance calculations and pathfinding."""

import heapq
from typing import Dict, List, Optional, Tuple


class HexGrid:
    """Hex grid utilities for TFT board (4 rows x 7 cols).

    Performance: Uses precomputed lookup tables for distance and neighbors
    to avoid repeated cube-coordinate conversions in the hot path.
    """

    ROWS = 4
    COLS = 7

    # Hex directions for odd-q offset coordinates
    DIRECTIONS_EVEN = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 0), (-1, -1)]
    DIRECTIONS_ODD = [(0, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]

    # --- Precomputed lookup tables (built once at module load) ---

    # _DISTANCE_LUT[(r1,c1)][(r2,c2)] = hex distance
    _DISTANCE_LUT: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = {}

    # _NEIGHBOR_LUT[(r,c)] = list of valid neighbor positions
    _NEIGHBOR_LUT: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}

    # _HEXES_IN_RANGE_LUT[(r,c)][radius] = list of hexes within radius
    _HEXES_IN_RANGE_LUT: Dict[Tuple[int, int], Dict[int, List[Tuple[int, int]]]] = {}

    @classmethod
    def _build_luts(cls):
        """Build all lookup tables once. Called at module load."""
        if cls._DISTANCE_LUT:
            return  # Already built

        all_hexes = [(r, c) for r in range(cls.ROWS) for c in range(cls.COLS)]

        # Build neighbor LUT
        for pos in all_hexes:
            row, col = pos
            directions = cls.DIRECTIONS_ODD if col % 2 == 1 else cls.DIRECTIONS_EVEN
            neighbors = []
            for dr, dc in directions:
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < cls.ROWS and 0 <= new_col < cls.COLS:
                    neighbors.append((new_row, new_col))
            cls._NEIGHBOR_LUT[pos] = neighbors

        # Build distance LUT using cube-coordinate conversion
        for pos1 in all_hexes:
            cls._DISTANCE_LUT[pos1] = {}
            r1, c1 = pos1
            x1 = c1
            z1 = r1 - (c1 - (c1 & 1)) // 2
            y1 = -x1 - z1
            for pos2 in all_hexes:
                r2, c2 = pos2
                x2 = c2
                z2 = r2 - (c2 - (c2 & 1)) // 2
                y2 = -x2 - z2
                cls._DISTANCE_LUT[pos1][pos2] = (abs(x1 - x2) + abs(y1 - y2) + abs(z1 - z2)) // 2

        # Build hexes-in-range LUT for common radii (0-6 covers entire board)
        for pos in all_hexes:
            cls._HEXES_IN_RANGE_LUT[pos] = {}
            for radius in range(7):
                cls._HEXES_IN_RANGE_LUT[pos][radius] = [
                    p for p in all_hexes if cls._DISTANCE_LUT[pos][p] <= radius
                ]

    @staticmethod
    def get_neighbors(pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Get all valid neighboring hexes (from precomputed LUT)."""
        return HexGrid._NEIGHBOR_LUT[pos]

    @staticmethod
    def hex_distance(pos1: Tuple[int, int], pos2: Tuple[int, int]) -> int:
        """Calculate distance between two hexes (from precomputed LUT)."""
        return HexGrid._DISTANCE_LUT[pos1][pos2]

    @staticmethod
    def find_path(
        start: Tuple[int, int], goal: Tuple[int, int], occupied: set
    ) -> List[Tuple[int, int]]:
        """A* pathfinding on hex grid."""
        if start == goal:
            return []

        dist_lut = HexGrid._DISTANCE_LUT
        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}
        f_score = {start: dist_lut[start][goal]}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]

            for neighbor in HexGrid._NEIGHBOR_LUT[current]:
                if neighbor in occupied and neighbor != goal:
                    continue

                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + dist_lut[neighbor][goal]
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []  # No path found

    @staticmethod
    def find_best_step(
        start: Tuple[int, int], goal: Tuple[int, int], occupied: set
    ) -> Optional[Tuple[int, int]]:
        """Find the single best next step toward goal, avoiding occupied hexes.

        Greedy neighbor selection -- much cheaper than full A* for the common
        case where the path is short and unobstructed. Falls back to A* only
        when all neighbors are blocked.
        """
        dist_lut = HexGrid._DISTANCE_LUT
        best_pos = None
        best_dist = dist_lut[start][goal]

        for neighbor in HexGrid._NEIGHBOR_LUT[start]:
            if neighbor in occupied and neighbor != goal:
                continue
            d = dist_lut[neighbor][goal]
            if d < best_dist:
                best_dist = d
                best_pos = neighbor

        if best_pos is not None:
            return best_pos

        # All direct neighbors blocked -- fall back to A*
        path = HexGrid.find_path(start, goal, occupied)
        return path[0] if path else None

    @staticmethod
    def get_hexes_in_range(center: Tuple[int, int], radius: int) -> List[Tuple[int, int]]:
        """Get all hexes within radius of center (from precomputed LUT)."""
        lut = HexGrid._HEXES_IN_RANGE_LUT.get(center)
        if lut and radius in lut:
            return lut[radius]
        # Fallback for out-of-range radius
        return [
            (r, c)
            for r in range(HexGrid.ROWS)
            for c in range(HexGrid.COLS)
            if HexGrid._DISTANCE_LUT[center][(r, c)] <= radius
        ]


# Build lookup tables at module load time
HexGrid._build_luts()
