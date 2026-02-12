use crate::hex_grid;
/// Damage calculation, application, and healing for the TFT combat engine.
use crate::python_rng::PyRng;
use crate::types::*;
use crate::unit::Unit;

/// Result of a damage calculation.
pub struct DamageResult {
    pub final_damage: f64,
    pub did_crit: bool,
}

/// Calculate final damage after all modifiers.
pub fn calculate_damage(
    attacker: &Unit,
    defender: &Unit,
    base_damage: f64,
    damage_type: DamageType,
    can_crit: bool,
    is_ability: bool,
    rng: &mut PyRng,
) -> DamageResult {
    let mut damage = base_damage;

    // Apply damage amp (including Longshot per-hex bonus)
    let mut longshot_bonus = 0.0;
    if attacker.longshot_per_hex > 0.0 {
        let distance = hex_grid::hex_distance(attacker.position, defender.position);
        longshot_bonus = attacker.longshot_per_hex * distance as f64;
    }
    damage *= 1.0 + attacker.stats.damage_amp + longshot_bonus;

    // Check for crit
    let mut did_crit = false;
    if can_crit {
        let has_jeweled = attacker.has_jeweled_gauntlet;
        let has_vanquisher_crit = attacker.vanquisher_ability_crit;
        if !is_ability || has_jeweled || has_vanquisher_crit {
            if rng.random() < attacker.stats.crit_chance {
                damage *= attacker.stats.crit_multiplier;
                did_crit = true;
            }
        }
    }

    // Apply resistance reduction
    match damage_type {
        DamageType::Physical => {
            let resist = defender.stats.armor.max(0.0);
            damage *= 100.0 / (100.0 + resist);
        }
        DamageType::Magic => {
            let resist = defender.stats.magic_resist.max(0.0);
            damage *= 100.0 / (100.0 + resist);
        }
        DamageType::True => {} // No mitigation
    }

    // Apply durability (damage reduction)
    if defender.stats.damage_reduction > 0.0 {
        damage *= 1.0 - defender.stats.damage_reduction;
    }

    // Dragonborn aura: allies take 10% less ability damage
    if is_ability && defender.dragonborn_protected {
        damage *= 0.90;
    }

    // Giant Slayer: +15% damage vs tanks (units with >1750 max HP)
    if attacker.has_giant_slayer && defender.stats.max_hp > 1750.0 {
        damage *= 1.15;
    }

    DamageResult {
        final_damage: damage.max(0.0),
        did_crit,
    }
}

/// Apply damage to a unit, handling shields first.
/// Returns (pre_mitigation_damage, post_mitigation_damage) for mana generation.
pub fn apply_damage_to_unit(
    target: &mut Unit,
    damage: f64,
    _damage_type: DamageType,
    _source_name: &str,
) -> (f64, f64) {
    if !target.is_alive || !target.is_targetable || damage <= 0.0 {
        return (0.0, 0.0);
    }

    let mut remaining = damage;

    // Shield absorbs damage first
    if target.stats.shield > 0.0 {
        if target.stats.shield >= remaining {
            target.stats.shield -= remaining;
            return (0.0, 0.0);
        } else {
            remaining -= target.stats.shield;
            target.stats.shield = 0.0;
        }
    }

    // "Pre-mitigation" here mirrors the Python engine: post-shield, pre-HP clamp.
    let pre_mit = remaining;

    // Apply remaining damage to HP
    let actual_hp_damage = remaining.min(target.stats.hp);
    target.stats.hp -= actual_hp_damage;
    target.total_damage_taken += actual_hp_damage;

    // Check death
    if target.stats.hp <= 0.0 {
        target.stats.hp = 0.0;
        target.is_alive = false;
    }

    // Mana on damage taken: 1% pre-mitigation + 3% post-mitigation, capped at 42.5
    let mana_gain = (pre_mit * 0.01 + actual_hp_damage * 0.03).min(42.5);
    target.stats.mana = (target.stats.mana + mana_gain).min(target.stats.max_mana);

    (pre_mit, actual_hp_damage)
}

/// Heal a unit.
pub fn heal_unit(unit: &mut Unit, amount: f64) {
    if !unit.is_alive || amount <= 0.0 {
        return;
    }
    let healed = amount.min(unit.stats.max_hp - unit.stats.hp);
    unit.stats.hp += healed;
    unit.total_healing += healed;
}

/// Apply sunder (armor reduction) to a target.
pub fn apply_sunder(target: &mut Unit, reduction_pct: f64, duration: f64, time: f64, source: &str) {
    let reduction = target.stats.armor * reduction_pct;
    target.stats.armor = (target.stats.armor - reduction).max(0.0);
    target.sunder_stacks.push(crate::unit::ResistReduction {
        reduction,
        expiry: time + duration,
        source: source.to_string(),
    });
}

/// Apply shred (magic resist reduction) to a target.
pub fn apply_shred(target: &mut Unit, reduction_pct: f64, duration: f64, time: f64, source: &str) {
    let reduction = target.stats.magic_resist * reduction_pct;
    target.stats.magic_resist = (target.stats.magic_resist - reduction).max(0.0);
    target.shred_stacks.push(crate::unit::ResistReduction {
        reduction,
        expiry: time + duration,
        source: source.to_string(),
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::unit::CombatStats;

    fn make_unit() -> Unit {
        let mut stats = CombatStats::default();
        stats.hp = 100.0;
        stats.max_hp = 100.0;
        stats.mana = 0.0;
        stats.max_mana = 100.0;
        Unit::new(
            "Dummy".to_string(),
            "TFT16_Dummy".to_string(),
            1,
            1,
            "ADCarry".to_string(),
            stats.clone(),
            stats,
            (0, 0),
            0,
        )
    }

    #[test]
    fn test_apply_damage_shield_and_mana() {
        let mut target = make_unit();
        target.stats.shield = 50.0;

        let (pre_mit, post_mit) =
            apply_damage_to_unit(&mut target, 80.0, DamageType::Physical, "test");

        assert!((pre_mit - 30.0).abs() < 1e-9);
        assert!((post_mit - 30.0).abs() < 1e-9);
        assert!((target.stats.hp - 70.0).abs() < 1e-9);
        assert!((target.stats.mana - 1.2).abs() < 1e-9);
        assert!(target.is_alive);
    }

    #[test]
    fn test_apply_damage_overkill_clamped() {
        let mut target = make_unit();
        let (_, post_mit) = apply_damage_to_unit(&mut target, 500.0, DamageType::Magic, "test");

        assert!((post_mit - 100.0).abs() < 1e-9);
        assert!((target.stats.hp - 0.0).abs() < 1e-9);
        assert!(!target.is_alive);
    }

    #[test]
    fn test_apply_damage_ignores_untargetable_unit() {
        let mut target = make_unit();
        target.is_targetable = false;
        let (pre_mit, post_mit) =
            apply_damage_to_unit(&mut target, 80.0, DamageType::Physical, "test");

        assert!((pre_mit - 0.0).abs() < 1e-9);
        assert!((post_mit - 0.0).abs() < 1e-9);
        assert!((target.stats.hp - 100.0).abs() < 1e-9);
    }
}
