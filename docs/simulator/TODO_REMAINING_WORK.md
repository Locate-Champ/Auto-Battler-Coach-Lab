# TFT Combat Simulator - Remaining Work

This document outlines what still needs to be implemented in the combat simulator.

---

## Progress Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Combat Engine Core | ✅ Complete | `combat_engine.py` - damage, targeting, stats |
| Champion Data | ✅ Complete | `combat_data.json` - all Set 16 champions |
| Champion Abilities | ✅ Complete | 40+ champions with special mechanics |
| Augment System | ✅ Complete | 284 augments, 131 combat-relevant |
| Item Effects | ✅ Complete | Items affect combat stats + on-hit/ability effects |
| Item Optimizer | ✅ Complete | `item_optimizer.py` - best items, builds, distribution |
| Trait Bonuses | ✅ Complete | 10 stat-buffing traits in TraitManager |
| Complex Mechanics | ⚠️ Partial | 4 high-priority, 4 medium-priority remaining |

**Overall: ~80% of combat mechanics implemented**

---

## Recently Completed

### Champion Abilities Module (2026-02-01)
**Status:** ✅ IMPLEMENTED

Created `champion_abilities.py` with 40+ champion-specific ability handlers.

**Implemented Champions:**
- **Excess Damage:** Caitlyn, Lissandra
- **Dashes:** Yasuo, Yone, Vayne, Renekton, Ambessa, LeBlanc, Diana, Loris, Fizz
- **Executes:** Aatrox (15% HP combo), Darius (bleed stacks), Zaahen (22-cast Divine Challenge)
- **Summons:** Annie (Tibbers), Malzahar (voidlings), Wukong (clone)
- **Stacking:** Veigar (permanent AP), Draven (gold), Seraphine (crystals), Aurelion Sol (stardust)
- **Synergies:** Yasuo+Yone, Diana+Leona
- **Line Abilities:** Lux (line laser w/ 200 width), Seraphine (big cast), Yunara (piercing)
- **Zone Effects:** Kindred (2-hex radius shield zone), Fiddlesticks (fear + mana drain)
- **Special:** Zaahen (Immortal resurrection), Warwick (single cast), Taric (invuln threshold)

