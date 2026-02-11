/// Hex grid math for the TFT board.
///
/// The board is a 4-row x 7-column offset hex grid (odd-r layout).
/// Odd rows are shifted right by 0.5 hexes.
use crate::types::HexPos;
use std::cmp::Ordering;
use std::collections::{BinaryHeap, HashMap};

pub const BOARD_ROWS: i32 = 4;
pub const BOARD_COLS: i32 = 7;

/// Convert offset coordinates (row, col) to cube coordinates (q, r, s).
#[inline]
fn offset_to_cube(pos: HexPos) -> (i32, i32, i32) {
    let (row, col) = pos;
    let q = col - (row - (row & 1)) / 2;
    let r = row;
    let s = -q - r;
    (q, r, s)
}

/// Hex distance between two positions using cube coordinates.
#[inline]
pub fn hex_distance(a: HexPos, b: HexPos) -> i32 {
    let (q1, r1, s1) = offset_to_cube(a);
    let (q2, r2, s2) = offset_to_cube(b);
    ((q1 - q2).abs() + (r1 - r2).abs() + (s1 - s2).abs()) / 2
}

/// Get the 6 hex neighbors of a position (filtered to valid board positions).
pub fn hex_neighbors(pos: HexPos) -> Vec<HexPos> {
    let (row, col) = pos;
    let is_odd_row = (row & 1) == 1;

    // Offset hex neighbor directions differ for even/odd rows
    let directions: [(i32, i32); 6] = if is_odd_row {
        [
            (-1, 0),
            (-1, 1), // upper-left, upper-right
            (0, -1),
            (0, 1), // left, right
            (1, 0),
            (1, 1), // lower-left, lower-right
        ]
    } else {
        [
            (-1, -1),
            (-1, 0), // upper-left, upper-right
            (0, -1),
            (0, 1), // left, right
            (1, -1),
            (1, 0), // lower-left, lower-right
        ]
    };

    let mut neighbors = Vec::with_capacity(6);
    for (dr, dc) in directions {
        let nr = row + dr;
        let nc = col + dc;
        if nr >= 0 && nr < BOARD_ROWS && nc >= 0 && nc < BOARD_COLS {
            neighbors.push((nr, nc));
        }
    }
    neighbors
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
    let neighbors = hex_neighbors(start);
    if neighbors.contains(&goal) && !occupied.contains(&goal) {
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

        for neighbor in hex_neighbors(current.pos) {
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
    for neighbor in hex_neighbors(start) {
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
        for (r, c) in &n {
            assert!(is_valid_pos((*r, *c)));
        }
    }

    #[test]
    fn test_neighbors_center() {
        let n = hex_neighbors((1, 3));
        assert_eq!(n.len(), 6);
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
