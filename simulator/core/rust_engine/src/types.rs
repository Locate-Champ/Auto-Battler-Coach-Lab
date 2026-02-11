/// Core enumerations and type aliases for the TFT combat engine.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DamageType {
    Physical,
    Magic,
    True,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UnitState {
    Idle,
    Moving,
    Attacking,
    Casting,
    Stunned,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AbilityType {
    Damage,
    AoeDamage,
    Buff,
    Debuff,
    Summon,
    Dash,
    Heal,
    Shield,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TargetingType {
    Nearest,
    LowestHp,
    LowestHpPercent,
    HighestHp,
    Farthest,
    Random,
    CurrentTarget,
    MostEnemiesInRange,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CcType {
    Stunned,
    Feared,
    Taunted,
    Rooted,
}

/// Index into the engine's unit arena (Vec<Unit>).
pub type UnitId = usize;

/// Hex position as (row, col) on the 4x7 board.
pub type HexPos = (i32, i32);
