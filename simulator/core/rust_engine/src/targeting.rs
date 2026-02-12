use crate::hex_grid;
/// Target selection logic for the TFT combat engine.
use crate::python_rng::PyRng;
use crate::types::*;
use crate::unit::Unit;

/// Find the best target for a unit from a list of enemy indices.
pub fn find_target(
    unit_idx: UnitId,
    units: &[Unit],
    enemy_indices: &[UnitId],
    rng: &mut PyRng,
) -> Option<UnitId> {
    let unit = &units[unit_idx];

    // If taunted, must attack taunt source
    if let Some(CcType::Taunted) = unit.cc_type {
        if let Some(taunt_src) = unit.taunt_source {
            if units[taunt_src].is_alive {
                return Some(taunt_src);
            }
        }
    }

    // Filter valid targets
    let valid_enemies: Vec<UnitId> = enemy_indices
        .iter()
        .copied()
        .filter(|&idx| {
            let enemy = &units[idx];
            enemy.is_alive && enemy.is_targetable
        })
        .collect();

    if valid_enemies.is_empty() {
        return None;
    }

    let targeting = unit
        .ability
        .as_ref()
        .map(|a| a.targeting)
        .unwrap_or(TargetingType::Nearest);

    // For auto-attacks, always use nearest (targeting type is for abilities)
    match targeting {
        TargetingType::CurrentTarget => {
            // Keep current target if valid
            if let Some(target_idx) = unit.target_idx {
                if units[target_idx].is_alive && units[target_idx].is_targetable {
                    return Some(target_idx);
                }
            }
            // Fall through to nearest
            find_nearest(unit, &valid_enemies, units)
        }
        TargetingType::Nearest => find_nearest(unit, &valid_enemies, units),
        TargetingType::LowestHp => find_lowest_hp(units, &valid_enemies),
        TargetingType::LowestHpPercent => find_lowest_hp_percent(units, &valid_enemies),
        TargetingType::HighestHp => find_highest_hp(units, &valid_enemies),
        TargetingType::Farthest => find_farthest(unit, &valid_enemies, units),
        TargetingType::Random => find_random(&valid_enemies, rng),
        TargetingType::MostEnemiesInRange => {
            find_most_enemies_in_range(unit, &valid_enemies, units)
        }
    }
}

/// Find the nearest enemy (with tie-breaking for closest to center).
fn find_nearest(unit: &Unit, enemies: &[UnitId], units: &[Unit]) -> Option<UnitId> {
    let mut min_dist = i32::MAX;
    let mut distances: Vec<(UnitId, i32)> = Vec::with_capacity(enemies.len());

    for &idx in enemies {
        let dist = hex_grid::hex_distance(unit.position, units[idx].position);
        distances.push((idx, dist));
        if dist < min_dist {
            min_dist = dist;
        }
    }

    if distances.is_empty() {
        return None;
    }

    let mut frontline_best: Option<UnitId> = None;
    let mut frontline_best_dist = i32::MAX;
    for (idx, dist) in distances.iter().copied() {
        if dist > min_dist + 1 {
            continue;
        }
        if !is_frontline(&units[idx]) {
            continue;
        }
        if dist < frontline_best_dist {
            frontline_best_dist = dist;
            frontline_best = Some(idx);
        }
    }
    if frontline_best.is_some() {
        return frontline_best;
    }

    let mut closest_idx: Option<UnitId> = None;
    let mut closest_dist = i32::MAX;
    for (idx, dist) in distances.iter().copied() {
        if dist < closest_dist {
            closest_dist = dist;
            closest_idx = Some(idx);
        }
    }
    closest_idx
}

fn is_frontline(unit: &Unit) -> bool {
    unit.role.contains("Tank") || unit.role.contains("Fighter")
}

fn find_lowest_hp(units: &[Unit], enemies: &[UnitId]) -> Option<UnitId> {
    enemies.iter().copied().min_by(|&a, &b| {
        units[a]
            .stats
            .hp
            .partial_cmp(&units[b].stats.hp)
            .unwrap_or(std::cmp::Ordering::Equal)
    })
}

