# TFT Combat Simulator - Remaining Work

This document outlines what still needs to be implemented in the combat simulator.

---

## Recently Completed

### Augment System (2026-02-02)
**Status:** ✅ IMPLEMENTED

The combat simulator now supports augments with the `AugmentManager` class.

**Features:**
- 284 augments loaded from Set 16 data
- 131 combat-relevant augments categorized and functional
- Team-wide stat buffs (45 augments)
- Hex-based effects (8 augments)
- Event-triggered augments (13 augments)
- Item-conditional augments (15 augments)

**Usage:**
```python
engine = CombatEngine()

# 1v1 with augments
result = engine.simulate_1v1(
    'TFT16_Draven', 'TFT16_Leona',
    star1=2, star2=2,
    augments1=["Darkwill's Invasion"],  # +10% damage amp
    num_simulations=100
)

# Team combat with augments
result = engine.run_combat(
    team0, team1,
    team0_augments=["Darkwill's Invasion", "Defense of the Placidium"],
    team1_augments=["Chaos Magic"]
)
```

**Key augments tested:**
- `Darkwill's Invasion` - +10% Damage Amp (15% with Noxus active)
- `Defense of the Placidium` - +8% Durability (12% with Ionia active)
- `U.R.F` - +15% Attack Speed for Spatula holders

**Test file:** `UnitTests/test_augments.py`

---

## High Priority - Complex Mechanics

### 1. Lucian → Senna Transition
**What it does:** Lucian channels for 3s, then transforms into Senna who continues the fight.
**Implementation notes:**
- Need to track channel state
- On channel complete, replace Lucian unit with Senna unit
- Senna inherits position, items, and partial stats
- Channel can be interrupted

**Location:** Add `_cast_luciansenna` handler in `champion_abilities.py`

### 2. Shadow Isles Soul Collection
**What it does:** Shared trait mechanic. When enemies die, Shadow Isles units collect souls.
**Affected champions:**
- Thresh: `HealthDrainPerSoul` - drains more HP per soul
- Gwen: `SnipPerSoulBreakpoint` - extra snips at soul thresholds
- Kalista: `SoulsPerSpearBreakpoint` - more spears at thresholds
- Viego: `BaseAttackSpeed` scales with souls

**Soul multipliers:** 1.0x → 1.3x → 1.6x → 1.9x
**Stat bonuses:** 18-33% AD/AP

**Implementation notes:**
- Add `soul_count` tracking to TraitManager
- Hook into death processing to award souls
- Modify each champion's ability to check soul count

### 3. Ryze Trait-Dependent Ability
**What it does:** Ryze's ability changes based on what traits are active on your team.
**25+ trait interactions:**
- Targon: 10% heal
- Yordle: 12% damage reduction
- Bilgewater: 25% explosion damage
- Void: 30% resist ignore
- Shadow Isles: 5% + soul scaling
- Piltover: 40% overcharge
- Demacia: 12% execute
- Freljord: chill + 6% true damage
- Zaun: poison/ticks
- Shurima: coin/component drops
- Noxus/Ionia: damage reduction

**Implementation notes:**
- Check team traits at cast time
- Select ability effect based on highest/most relevant trait
- May need priority system if multiple traits active

### 4. Sylas Trifold Ability Rotation
**What it does:** Sylas rotates between 3 stolen abilities:
1. Jarvan - Stun
2. Garen - Execute
3. Lux - Shield

**Rules:** Cannot cast same ability twice in a row.

**Implementation notes:**
- Track `_sylas_last_ability` index
- Cycle through abilities, skipping last used
- Each ability has different targeting/effects

---

## Medium Priority - Unique Mechanics

### 5. Tahm Kench Glutton Feeding
**What it does:** Tahm Kench can "eat" units to gain permanent stats.
**Stat gains:** Based on unit cost/star level (need wiki data)

**Implementation notes:**
- Need bench/feeding UI interaction (may be out of scope for combat sim)
- Could simulate as pre-combat stat bonus based on "fed units" config

### 6. Galio Bench Mechanic
**What it does:** Galio stays on bench until first Demacia rally, then joins fight.

**Implementation notes:**
- Track Demacia rally event
- On first rally, spawn Galio onto board
- Need to determine spawn position logic

### 7. T-Hex Pilot System
**What it does:** T-Hex strength scales with who is piloting it.

**Implementation notes:**
- Need pilot assignment mechanic
- Scale T-Hex stats based on pilot's stats/cost
- Pilot determines some ability interactions

### 8. Baron Nashor Riftscourge
**What it does:** Baron has Riftscourge trait for Void synergy.
- 10 acid shots per cast
- 3s refresh (0.25s at 3-star!)

**Implementation notes:**
- Implement acid shot targeting
- Add Void rift passive mechanics

---

## Low Priority - Stats-Only Champions

These champions have basic damage working but missing special mechanics:

| Champion | Missing Mechanic |
|----------|-----------------|
| Rift Herald | Durability passive, armor scaling |
| Taric | 90% DR passive (partially done), invuln at 35% |
| Skarner | Armor aura, impale grab physics |
| Xerath | Trait store items at first shop |
| Zilean | Time bomb chaining, double bomb explosion |
| Mel | Mana drain passive, radiant item generation |
| Sett | Walking animation enter/exit |
| Brock | Board-wide seismic passive |

---

## How to Implement a New Champion

1. **Find the champion in `combat_data.json`**
   ```python
   # Look for ability variables
   champ_data = engine.champions.get('TFT16_ChampionName')
   ability_vars = champ_data['ability']['variables']
   ```

2. **Add handler to `champion_abilities.py`**
   ```python
   def _cast_championname(self, unit, enemies, allies, ability_vars):
       """ChampionName - Ability Name: Description."""
       from .combat_engine import DamageType

       # Get variables
       damage = self._get_var(ability_vars, 'Damage', unit.star_level, 100)

       # Implement logic
       target = unit.target or self._find_nearest_enemy(unit, enemies)
       if target:
           self._deal_damage(unit, target, damage + unit.stats.ap,
                            DamageType.MAGIC, "championname_ability")

       unit.stats.mana = 0
       return True
   ```

3. **Test with a 1v1 simulation**
   ```python
   engine = CombatEngine()
   result = engine.simulate_1v1('TFT16_ChampionName', 'TFT16_Dummy',
                                 star1=2, star2=2, num_simulations=100)
   print(result)
   ```

4. **Update `champion_ability_audit.md`** with implementation status

---

## Helper Methods Available

In `ChampionAbilities` class:
- `_get_var(ability_vars, key, star_level, default)` - Get star-scaled value
- `_find_nearest_enemy(unit, enemies)` - Find closest target
- `_find_farthest_enemy(unit, enemies, max_range)` - Find farthest target
- `_find_lowest_hp_enemy(unit, enemies)` - Find execute target
- `_get_enemies_in_radius(center, radius, enemies)` - AOE targeting
- `_dash_to_position(unit, target_pos)` - Movement ability
- `_deal_damage(unit, target, amount, damage_type, source)` - Apply damage
- `_apply_stun(target, duration, source)` - CC application
- `_hex_distance(pos1, pos2)` - Distance calculation

---

## Testing

Run the combat engine demo:
```bash
cd simulator/core
python combat_engine.py
```

This runs several test scenarios including 1v1s, team fights, and item impact tests.

---

*Last updated: 2026-02-02*
