# TFT Simulator Data Audit - Patch 16.4 (Riot internal 16.3)

> **Purpose:** Systematically verify every champion, trait, item, and augment in the simulator
> against authoritative online sources. Fix anything that's wrong. Do NOT fabricate data.
>
> **Target Patch:** 16.4 (live as of Feb 4, 2026). Riot internal version is 16.3.
>
> **CRITICAL RULE:** If you cannot find authoritative data for something, mark it as
> `# TODO: UNVERIFIED - could not find source` rather than guessing. Wrong data is worse
> than missing data.

---

## How To Do This Audit

This audit is large. Work through it **one section at a time**, committing after each section.
Use the todo list to track progress. Each section should:

1. Read the simulator's current data
2. Cross-reference against online sources (see Source Priority below)
3. Fix discrepancies with a clear comment noting the source
4. Run a quick smoke test (`python -c "from simulator.game.game import TFTGame; TFTGame(seed=42).play()"`)
5. Commit with a descriptive message

### Source Priority (use in this order)

1. **Riot Patch Notes** - https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/
   - Check 16.1, 16.2, 16.3, 16.4 notes for balance changes
2. **League Wiki (TFT)** - https://wiki.leagueoflegends.com/en-us/TFT:
   - Has exact stat tables for champions, traits, items
   - Example: https://wiki.leagueoflegends.com/en-us/TFT:Noxus
3. **MetaTFT** - https://www.metatft.com/
   - Has current unit stats, items, augments, traits
   - Example: https://www.metatft.com/units/Swain
4. **Community Dragon / Data Dragon** - Static game data files
5. **Our own combat_data.json** (`simulator/data/combat_data.json`)
   - Extracted from game files, generally trustworthy for raw ability variables
   - BUT champion costs may be wrong (e.g., shows 7-costs as cost=5)

### Files You'll Be Editing

| File | What's in it | # Entries |
|------|-------------|-----------|
| `simulator/Simulator/pool_stats.py` | Champion pool sizes (COST_1 through COST_7) | 105 champs |
| `simulator/Simulator/origin_class_stats.py` | Champion -> trait mappings, trait breakpoints | 175 entries |
| `simulator/core/combat_engine.py` | Trait effect dicts (stats at each breakpoint) | ~25 traits |
| `simulator/core/champion_abilities.py` | Champion ability handlers (_cast_*) | ~68 methods |
| `simulator/data/set16_items.py` | Item stats, emblem mappings | ~150 items |
| `simulator/data/combat_data.json` | Raw champion/trait data from game extraction | 106 champs |
| `data/game_data/champions.jsonl` | Champion meta stats (placements, win rates) | 101 entries |
| `data/game_data/traits.jsonl` | Trait meta stats | 50 entries |
| `data/game_data/items.jsonl` | Item data | 152 entries |
| `data/game_data/augments.jsonl` | Augment data | 399 entries |

---

## Section 1: Champions - Pool & Cost Verification

**Goal:** Verify every champion exists, has the correct cost tier, and correct pool count.

### What to check:
- `simulator/Simulator/pool_stats.py` has 6 dicts: COST_1 through COST_7
- Each dict maps `champion_name` -> `copy_count`
- Pool sizes should be: 1-cost=29, 2-cost=22, 3-cost=18, 4-cost=12, 5-cost=10, 7-cost=10

### Verify against:
- https://wiki.leagueoflegends.com/en-us/TFT:Teamfight_Tactics (champion list)
- https://www.metatft.com/ (unit costs)
- Patch 16.4 notes for any champion additions/removals

### Specific checks:
- [ ] Are there exactly 14 one-cost, 19 two-cost, 18 three-cost, 24 four-cost, 24 five-cost, 6 seven-cost champions?
- [ ] Does each champion name match the game? (lowercase, no spaces)
- [ ] Are any champions missing or extra?
- [ ] `base_pool_values` should be `[29, 22, 18, 12, 10, 0, 10]` (index 5 is unused, index 6 is 7-cost)
- [ ] Were any champions added/removed/reclassified in patches 16.2-16.4?

---

## Section 2: Champion Traits Verification

**Goal:** Verify every champion has the correct traits assigned.

### What to check:
- `simulator/Simulator/origin_class_stats.py` -> `origin_class` dict
- Maps `champion_name` -> `[trait1, trait2, ...]` using internal snake_case names
- Internal names: `shadow_isles`, `world_ender`, etc.

### Verify against:
- https://wiki.leagueoflegends.com/en-us/TFT: (each champion page)
- https://www.metatft.com/units/{ChampionName}

