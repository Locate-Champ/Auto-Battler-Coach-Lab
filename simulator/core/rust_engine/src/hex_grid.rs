/// Hex grid math for the TFT board.
///
/// The board is a 4-row x 7-column offset hex grid (odd-q layout).
/// Odd columns are shifted down by 0.5 hexes.
///
/// Performance: Uses precomputed lookup tables for distance and neighbors
/// to avoid cube-coordinate conversion in hot paths.
use crate::types::HexPos;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};
use std::sync::OnceLock;

pub const BOARD_ROWS: i32 = 4;
pub const BOARD_COLS: i32 = 7;
const NUM_HEXES: usize = (BOARD_ROWS * BOARD_COLS) as usize; // 28

/// Flat index into the board: row * BOARD_COLS + col.
#[inline(always)]
fn flat_idx(pos: HexPos) -> usize {
    (pos.0 * BOARD_COLS + pos.1) as usize
}

/// Precomputed lookup tables built once at first access.
struct HexLuts {
    /// distance_lut[flat(a)][flat(b)] = hex distance
    distance: [[i32; NUM_HEXES]; NUM_HEXES],
    /// neighbors[flat(pos)] = list of valid neighbor positions
    neighbors: [Vec<HexPos>; NUM_HEXES],
}

static HEX_LUTS: OnceLock<HexLuts> = OnceLock::new();

fn build_luts() -> HexLuts {
    let mut distance = [[0i32; NUM_HEXES]; NUM_HEXES];
    // Initialize neighbors array
    let neighbors: [Vec<HexPos>; NUM_HEXES] = std::array::from_fn(|_| Vec::new());
    let mut luts = HexLuts { distance, neighbors };

    let even_dirs: [(i32, i32); 6] = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 0), (-1, -1)];
    let odd_dirs: [(i32, i32); 6] = [(0, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)];

    for r in 0..BOARD_ROWS {
        for c in 0..BOARD_COLS {
            let idx = flat_idx((r, c));

            // Neighbors
            let dirs = if (c & 1) == 1 { &odd_dirs } else { &even_dirs };
            let mut nbrs = Vec::with_capacity(6);
            for &(dr, dc) in dirs {
                let nr = r + dr;
                let nc = c + dc;
                if nr >= 0 && nr < BOARD_ROWS && nc >= 0 && nc < BOARD_COLS {
                    nbrs.push((nr, nc));
                }
            }
            luts.neighbors[idx] = nbrs;

            // Distances (cube coordinates)
            let x1 = c;
            let z1 = r - (c - (c & 1)) / 2;
            let y1 = -x1 - z1;
            for r2 in 0..BOARD_ROWS {
                for c2 in 0..BOARD_COLS {
                    let x2 = c2;
                    let z2 = r2 - (c2 - (c2 & 1)) / 2;
                    let y2 = -x2 - z2;
                    luts.distance[idx][flat_idx((r2, c2))] =
                        ((x1 - x2).abs() + (y1 - y2).abs() + (z1 - z2).abs()) / 2;
                }
            }
        }
    }
    luts
}

#[inline(always)]
fn luts() -> &'static HexLuts {
    HEX_LUTS.get_or_init(build_luts)
}

/// Hex distance between two positions (precomputed LUT).
#[inline]
pub fn hex_distance(a: HexPos, b: HexPos) -> i32 {
    luts().distance[flat_idx(a)][flat_idx(b)]
}

/// Get the 6 hex neighbors of a position (precomputed LUT).
#[inline]
pub fn hex_neighbors(pos: HexPos) -> &'static [HexPos] {
    &luts().neighbors[flat_idx(pos)]
}

/// A* pathfinding on the hex grid, avoiding occupied hexes.
/// Returns the next step toward `goal` (not the full path).
/// Returns None if no path exists or already at goal.
pub fn find_next_step(
    start: HexPos,
    goal: HexPos,
    occupied: &std::collections::HashSet<HexPos>,
) -> Option<HexPos> {
    if start == goal {
        return None;
    }

    // Check if goal is a neighbor (fast path)
    if hex_neighbors(start).contains(&goal) && !occupied.contains(&goal) {
        return Some(goal);
    }

    // A* search
    #[derive(Debug)]
    struct Node {
        pos: HexPos,
        g_cost: i32,
        f_cost: i32,
    }

    impl PartialEq for Node {
        fn eq(&self, other: &Self) -> bool {
            self.f_cost == other.f_cost
        }
    }
    impl Eq for Node {}
    impl PartialOrd for Node {
        fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
            Some(self.cmp(other))
        }
    }
    impl Ord for Node {
        fn cmp(&self, other: &Self) -> Ordering {
            other.f_cost.cmp(&self.f_cost) // Min-heap
        }
    }

    let mut open = BinaryHeap::new();
    let mut came_from: HashMap<HexPos, HexPos> = HashMap::new();
    let mut g_score: HashMap<HexPos, i32> = HashMap::new();

    g_score.insert(start, 0);
    open.push(Node {
        pos: start,
        g_cost: 0,
        f_cost: hex_distance(start, goal),
    });

    while let Some(current) = open.pop() {
        if current.pos == goal {
            // Reconstruct path back to first step
            let mut step = goal;
            while let Some(&prev) = came_from.get(&step) {
                if prev == start {
                    return Some(step);
                }
                step = prev;
            }
            return Some(step);
        }

        let current_g = g_score[&current.pos];

        for &neighbor in hex_neighbors(current.pos) {
            // Can move to the goal hex or any unoccupied hex
            if neighbor != goal && occupied.contains(&neighbor) {
                continue;
            }

            let tentative_g = current_g + 1;
            if tentative_g < *g_score.get(&neighbor).unwrap_or(&i32::MAX) {
                came_from.insert(neighbor, current.pos);
                g_score.insert(neighbor, tentative_g);
                open.push(Node {
                    pos: neighbor,
                    g_cost: tentative_g,
                    f_cost: tentative_g + hex_distance(neighbor, goal),
                });
            }
        }
    }

    // No path found - try to move to the closest unoccupied neighbor to goal
    let mut best_neighbor = None;
    let mut best_dist = i32::MAX;
    for &neighbor in hex_neighbors(start) {
        if !occupied.contains(&neighbor) {
            let dist = hex_distance(neighbor, goal);
            if dist < best_dist {
                best_dist = dist;
                best_neighbor = Some(neighbor);
            }
        }
    }
    best_neighbor
}

