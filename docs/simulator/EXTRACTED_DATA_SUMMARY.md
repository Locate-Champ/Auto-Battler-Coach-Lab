# TFT Set 16 Extracted Data Summary

## Status (What Is And Isn't Stored In Git)

This repo intentionally does not store Riot `.wad.client` binaries or extracted WAD asset trees (too large for git).
If you need to work with WADs locally, do it out-of-repo and only commit small, derived artifacts after review.

## Data Sources (In-Repo)

Champion stats and abilities:
- `simulator/data/combat_data.json`

Traits:
- `simulator/data/traits.json`

Timing constants:
- `simulator/data/timing_constants.json`

Wiki timing reference inputs (partial):
- `simulator/calibration/wiki_timing_data.json`

## Optional Local WAD Extraction (Out-Of-Repo)

If you need to regenerate timing/frame reference data from WADs, do it in a separate local folder (not committed).
Only commit the small derived outputs (like `simulator/data/timing_constants.json`) once reviewed.

## What's Missing (Needs Manual Measurement)

1. **Attack Animation Timing** - Most TFT champions don't have explicit frame events available via stable, small artifacts.
2. **Spell Cast Times** - Not consistently available in extracted data.
3. **Projectile Travel Times** - Partial from Wiki; needs TFT-specific measurement.

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

# Ability Damage
# Use values from simulator/data/combat_data.json ability.variables
```