### Specific checks:
- [ ] Every champion in pool_stats.py has a matching entry in origin_class
- [ ] Every champion's trait list is correct and complete
- [ ] No traits are misspelled (compare against the `tiers` dict in same file)
- [ ] Special/unique units (Atakhan, Rift Herald, Piltover Invention, etc.) have correct (possibly empty) trait lists
- [ ] Trait breakpoint tiers in the `tiers` dict match the game (e.g., `noxus: [3, 5, 7, 10]`)

---

## Section 3: Trait Effects Verification

**Goal:** Verify every trait's stat effects at each breakpoint are correct.

### What to check:
- `simulator/core/combat_engine.py` has ~25 `*_EFFECTS` dicts in the TraitManager class
- Each dict maps breakpoint -> stat values

### Verify against:
- https://wiki.leagueoflegends.com/en-us/TFT:{TraitName} for each trait
- Patch 16.2/16.3/16.4 notes for balance changes
- `simulator/data/combat_data.json` -> traits section for raw game data

### Specific checks per trait:
- [ ] **Region traits** (12): Bilgewater, Demacia, Freljord, Ionia, Ixtal, Noxus, Piltover, Shadow Isles, Shurima, Targon, Void, Yordle, Zaun
- [ ] **Class traits** (10+): Arcanist, Bruiser, Defender, Disruptor, Gunslinger, Harvester, Invoker, Juggernaut, Longshot, Quickstriker, Slayer, Vanquisher, Warden
- [ ] **Unique traits**: Blacksmith, Darkin, World Ender, Emperor, etc.
- [ ] For each trait: Are the breakpoints correct? Are the stat values at each tier correct?
- [ ] Are there traits in the game that have NO implementation? (search for "stub" or missing _apply_ methods)
- [ ] Were any trait values changed in patches 16.2-16.4?

### Important trait mechanics to verify:
- **Noxus**: Atakhan summoning at 15% enemy HP loss. Star = sum of Noxian stars. Breakpoints 3/5/7/10.
- **Freljord**: Tower placement, 3=stats only, 5=extra tower+stats, 7=stun ALL enemies on tower break.
- **Shadow Isles**: Soul collection on enemy death, stat scaling.
- **Bilgewater**: Serpent economy, pirate store.
- **Piltover**: Module system at 2/4/6.
- **Zaun**: Shimmer transformation at HP threshold.

---

## Section 4: Champion Abilities Verification

**Goal:** Verify each champion's ability implementation matches the game.

### What to check:
- `simulator/core/champion_abilities.py` has ~68 `_cast_*` methods
- `simulator/data/combat_data.json` has raw ability variables per champion

### Verify against:
- https://wiki.leagueoflegends.com/en-us/TFT:{ChampionName}
- https://www.metatft.com/units/{ChampionName}
- `combat_data.json` ability variables (these are data-mined, generally accurate)