/// Check if position is within the board bounds.
#[inline]
pub fn is_valid_pos(pos: HexPos) -> bool {
    pos.0 >= 0 && pos.0 < BOARD_ROWS && pos.1 >= 0 && pos.1 < BOARD_COLS
}

#[cfg(test)]
mod tests {
    use super::*;

    fn expected_python_neighbors(pos: HexPos) -> Vec<HexPos> {
        let even_col = [(0, -1), (1, -1), (1, 0), (0, 1), (-1, 0), (-1, -1)];
        let odd_col = [(0, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)];
        let (row, col) = pos;
        let dirs = if (col & 1) == 1 { odd_col } else { even_col };
        let mut out = Vec::with_capacity(6);
        for (dr, dc) in dirs {
            let nr = row + dr;
            let nc = col + dc;
            if nr >= 0 && nr < BOARD_ROWS && nc >= 0 && nc < BOARD_COLS {
                out.push((nr, nc));
            }
        }
        out
    }

    fn expected_python_distance(a: HexPos, b: HexPos) -> i32 {
        let (r1, c1) = a;
        let (r2, c2) = b;
        let x1 = c1;
        let z1 = r1 - (c1 - (c1 & 1)) / 2;
        let y1 = -x1 - z1;
        let x2 = c2;
        let z2 = r2 - (c2 - (c2 & 1)) / 2;
        let y2 = -x2 - z2;
        ((x1 - x2).abs() + (y1 - y2).abs() + (z1 - z2).abs()) / 2
    }

    #[test]
    fn test_hex_distance_same() {
        assert_eq!(hex_distance((0, 0), (0, 0)), 0);
    }

    #[test]
    fn test_hex_distance_adjacent() {
        assert_eq!(hex_distance((0, 0), (0, 1)), 1);
        assert_eq!(hex_distance((0, 0), (1, 0)), 1);
    }

    #[test]
    fn test_hex_distance_across_board() {
        // Corner to corner
        let dist = hex_distance((0, 0), (3, 6));
        assert!(dist > 0);
        assert!(dist <= 9);
    }

    #[test]
    fn test_neighbors_corner() {
        let n = hex_neighbors((0, 0));
        assert!(n.len() >= 2 && n.len() <= 3);
        for &(r, c) in n {
            assert!(is_valid_pos((r, c)));
        }
    }

    #[test]
    fn test_neighbors_center() {
        let n = hex_neighbors((1, 3));
        assert_eq!(n.len(), 6);
    }

    #[test]
    fn test_neighbors_even_col_match_python_order() {
        let n = hex_neighbors((1, 2));
        assert_eq!(n, &[(1, 1), (2, 1), (2, 2), (1, 3), (0, 2), (0, 1)]);
    }

    #[test]
    fn test_neighbors_odd_col_match_python_order() {
        let n = hex_neighbors((1, 3));
        assert_eq!(n, &[(1, 2), (2, 3), (2, 4), (1, 4), (0, 4), (0, 3)]);
    }

    #[test]
    fn test_neighbors_parity_against_python_for_all_board_positions() {
        for row in 0..BOARD_ROWS {
            for col in 0..BOARD_COLS {
                let pos = (row, col);
                assert_eq!(hex_neighbors(pos), expected_python_neighbors(pos).as_slice());
            }
        }
    }

    #[test]
    fn test_distance_parity_against_python_for_all_board_pairs() {
        for row_a in 0..BOARD_ROWS {
            for col_a in 0..BOARD_COLS {
                for row_b in 0..BOARD_ROWS {
                    for col_b in 0..BOARD_COLS {
                        let a = (row_a, col_a);
                        let b = (row_b, col_b);
                        assert_eq!(hex_distance(a, b), expected_python_distance(a, b));
                    }
                }
            }
        }
    }

    #[test]
    fn test_pathfinding_direct() {
        let occupied = std::collections::HashSet::new();
        let step = find_next_step((0, 0), (0, 1), &occupied);
        assert_eq!(step, Some((0, 1)));
    }

    #[test]
    fn test_pathfinding_around_obstacle() {
        let mut occupied = std::collections::HashSet::new();
        occupied.insert((0, 1));
        let step = find_next_step((0, 0), (0, 2), &occupied);
        assert!(step.is_some());
        assert_ne!(step, Some((0, 1))); // Should route around
    }
}
