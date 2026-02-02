# Artifact Item Analysis - Combat Engine Implementation Status

## Summary
- **Total Artifact Items**: 35 (includes Zhonya's Paradox added)
- **Implemented (stats only)**: 32
- **Fully Implemented (with effects)**: 3
  - Edge of Night (untargetable at 60% HP + cleanse)
  - Zhonya's Paradox (untargetable at 50% HP)
  - Radiant Edge of Night (untargetable + full heal at 60% HP)
- **Need Special Logic**: 32

## Core Mechanics Implemented
- **Untargetable State**: Units can become untargetable (Fizz ability, Edge of Night, Zhonya's)
- **HP Threshold Triggers**: Items check HP% and trigger effects on damage taken
- **Cleanse Effects**: Removes stuns and debuffs

## Champion Abilities Implemented
- **Fizz - Playful Trickster**: Untargetable, leap to farthest enemy in 4 hexes, AoE damage, enhanced attacks

---

## Items Requiring Special Combat Logic

### HIGH PRIORITY - Core Combat Mechanics

#### 1. **Statikk Shiv** ⚠️ NOT IMPLEMENTED
- **Effect**: Every 3rd attack deals 30 + 40% AP magic damage to 4 enemies
- **Implementation**: Track attack counter, proc chain lightning every 3rd attack
- **Status**: Stats only, no chain lightning proc

#### 2. **Fishbones** ⚠️ NOT IMPLEMENTED
- **Effect**: Attacks target RANDOM enemies (not nearest)
- **Implementation**: Override targeting to use random instead of nearest
- **Status**: Stats only, targeting not changed

#### 3. **Silvermere Dawn** ⚠️ NOT IMPLEMENTED
- **Effect**: Stun immunity + attacks stun for 0.8s, BUT attack speed locked at 0.5
- **Implementation**: Add stun immunity, apply stun on hit, cap AS at 0.5
- **Status**: Stats only, no stun mechanics

#### 4. **Prowler's Claw** ⚠️ NOT IMPLEMENTED
- **Effect**: After kill, cleanse + dash to farthest enemy within 4 hexes, next 2 crits deal +50% crit damage
- **Implementation**: Track kills, implement dash, buff next crits
- **Status**: Stats only, no dash/cleanse

#### 5. **Spectral Cutlass** ⚠️ NOT IMPLEMENTED
- **Effect**: Combat start: Teleport to mirrored hex on enemy side for 8 seconds
- **Implementation**: Relocate unit at combat start, return after 8s
- **Status**: Stats only, no teleport

#### 6. **Shadow Puppet** ⚠️ NOT IMPLEMENTED
- **Effect**: Spawn clone with 60% HP, 40% damage, copies items
- **Implementation**: Create duplicate unit at combat start
- **Status**: Stats only, no clone

#### 7. **Suspicious Trench Coat** ⚠️ NOT IMPLEMENTED
- **Effect**: At 60% HP, split into 3 copies with 33% HP each
- **Implementation**: Monitor HP threshold, spawn copies
- **Status**: Stats only, no splitting

#### 8. **The Indomitable** ⚠️ NOT IMPLEMENTED
- **Effect**: Pulls current target into melee range, stun immune, slow movement
- **Implementation**: Pull mechanic, modify movement speed
- **Status**: Stats only, no pull

---

### MEDIUM PRIORITY - Stat Stealing/Stacking

#### 9. **Aegis of Dawn** ⚠️ NOT IMPLEMENTED
- **Effect**: Every 2.5s steal 5 Armor from enemies in 1 hex, heal % of holder's Armor
- **Implementation**: Periodic tick, AoE armor steal, self-heal
- **Status**: Stats only

#### 10. **Aegis of Dusk** ⚠️ NOT IMPLEMENTED
- **Effect**: Every 2.5s steal 5 MR from enemies in 1 hex, deal damage = % of holder's MR
- **Implementation**: Periodic tick, AoE MR steal, damage
- **Status**: Stats only

#### 11. **Blighting Jewel** ⚠️ NOT IMPLEMENTED
- **Effect**: Magic damage reduces target MR by 2. If MR=0, gain 2 mana instead
- **Implementation**: Track enemy MR, apply shred or mana gain
- **Status**: Stats only

#### 12. **Cappa Juice** ⚠️ NOT IMPLEMENTED
- **Effect**: Gain 1% AD/AP per takedown (stacking hats). Lose 20% hats on death
- **Implementation**: Track takedowns, stack stats
- **Status**: Stats only

#### 13. **Seeker's Armguard** ⚠️ NOT IMPLEMENTED
- **Effect**: Takedowns grant +20 Armor, MR, and AP
- **Implementation**: Track takedowns, stack stats
- **Status**: Stats only

#### 14. **Flickerblades (Navori)** ⚠️ NOT IMPLEMENTED
- **Effect**: Attacks grant +5% stacking AS. Every 5 attacks also grant +2% AD and +2 AP
- **Implementation**: Track attacks, stack multiple stats
- **Status**: Stats only

#### 15. **Rapid Firecannon** ⚠️ NOT IMPLEMENTED
- **Effect**: +1 Attack Range, +1 more per kill
- **Implementation**: Track kills, modify range stat
- **Status**: Stats only (range increase not implemented)

---

### MEDIUM PRIORITY - On-Hit/Proc Effects

#### 16. **Lich Bane** ⚠️ NOT IMPLEMENTED
- **Effect**: First attack after ability deals bonus magic damage (stage-scaling)
- **Implementation**: Track ability casts, buff next auto
- **Status**: Stats only

#### 17. **Titanic Hydra** ⚠️ NOT IMPLEMENTED
- **Effect**: Attacks deal 3% max HP + 8% AD as splash to target and adjacent
- **Implementation**: Calculate splash damage, apply to adjacent enemies
- **Status**: Stats only

#### 18. **Wit's End** ⚠️ NOT IMPLEMENTED
- **Effect**: Attacks deal bonus magic damage (stage-scaling), heal 30% of magic damage dealt
- **Implementation**: Add on-hit magic damage, heal on magic damage
- **Status**: Stats only

#### 19. **Hellfire Hatchet** ⚠️ NOT IMPLEMENTED
- **Effect**: Attacks deal 2% max HP as physical damage. Gain 1% AS per 1% missing HP
- **Implementation**: Calculate HP-based damage, dynamic AS buff
- **Status**: Stats only

#### 20. **Corrupt Vampiric Scepter** ⚠️ NOT IMPLEMENTED
- **Effect**: Attacks deal +60% AD as physical and heal for that amount. CANNOT CAST ABILITIES
- **Implementation**: Block ability casting, add lifesteal damage
- **Status**: Stats only, ability blocking not implemented

---

### MEDIUM PRIORITY - Shields/Healing/Support

#### 21. **Lightshield Crest** ⚠️ NOT IMPLEMENTED
- **Effect**: Every 3s, shield lowest HP ally for 70% of holder's (Armor + MR). On death, shield all allies
- **Implementation**: Periodic shield, death trigger for team shield
- **Status**: Stats only

#### 22. **Mending Echoes** ⚠️ NOT IMPLEMENTED
- **Effect**: +25% healing received. When healed, grant 40% of heal to lowest HP ally
- **Implementation**: Modify healing received, trigger ally heals
- **Status**: Stats only

#### 23. **Forbidden Idol** ⚠️ NOT IMPLEMENTED
- **Effect**: 50% of shield value converts to max HP instead
- **Implementation**: Intercept shields, convert to HP
- **Status**: Stats only

#### 24. **Innervating Locket** ⚠️ NOT IMPLEMENTED
- **Effect**: Gain 1% mana when hit. Each cast heals 20% max HP over 3s
- **Implementation**: Track incoming attacks for mana, HoT on cast
- **Status**: Stats only

#### 25. **Eternal Pact** ⚠️ NOT IMPLEMENTED
- **Effect**: Pact with highest HP ally. If they die, gain stats. When ally casts, gain mana. Every 6s shield ally
- **Implementation**: Track linked ally, multiple triggers
- **Status**: Stats only

---

### LOWER PRIORITY - Conditional/Delayed Effects

#### 26. **Dawncore** ⚠️ NOT IMPLEMENTED
- **Effect**: Reduce max mana by 10. Each cast reduces max mana by 10% (min 10)
- **Implementation**: Modify mana on ability cast
- **Status**: Stats only

#### 27. **Talisman of Ascension** ⚠️ NOT IMPLEMENTED
- **Effect**: After 22 seconds gain +100% max HP and +120% damage amp
- **Implementation**: Timer, massive stat buff
- **Status**: Stats only

#### 28. **Horizon Focus** ⚠️ NOT IMPLEMENTED
- **Effect**: When stunning an enemy, deal 30% of their max HP as magic damage
- **Implementation**: Track stun applications, deal bonus damage
- **Status**: Stats only

#### 29. **Luden's Tempest** ⚠️ NOT IMPLEMENTED
- **Effect**: 100% of overkill damage + 100 dealt to 3 nearest enemies
- **Implementation**: Calculate overkill, apply splash
- **Status**: Stats only

#### 30. **Unending Despair** ⚠️ NOT IMPLEMENTED
- **Effect**: When shield breaks, deal 150% of shield value to nearest enemy
- **Implementation**: Track shield breaks, trigger damage
- **Status**: Stats only

#### 31. **Void Gauntlet** ⚠️ NOT IMPLEMENTED
- **Effect**: Store 30% max HP at start + 2.5% per second. On death, deal stored HP as magic damage in 4 hex AoE
- **Implementation**: Accumulate damage, death trigger
- **Status**: Stats only

---

### SPECIAL - Persona Items

#### 32. **Mirrored Persona** ⚠️ NOT IMPLEMENTED
- **Effect**: Share 15% of bonus stats with other Persona holders. Every 6 combats gain a lesser copy
- **Implementation**: Track Persona holders, share stats, spawn items
- **Status**: Stats only

#### 33. **Lesser Mirrored Persona** ⚠️ NOT IMPLEMENTED
- **Effect**: Share 15% of bonus stats with other Persona holders
- **Implementation**: Track Persona holders, share stats
- **Status**: Stats only

---

### IMMUNITY Items

#### 34. **Mittens** ⚠️ NOT IMPLEMENTED
- **Effect**: Immunity to Chill, Burn, Wound. +25% damage reduction
- **Implementation**: Add debuff immunities, damage reduction
- **Status**: Stats only, immunities not implemented

---

## Non-Artifact Items Requiring Untargetable Logic

### Edge of Night (Base Item)
- **Effect**: At 60% HP, become untargetable briefly, cleanse negative effects
- **Status**: Stats only, untargetable not implemented

### Zhonya's Paradox (Artifact - missing from list)
- **Effect**: At % HP, become invulnerable and untargetable for X seconds
- **Status**: Not in artifact list, needs to be added

### Radiant Edge of Night
- **Effect**: At threshold, become untargetable, cleanse, heal all missing HP
- **Status**: Radiant version with full heal

---

## Champion Abilities Requiring Untargetable

### Fizz - Playful Trickster
- **Effect**: Become UNTARGETABLE, leap to farthest enemy within 4 hexes, deal damage, gain AS + on-hit for 4 attacks
- **Current Status**: ❌ Not implemented - no untargetable, no leap, no enhanced attacks
- **Implementation Needed**:
  1. Set `is_targetable = False` during cast
  2. Find farthest enemy within 4 hex range
  3. Teleport/dash to that position
  4. Deal AoE damage on landing
  5. Grant AS buff + on-hit magic damage for next 4 attacks

---

## Implementation Priority Order

1. **Untargetable state** - Needed for Fizz, Edge of Night, Zhonya's, etc.
2. **Clone/Split mechanics** - Shadow Puppet, Suspicious Trench Coat
3. **On-hit procs** - Statikk Shiv, Lich Bane, Wit's End, Titanic Hydra
4. **Stat stealing** - Aegis items, Blighting Jewel
5. **Stacking mechanics** - Cappa Juice, Seeker's, Flickerblades
6. **Periodic effects** - Lightshield, Eternal Pact
7. **Death triggers** - Void Gauntlet, Lightshield on death
8. **Movement abilities** - Prowler's dash, Spectral teleport, Indomitable pull