**Core Mechanics Added:**
- Target retargeting when current target dies
- Untargetable state (Fizz, Edge of Night, Zhonya's)
- Immortal trait (Zaahen resurrection at 60% HP)
- Form swapping (Kai'Sa, Jinx)

**Session log:** `SESSION_LOG_2026-02-01.md`

---

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

### Trait System Implementation (2026-02-02)
**Status:** ✅ IMPLEMENTED

Added 10 stat-buffing traits to TraitManager that auto-apply at combat start.

**Fixed trait naming:** Converted from backend API names (e.g., `TFT16_Sorcerer`) to display names (e.g., `Arcanist`).

| Trait | Effect |
|-------|--------|
| Arcanist | Team +18/25/40 AP, Arcanists +25/40/60 bonus |
| Defender | Team +12 armor/MR, Defenders +30/55/80 bonus |
| Bruiser | Team +150 HP, Bruisers +25/45/65% HP |
| Slayer | +22/33/44% AD, +10/16/20% omnivamp |
| Juggernaut | +18/20/26% durability |
| Invoker | Team +1 mana regen, Invokers +25/40% mana |
| Vanquisher | +15-30% crit chance/damage, abilities can crit |
| Longshot | +18-32% damage amp + per-hex bonus |
| Quickstriker | Team +15% AS, scaling AS based on target HP |
| Gunslinger | +20/35% AD, 4th attack bonus damage |
| Warden | Shield triggers at 75%/25% HP |

**Commits:**
- `6dc40889` - Implement AugmentManager for combat simulation augments
- `e62d7bd2` - Fix trait names to use display names instead of backend API names
- `335940bc` - Fix augments_set16.json to use display trait names
- `575f0e7c` - Implement 10 stat-buffing traits in TraitManager

**Branch:** `claude/review-session-progress-EAYdf`

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

---

## Quick Stats

- **Champions with abilities:** 40+ of ~55 total
- **Traits implemented:** 10 stat-buffing traits
- **Augments functional:** 131 combat-relevant
- **Item effects:** 20+ items with on-hit/ability/damage effects
- **Core mechanics:** All basic combat working
- **Remaining complex mechanics:** 8 (4 high priority, 4 medium priority)

---

## Phase 1: Validation (Before ML Training)

Before using the simulator as a "factory" for training data, it must be validated as a "scientific instrument."

### Completed (2026-02-02)
- [x] **Benchmark script** - `simulator/benchmark.py` measures throughput
- [x] **Determinism tests** - Verify same seed produces identical outcomes
- [x] **Seed parameter** - Added `seed` param to `run_combat()` and `simulate_1v1()`

### Completed (2026-02-02)
- [x] **Run benchmark** - Determinism verified ✅
- [x] **Fix any determinism failures** - All tests passing

### Still Needed
- [ ] **Integer tick mode** (optional) - Convert float time to integer ticks for precision

### How to Run Validation
```bash
cd simulator
python benchmark.py
```

Expected output:
- 1v1 throughput: X sims/sec
- Team combat throughput: X sims/sec
- Determinism: ✅ PASS or ❌ FAIL

---

## Phase 2: Positioning Optimization (Completed 2026-02-02)

**Goal:** Given a comp (units with items), find optimal board positions.

### Completed
- [x] **PositioningOptimizer class** - `core/positioning_optimizer.py`
- [x] **Position enumeration strategies** - exhaustive, sampled, strategic
- [x] **Evaluation function** - Win rate vs diverse opponent configurations
- [x] **CLI interface** - `position_search.py`
- [x] **Role-aware positioning** - Auto-classifies tanks/carries based on traits and stats
- [x] **Level/cost validation** - Validates unit costs vs player level
- [x] **Real meta comp testing** - Tested with MetaTFT comps (Piltover/Seraphine, Diana/Targon)
- [x] **Unconventional strategies** - Solo tank, spread, corner stack, diagonal, bait

### Features
- **3 generation strategies:**
  - `exhaustive` - All permutations (small teams only)
  - `sampled` - Random sampling
  - `strategic` - Mixed strategies (see below)
- **6 positioning strategies (mixed in 'strategic' mode):**
  - **Standard (40%)** - Tanks front (rows 0-1), carries back (rows 2-3)
  - **Solo Tank (15%)** - 1 itemized tank in front, everyone else in back 2 rows
  - **Spread (15%)** - No units adjacent (anti-AOE, zone defense style)
  - **Corner Stack (10%)** - All units clumped in one corner (anti-assassin)
  - **Diagonal (10%)** - Units on diagonal lines (controls pathing)
  - **Bait (10%)** - Weak unit in front corner, carry in opposite back corner
- **Unit role classification:**
  - Frontline: Defender, Bruiser, Warden, Juggernaut traits; melee range; high HP
  - Backline: Arcanist, Invoker, Gunslinger, Longshot traits; ranged
- **Deterministic seeding** - Reproducible results with `--seed`
- **JSON output** - Save results for further analysis

### Test Results (Mirror Match)
- **Baseline** (random positioning): 60% win rate
- **Optimized** positioning: 100% win rate
- **Conclusion:** Positioning alone can determine win/loss in equal matchups

### Usage
```bash
# Real meta comp (8 units)
python position_search.py --preset piltover_seraphine

# Custom comp
python position_search.py --comp '[{"champion":"TFT16_Draven","star":2},{"champion":"TFT16_Leona","star":2}]'

# Thorough search with saved output
python position_search.py --preset diana_targon --configs 500 --sims 20 --seed 42 -o results.json

# Test with meta comps
python test_meta_comps.py

# See all options
python position_search.py --help
python position_search.py --presets
python position_search.py --champions
python position_search.py --strategies  # Explain positioning strategies
```

### Performance
- ~300 configs × 40 sims each ≈ 3 minutes
- ~1000 configs × 40 sims each ≈ 10 minutes

---

## Phase 3: Item Optimization (Completed 2026-02-02)

**Goal:** Recommend optimal items for champions and distribute items across a comp.

### Completed
- [x] **MetaTFT item data fetcher** - `fetch_metatft_items.py`
- [x] **Item statistics storage** - `data/metatft_items.json` (100 champions)
- [x] **ItemOptimizer class** - `core/item_optimizer.py`
- [x] **Item CLI interface** - `item_search.py`
- [x] **Item effects in combat** - `core/item_effects.py`
- [x] **Combat engine integration** - Items now affect combat outcomes

### Features
- **Get best items for a unit:**
  ```bash
  python item_search.py best Seraphine
  python item_search.py best Shyvana --count 10 --special
  ```
- **Get optimal 3-item build:**
  ```bash
  python item_search.py build Seraphine
  ```
- **Recommend crafts from components:**
  ```bash
  python item_search.py craft bf rod tear vest
  python item_search.py craft bf rod tear --comp Seraphine,Braum
  ```
- **Slam vs hold analysis:**
  ```bash
  python item_search.py slam bf rod tear --stage 3-2 --hp 65
  ```
- **Distribute items across a comp:**
  ```bash
  python item_search.py distribute --comp Seraphine,Braum,Lissandra --items Leviathan,DragonsClaw
  ```

### Item Effects Implemented
| Effect Type | Items |
|-------------|-------|
| On-Hit | Giant Slayer, Last Whisper (30% armor shred), Titan's Resolve (+2 AD/armor per stack), Guinsoo's (+6% AS per stack), Statikk Shiv (chain lightning), Nashor's Tooth, Kraken's Fury, Madred's Bloodrazor (3% max HP), Wit's End |
| On-Ability | Spear of Shojin (+5 mana), Blue Buff (+20 mana), Archangel's Staff (+25 AP), Crownguard (30% HP shield), Leviathan |
| On-Damage-Dealt | Hextech Gunblade (25% heal), Morellonomicon (10% burn) |
| On-Damage-Taken | Bramble Vest (reflect), Gargoyle Stoneplate (15 armor/MR per enemy), Sterak's Gage (25% HP shield at 50% HP), Edge of Night (untargetable at 50% HP) |

### Test Results
- **Mirror match (items vs no items):** 100% win rate for itemized team
- Items properly scale combat outcomes

---

## Phase 4: Full Game RL (Future)

**Goal:** Train agents for economy, leveling, shop decisions, augment selection.

### Options
1. **Update `Simulator/`** - Existing MuZero game env, needs Set 16 update
2. **Build new wrapper** - Around combat engine with fresh architecture

### Required Components
- Game state (gold, XP, health, round, stage)
- Shop/roll mechanics
- Level-up decisions
- Augment selection (rounds 1-3-2, 2-3-2, etc.)
- Player matchmaking
- Carousel

---

### MetaTFT Position Data Integration (2026-02-02)
Fixed row orientation for MetaTFT position data:
- MetaTFT cells 1-7 (visual top) → Game row 3 (back)
- MetaTFT cells 22-28 (visual bottom) → Game row 0 (front)
- Positioning optimizer now uses 20% MetaTFT-guided positions in mixed strategy

---

*Last updated: 2026-02-02*