### Specific checks:
- [ ] Every champion in the pool has an ability handler (or at least a note that it's a stub)
- [ ] Ability damage values match combat_data.json at each star level
- [ ] Ability mechanics match the game description (stun durations, heal amounts, etc.)
- [ ] Special mechanics: Aatrox combo, Ambessa dash, Fizz untargetable, etc.
- [ ] Were any abilities reworked in patches 16.2-16.4? (Check: Taric, Kindred, Jhin from 16.3)
- [ ] Atakhan ability: cleave damage, omnivamp, damage amp, DOT, Bring Ruin timer

### Champions to pay special attention to (reworked in 16.3):
- **Taric**: Was 90% durability at 35% HP -> now heals 300/700 HP over 2s
- **Kindred**: Was preventing deaths -> now shields allies
- **Jhin**: Fixed Attack Speed set to 1.0
- **Shyvana**: Aura persistence (works even when dead)

---

## Section 5: Items Verification

**Goal:** Verify all items have correct stats and recipes.

### What to check:
- `simulator/data/set16_items.py` -> COMPLETED_ITEMS, EMBLEM_ITEMS, ARTIFACT_ITEMS, etc.
- `simulator/game/constants.py` -> ITEM_RECIPES dict
- `data/game_data/items.jsonl` -> raw item data

### Verify against:
- https://wiki.leagueoflegends.com/en-us/TFT:Items
- https://www.metatft.com/items
- items.jsonl (our data file)

### Specific checks:
- [ ] Every craftable item (36 combinations from 9 components) exists and has correct stats
- [ ] Item recipes are correct (component1 + component2 -> completed item)
- [ ] Emblem items: all 22 emblems present, correct trait mapping, 150 HP stat
- [ ] Tactician items (Crown/Cape/Shield): zero combat stats, +1 team size only
- [ ] Artifact items: stats match game data
- [ ] Radiant items: stats match game data
- [ ] Were any items changed in patches 16.2-16.4?

---

## Section 6: Augments Verification

**Goal:** Verify augment pool, tier assignments, and stage availability.

### What to check:
- `data/api/processed/augments_set16.json` (if exists) or `data/game_data/augments.jsonl`
- `simulator/game/game.py` -> augment selection logic, tier odds

### Verify against:
- https://www.metatft.com/augments
- https://tactics.tools/augments
- Patch notes for augment additions/removals/changes

### Specific checks:
- [ ] Are disabled augments properly excluded?
- [ ] Stage availability tags (2-1, 3-2, 4-2) are correct per augment
- [ ] Tier inference logic is reasonable (silver/gold/prismatic)
- [ ] Tier odds per stage match tftodds.com data:
  - 2-1: 28% silver, 62% gold, 10% prismatic
  - 3-2: 35% silver, 45% gold, 20% prismatic
  - 4-2: 6% silver, 74% gold, 20% prismatic
- [ ] Were any augments added/removed/changed in patches 16.2-16.4?

---

## Section 7: Shop & Economy Verification

**Goal:** Verify level odds, XP costs, economy rules.

### What to check:
- `simulator/Simulator/pool_stats.py` -> `level_percentage` (cumulative odds per level)
- `simulator/game/constants.py` -> LEVEL_ODDS, LEVEL_XP_REQUIRED, economy constants
- `simulator/game/champion_pool.py` -> shop rolling logic

### Verify against:
- https://tftodds.com/ or similar TFT odds calculator
- Patch 16.4 notes: "reduced XP needed Level 8->9 (76->68)"
- Patch 16.4 notes: "Increased 3-cost appearance at Level 7"

### Specific checks:
- [ ] Level-up XP thresholds match the game (especially Level 8->9 changed in 16.4!)
- [ ] Shop odds per level match current patch (Level 7 3-cost odds increased in 16.4!)
- [ ] 7-cost champions are included in 5-cost roll pool (already implemented)
- [ ] Interest cap is 5 gold
- [ ] Streak bonuses are correct
- [ ] Reroll cost is 2 gold

---

## Section 8: Cross-Reference Consistency Check

**Goal:** Verify all data files agree with each other.

### Checks:
- [ ] Every champion in pool_stats.py exists in origin_class_stats.py
- [ ] Every champion in origin_class_stats.py exists in combat_data.json
- [ ] Every champion with an ability handler exists in the pool
- [ ] Every trait in origin_class has a matching entry in the tiers dict
- [ ] Every trait in tiers dict has a corresponding _EFFECTS dict in combat_engine.py
- [ ] Every emblem in EMBLEM_TO_TRAIT maps to a trait that exists in the tiers dict
- [ ] Champion names are consistent across all files (all lowercase, no spaces)
- [ ] No orphaned entries (data in one file but not referenced elsewhere)

---

## Commit Strategy

Commit after completing each section:

```
fix: Audit section 1 - verify champion pool sizes and costs (patch 16.4)
fix: Audit section 2 - verify champion trait assignments (patch 16.4)
fix: Audit section 3 - verify trait effect values (patch 16.4)
fix: Audit section 4 - verify champion ability implementations (patch 16.4)
fix: Audit section 5 - verify item stats and recipes (patch 16.4)
fix: Audit section 6 - verify augment pool and tiers (patch 16.4)
fix: Audit section 7 - verify shop odds and economy (patch 16.4)
fix: Audit section 8 - cross-reference consistency check (patch 16.4)
```

---

## Known Issues From Previous Sessions

These have already been fixed but double-check they're still correct:

1. **7-cost pool**: Should be 10 copies each (same as 5-cost), NOT 1
2. **7-cost shop**: Should roll in same pool as 5-cost (check champion_pool.py)
3. **Freljord stun**: ONLY at 7 Freljord (not 3 or 5)
4. **Emblems**: Exactly 22. NO Shadow Isles, Targon, Harvester, Disruptor, or Shurima emblems
5. **Tactician items**: ZERO combat stats
6. **Noxus/Atakhan**: Summoned mid-combat, star = sum of Noxian stars
7. **Augment weights**: Equal weights (no 3x trait boost)

---

## Notes

- This is a Set 16 "Lore & Legends" simulator
- The game has 8 Noxus champions (Briar, Sion, Darius, Draven, LeBlanc, Ambessa, Swain, Mel)
- There are 6 seven-cost champions (Aurelion Sol, Baron Nashor, Brock, Ryze, Sylas, Zaahen)
- Atakhan is a summon (not in the champion pool) with cost=11 in combat_data.json
- The combat engine uses DISPLAY names for traits (e.g., "Shadow Isles"), while
  origin_class_stats uses INTERNAL names (e.g., "shadow_isles")