fn find_lowest_hp_percent(units: &[Unit], enemies: &[UnitId]) -> Option<UnitId> {
    enemies.iter().copied().min_by(|&a, &b| {
        let pct_a = if units[a].stats.max_hp > 0.0 {
            units[a].stats.hp / units[a].stats.max_hp
        } else {
            1.0
        };
        let pct_b = if units[b].stats.max_hp > 0.0 {
            units[b].stats.hp / units[b].stats.max_hp
        } else {
            1.0
        };
        pct_a
            .partial_cmp(&pct_b)
            .unwrap_or(std::cmp::Ordering::Equal)
    })
}

fn find_highest_hp(units: &[Unit], enemies: &[UnitId]) -> Option<UnitId> {
    enemies.iter().copied().max_by(|&a, &b| {
        units[a]
            .stats
            .hp
            .partial_cmp(&units[b].stats.hp)
            .unwrap_or(std::cmp::Ordering::Equal)
    })
}

fn find_farthest(unit: &Unit, enemies: &[UnitId], units: &[Unit]) -> Option<UnitId> {
    let mut best_idx = None;
    let mut best_dist = -1;

    for &idx in enemies {
        let dist = hex_grid::hex_distance(unit.position, units[idx].position);
        if dist > best_dist {
            best_dist = dist;
            best_idx = Some(idx);
        }
    }
    best_idx
}

fn find_random(enemies: &[UnitId], rng: &mut PyRng) -> Option<UnitId> {
    if enemies.is_empty() {
        return None;
    }
    let idx = rng.randbelow(enemies.len());
    Some(enemies[idx])
}

fn find_most_enemies_in_range(unit: &Unit, enemies: &[UnitId], units: &[Unit]) -> Option<UnitId> {
    // Find the enemy whose position has the most other enemies within 1 hex
    let mut best_idx = None;
    let mut best_count = 0;

    for &idx in enemies {
        let pos = units[idx].position;
        let count: usize = enemies
            .iter()
            .filter(|&&other_idx| {
                other_idx != idx && hex_grid::hex_distance(pos, units[other_idx].position) <= 1
            })
            .count()
            + 1; // Include the target itself

        if count > best_count
            || (count == best_count
                && best_idx.map_or(true, |bi: UnitId| {
                    hex_grid::hex_distance(unit.position, pos)
                        < hex_grid::hex_distance(unit.position, units[bi].position)
                }))
        {
            best_count = count;
            best_idx = Some(idx);
        }
    }
    best_idx
}

/// Get all enemies within a given hex range of a position.
pub fn get_enemies_in_range(
    center: HexPos,
    range: i32,
    enemy_indices: &[UnitId],
    units: &[Unit],
) -> Vec<UnitId> {
    enemy_indices
        .iter()
        .copied()
        .filter(|&idx| {
            let enemy = &units[idx];
            enemy.is_alive && hex_grid::hex_distance(center, enemy.position) <= range
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::unit::{CombatStats, Unit};

    fn make_unit(role: &str, position: HexPos, team: i32) -> Unit {
        let mut stats = CombatStats::default();
        stats.hp = 1000.0;
        stats.max_hp = 1000.0;
        Unit::new(
            role.to_string(),
            format!("TFT16_{role}"),
            1,
            1,
            role.to_string(),
            stats.clone(),
            stats,
            position,
            team,
        )
    }

    #[test]
    fn test_nearest_prefers_frontline_within_plus_one() {
        let attacker = make_unit("ADCarry", (0, 0), 0);
        let backline = make_unit("APCaster", (0, 1), 1); // dist=1
        let frontline = make_unit("Tank", (1, 1), 1); // dist=2 (within min+1)
        let units = vec![attacker, backline, frontline];
        let enemies = vec![1_usize, 2_usize];

        let target = find_nearest(&units[0], &enemies, &units);
        assert_eq!(target, Some(2));
    }

    #[test]
    fn test_nearest_uses_closest_when_no_frontline() {
        let attacker = make_unit("ADCarry", (0, 0), 0);
        let mage = make_unit("APCaster", (0, 1), 1); // dist=1
        let specialist = make_unit("Specialist", (1, 1), 1); // dist=2
        let units = vec![attacker, mage, specialist];
        let enemies = vec![1_usize, 2_usize];

        let target = find_nearest(&units[0], &enemies, &units);
        assert_eq!(target, Some(1));
    }
}
