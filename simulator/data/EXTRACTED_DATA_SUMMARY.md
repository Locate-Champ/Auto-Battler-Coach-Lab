# TFT Set 16 Extracted Data Summary

## Data Sources

### 1. CommunityDragon API (Primary - Complete)
**File:** `wad_extraction/cdragon_tft_en_us.json` (21 MB)
**Extracted:** `wad_extraction/set16_champions.json` (274 KB)

Contains:
- **103 Set 16 Champions** with complete data:
  - Base stats (HP, AD, AS, Armor, MR, Range, Mana, Crit)
  - Ability descriptions and damage values at 1/2/3 star
  - Traits and roles
- **53 Set 16 Traits** with breakpoint effects

### 2. WAD File Extractions

#### TFTSet16.wad.client (89 MB) → Already Extracted
**Location:** `wad_extraction/extracted/TFTSet16/` and `wad_extraction/json/TFTSet16/`

Contains:
- Animation data (attack animations, spell animations)
- Skin configurations
- Frame event data (mStartFrame values)
- ~400 BIN files converted to JSON

**Useful for:**
- Animation frame timing references
- Visual effect timing

#### Scripts.wad.client (4.9 MB) → Extracted
**Location:** `wad_extraction/extracted_wads/Scripts/`

Contains:
- Compiled Lua scripts (.luabin64) - NOT readable
- .preload files showing script dependencies
- Per-champion ability scripts (TFT16_xxx)

**Limitation:** Scripts are compiled bytecode, not human-readable.

#### DATA.wad.client (54 MB) → Extracted
**Location:** `wad_extraction/extracted_wads/DATA/`

Contains:
- Bot AI scripts (.dat files) - Binary, not useful
- Configuration files (input, settings)
- Per-champion bot behavior

**Not useful for combat simulation.**

### 3. Not Yet Extracted (Potentially Useful)

| File | Size | Potential Value |
|------|------|-----------------|
| Global.wad.client | 888 MB | May contain damage formulas, game constants |
| TFTSetTutorial.wad.client | 49 MB | Tutorial timing examples |

## Key Data Files for Simulator

### Champion Stats & Abilities
```
simulator/wad_extraction/set16_champions.json
```
Contains all 103 champions with:
- Base stats at 1-star
- Ability damage scaling (1/2/3 star values)
- Traits, cost, range, role

### Timing Data (Previously Built)
```
simulator/data/timing_constants.json
```
Contains:
- Attack windup estimates
- Wiki-sourced missile speeds
- Animation frame references from WAD extraction

### Wiki Timing Data
```
simulator/calibration/wiki_timing_data.json
```
Contains League Wiki data for 12 ranged champions:
- Windup percentages
- Missile speeds
- Base attack speeds

## What's Missing (Needs Manual Measurement)

1. **Attack Animation Timing** - Most TFT champions don't have explicit frame events in WAD files
2. **Spell Cast Times** - Not in extracted data
3. **Projectile Travel Times** - Partial from Wiki, needs measurement for TFT-specific

## Damage Formula (Standard TFT)

```python
# Physical Damage
physical_damage = base_damage * (1 + bonus_ad) * damage_amp
final_damage = physical_damage * (100 / (100 + armor))

# Magic Damage
magic_damage = base_damage * (1 + ap/100) * damage_amp
final_damage = magic_damage * (100 / (100 + magic_resist))

# Critical Strike
if random() < crit_chance:
    final_damage *= crit_multiplier  # Default 1.4x (140%)
```

## Star Level Scaling

```python
# HP Scaling
hp_2star = hp_1star * 1.8
hp_3star = hp_1star * 3.24  # 1.8^2

# AD Scaling
ad_2star = ad_1star * 1.5
ad_3star = ad_1star * 2.25  # 1.5^2

# Ability Damage - Use values from set16_champions.json ability.variables
```

## Next Steps

1. Use `set16_champions.json` as primary data source
2. Merge with `timing_constants.json` for timing data
3. Use YouTube measurement tool for missing attack timings
4. Build combat simulator using extracted stats
