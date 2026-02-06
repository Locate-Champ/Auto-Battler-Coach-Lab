# TFT Set 16 Champion Ability Audit

## Implementation Status Legend
- ✅ **Implemented** - Ability mechanics are in champion_abilities.py
- ⚠️ **Stats Only** - Has data in combat_data.json but no special logic
- ❌ **Not Implemented** - Missing special mechanics that need coding

---

## Core Combat Mechanics Implemented

1. **Target Retargeting** ✅ - Units find new target when current dies/becomes untargetable
2. **Untargetable State** ✅ - Fizz, Edge of Night, Zhonya's Paradox
3. **Form Swapping** ✅ - Kai'Sa AD/AP, Jinx minigun→rockets
4. **Tank Targeting** ✅ - Frontline units draw aggro
5. **Enhanced Attacks** ✅ - Fizz post-ability buffed attacks
6. **Champion Abilities Module** ✅ - 40+ champions in champion_abilities.py

---

## Champion Audit

### Caitlyn (TFT16_Caitlyn) ✅ IMPLEMENTED
**Ability:** Ace in the Hole - Excess damage on kill
- ADDamage: 475/715/1105
- APDamage: 40/60/100
- **Implemented:** Excess damage overflow to next target (champion_abilities.py)

### Aphelios (TFT16_Aphelios) ✅ IMPLEMENTED
**Ability:** Incendiary Onslaught
- NumTargets: 3 (Infernum hits 3 enemies)
- AttackSpeed: 2.0 during ability
- SeverumADDamage: 70/105/175
- Omnivamp: 10%
- **Implemented:** 3-target Infernum spread with omnivamp healing

### Bard (TFT16_Bard) ✅ IMPLEMENTED
**Ability:** Traveler's Call
- Damage: 120/170/240
- NumMissilesBase: 6
- PercentDamageOnCurrentTarget: 75%
- EnemyHexSearchRadius: 3
- **Implemented:** Meep-based targeting with primary/secondary damage distribution

### Yasuo (TFT16_Yasuo) ✅ IMPLEMENTED
**Ability:** Sweeping Blade
- ADDamage: 85/125/190
- YasuoADPercent: 100% AD scaling
- AttributeBrothersDamageToYasuo: 1.0 (Yone synergy)
- **Implemented:** Dash mechanic, Yone combo synergy with damage bonus

### Malzahar (TFT16_Malzahar) ✅ IMPLEMENTED
**Ability:** Void Swarm
- NumMinions: 2
- NumAttacks: 8
- Damage: 29/43/68 per voidling attack
- MinionDuration: 90 seconds
- **Implemented:** Simulated voidling attacks (untargetable damage over time)

### LeBlanc (TFT16_Leblanc) ✅ IMPLEMENTED
**Ability:** Distortions
- NumTargets: 3
- Damage: 300/450/700
- SecondaryDamage: 180/270/450
- NearbyEnemyHexRadius: 3
- StunDuration: 1.0s
- **Implemented:** Multi-target dash + stun mechanics

### Gangplank (TFT16_Gangplank) ✅ IMPLEMENTED
**Ability:** Powder Kegs
- ADDamage: 190/285/450
- NumofBarrels: 3
- FalloffDamage: 25%
- ArmorReduction: 10 (20 on crit)
- **Implemented:** Barrel chain with damage falloff and armor shred

### Milio (TFT16_Milio) ✅ IMPLEMENTED
**Ability:** Ultra Mega Fire Kick!!!
- NumBounces: 3
- MagicDamage: 190/285/445
- MagicDamageAOE: 160/240/375
- BounceSearchRange: 2 hexes
- **Implemented:** Bouncing projectile with AOE splash

### Loris (TFT16_Loris) ✅ IMPLEMENTED
**Ability:** Piltover Tussle
- Shield: 700/800/1000
- Damage: 150/225/360
- KnockupDuration: 1.25s
- ShieldDuration: 4.0s
- **Implemented:** Dash, taunt, knockup, shield application

### Darius (TFT16_Darius) ✅ IMPLEMENTED
**Ability:** Decimate
- ADDamage: 90/135/210
- APHealing: 180/220/280
- PhysicalDamagePerSecond: 15/25/40 (bleed)
- ExecutePercentPerHemorrhage: 8% per stack
- BleedDuration: 4.0s
- **Implemented:** Bleed stacking, execute based on stacks, healing

### Draven (TFT16_Draven) ✅ IMPLEMENTED
**Ability:** Spinning Axes
- GoldAmount: 1/3/5 gold per takedown
- ADDamage: 120/170/290
- TotalTakedown: 11
- **Implemented:** Axe cycling, gold on takedowns

### Vayne (TFT16_Vayne) ✅ IMPLEMENTED
**Ability:** Tumble
- ADDamage: 100/150/230
- APDamage: 6/10/15
- HexDashRange: 3 hexes
- **Implemented:** Dash away from enemies, Silver Bolts 3-hit true damage

### Renekton (TFT16_Renekton) ✅ IMPLEMENTED
**Ability:** Slice and Dice
- DashADDamage: 80/120/360
- SlashADDamage: 50/75/550
- DashRange: 2 hexes
- **Implemented:** Dash through enemies, AOE slash on landing

### Veigar (TFT16_Veigar) ✅ IMPLEMENTED
**Ability:** Dark Storm
- IncreasedAPRatio: 0.5 (50% bonus AP scaling)
- NumMeteors: 12/12/24
- Damage: 62/93/199 per meteor
- APPerKill: +1 permanent AP
- PercentOnPrimaryTarget: 70%/70%/50%
- **Implemented:** Innate AP scaling, permanent AP stacking on kills

### Seraphine (TFT16_Seraphine) ✅ IMPLEMENTED
**Ability:** Grand Encore
- DamagePerCrystal: 35/55/300
- CastBreakpoint: 12 casts for big cast
- BigCastDamage: 270/405/2200
- BigCastHeal: 40/80/400
- CrystalsPerCast: 3
- BigCastDamageFalloff: 30%
- **Implemented:** Cast tracking, 12-cast super ability, line damage with falloff

### Lissandra (TFT16_Lissandra) ✅ IMPLEMENTED
**Ability:** Frozen Tomb
- TargetDamage: 275/415/2800
- SecondaryDamage: 415/625/2800 (excess overflow)
- NumOverkillEnemies: 2
- StunDuration: 1.0s
- DamageAmpChilledTargets: 12%
- **Implemented:** Stun, excess damage overflow to nearby enemies

### Swain (TFT16_Swain) ✅ IMPLEMENTED
**Ability:** Nevermove
- PercentMaximumHealthHealing: 1.5%
- PassiveDamage: 20/30/90 per tick
- StunDuration: 1.5s (AoE)
- **Implemented:** AoE stun, passive damage, drain healing

### Yone (TFT16_Yone) ✅ IMPLEMENTED
**Ability:** Kin of the Stained Blade
- BasicAttackADDamage: 80/120/800
- BasicAttackAPDamage: 140/210/1400
- StrikeADDamage: 160/240/1080
- KnockupDuration: 1.5s
- YasuoADPercent: 2.5x with Yasuo
- DashHexRange: 2.5/2.5/5.0 (3-star doubles)
- **Implemented:** Yasuo combo synergy, dual AD/AP scaling, knockup

### Lux (TFT16_Lux) ✅ IMPLEMENTED
**Ability:** Final Spark
- PrimaryDamage: 330/500/1600 (main laser)
- SecondaryDamage: 90/135/900
- QDamage: 30/45/100
- NumQTargets: 2
- StunDuration: 1.0s
- BeamWidth: ~200 game units
- **Implemented:** Line laser toward target (not board-wide), beam width ~200, Q stun on 2 nearest

### Kai'Sa (TFT16_Kaisa) ✅ PARTIALLY IMPLEMENTED
**Ability:** Icathian Rain
- NumMissiles: 15/15/25
- APDamage: 6/9/20 per missile
- ADDamage: 39/63/150 per missile
- NumTargets: 4
- PercentMissilesOnCurrentTarget: 60%
- **Implemented:**
  - AD/AP form swap based on higher stat
  - Multi-target missile spread
- **Missing:**
  - AD form dash (costs 60 mana, starts with 20)
  - AP form mana mechanics (costs 30, starts 20, no mana gain for 5s)

### Rift Herald ✅ IMPLEMENTED
- BonusDurability: 0.25→0.8 at 3-star
- PercentHealthDamage: 6%→12%
- BonusHealth: 350-2000
- **Implemented:**
  - Warp Armor: Gain durability based on nearby enemies
  - Scales with enemy count (+1% DR per nearby enemy)
  - Grants bonus health on cast
  - Deals damage to nearby enemies

### Taric (TFT16_Taric) ✅ IMPLEMENTED
**Ability:** Starlight's Touch
- **Passive MR Aura** (always active): All allies gain 10/20/100 Magic Resist
- **Passive Heal at 35% HP** (once per combat): Restore 300/700/2500 health over 2 seconds
- **Active - Self Shield:** 600/700/2500
- **Active - Ally Shield:** Grant 2 LOWEST HEALTH allies 125/150/1000 shield for 4 seconds
- **Empowered Attacks:** Next 2/2/10 attacks deal 200/300/3000 bonus **magic damage**
- **Implemented:**
  - Passive MR aura at combat start via `apply_taric_passive_mr()`
  - Self shield on ability cast
  - Ally shields on 2 **lowest health** allies (not nearest!)
  - Empowered attacks with bonus MAGIC damage via `check_taric_empowered_attack()`
  - 35% HP heal trigger via `check_taric_low_hp_heal()` (NOT invulnerability!)

### Skarner (TFT16_Skarner) ✅ IMPLEMENTED
- ArmorForAllies: 10-100 aura
- ImpaleDuration: 2s→8s at 3-star
- DamagePercentArmor: 1.2x→25x (armor scaling!)
- ImpaleMaxTargets: 3→4
- **Implemented:**
  - Armor aura granted to all allies on cast
  - Self shield on ability
  - Impale: Stun + drag enemy to adjacent hex

### Leona (TFT16_Leona) ✅ IMPLEMENTED
**Ability:** Solar Flare
- FlatDR: 15/30/60 damage reduction (passive)
- NumEnemies: 3
- StunDuration: 1.0s
- Damage: 80/120/200
- IgniteDuration: 4.0s
- DianaAP: 3/4/5 (bonus AP to Diana)
- **Implemented:**
  - Passive flat damage reduction on first cast
  - AOE stun + damage centered on target
  - Ignite burn damage
  - Diana synergy: Grants Diana bonus AP

### Wukong (TFT16_Wukong) ✅ IMPLEMENTED
- SummonMaxHealthPercent: 40% clone HP
- SummonFlatHealth: 150-2000 flat HP
- Resists: 100-400 armor/MR on clone
- Duration: 4s
- **Implemented:** Simulated clone damage output

### Warwick (TFT16_Warwick) ✅ IMPLEMENTED
**Ability:** Eternal Hunger
- AttackSpeed: 1.0/1.0/4.0 (self buff)
- ADDamage: 45/70/550 (bonus AD)
- Omnivamp: 15%
- AllyAttackSpeed: 0.2/0.2/0.5 (ally buff)
- AllyBuffDuration: 3.0s
- **Implemented:**
  - Single cast only mechanic (permanent self buff)
  - Self AS + AD + Omnivamp buff
  - Ally attack speed buff
  - Buff duration tracking

### Singed (TFT16_Singed) ✅ IMPLEMENTED
**Ability:** Poison Trail
- PoisonCloudDuration: 4.0s
- DamagePerSecond: 8/50/160
- ArmorMR: 20 reduction
- HealPerSecond: 15/150/500
- **Implemented:**
  - Walk through enemies (dash to farthest enemy)
  - Aggro drawing (backline enemies re-target Singed)
  - Poison damage to all enemies
  - Armor/MR reduction debuff
  - Self-heal over duration

### Ambessa (TFT16_Ambessa) ✅ IMPLEMENTED
- SlamDamageMultiplier: 3.15x
- ADDamage: 45-320
- **Implemented:** Dash mechanic, kill reset (mana refund)

### Nidalee (TFT16_Nidalee) ✅ IMPLEMENTED
**Ability:** Javelin Toss / Takedown
- TargetDamage: 320/540/2000
- SecondaryDamage: 100/180/600
- TankDamageMult: 0.6x (40% less vs tanks)
- FighterDamageMult: 0.3x (70% less vs fighters)
- DamageReductionPerCast: 0.7 (30% less per cast)
- **Implemented:**
  - Role-based damage reduction (tanks, fighters)
  - Damage reduction per prior cast
  - Secondary damage to nearby enemies
- **Huntress Trait:** See Traits section below

### Miss Fortune (TFT16_MissFortune) ✅ IMPLEMENTED
**Ability:** Heartbreaker
- AutoRicochetMultiplier: 0.5/0.5/1.0 (passive)
- BaseNumWaves: 2/2/6
- NumCaststoGainExtraWave: 3
- ADDamage: 145/220/3000
- APDamage: 15/25/70
- PercentDamageOfSecondaryWaves: 50%
- **Implemented:**
  - Auto-attack ricochet passive enabled on first cast
  - Wave accumulation tracking (every 3 casts = +1 wave)
  - Cone damage to enemies in range
  - Secondary wave damage falloff

### Diana (TFT16_Diana) ✅ IMPLEMENTED
**Ability:** Lunar Rush
- Shield: 100/175/300
- ShieldDuration: 2.0s
- HexLimit: 4 hex radius
- TargetDamage: 125/190/600
- SecondaryDamage: 140/210/1350
- MoonlightDamageReduction: 10%
- **Implemented:**
  - Dash to target within range
  - Shield self on cast
  - Deal damage to primary target
  - Secondary damage to nearby enemies (pull effect)
  - Leona synergy: Gains 10% damage reduction when Leona is on team

### Ziggs (TFT16_Ziggs) ✅ IMPLEMENTED
**Ability:** Mega Inferno Bomb
- BABounceNumber: 1 (auto attack bounce)
- BAPercentAP: 40/65/500%
- BombAOERange: 4 hex
- MinAOEDamage: 70/105/3000 (edge damage)
- MaxAOEDamage: 550/875/7000 (center damage)
- **Implemented:**
  - Auto-attack bounce passive enabled on first cast
  - Large AOE bomb at target position
  - Distance-based damage (max at center, min at edge)
  - Linear damage interpolation based on distance

### Xerath (TFT16_Xerath) ✅ IMPLEMENTED
- NumberOfBlasts: 10→99
- Damage: 390→2500 per blast
- SpellRangeInEnemies: 4→10
- XerathCharmExtraBlasts: +3 with charm
- **Implemented:**
  - Eye of the Ascendant: Multiple blasts at random enemies
  - Each blast targets random alive enemy
  - Ascendant trait (shop items) handled externally

### Yorick (TFT16_Yorick) ✅ IMPLEMENTED
**Ability:** Mourning Mist
- FlatDamage: 80/110/150
- PercentHealthDamage: 5% (all star levels)
- APHeal: 325/370/500
- HealPerSoulBreakpoint: 7 (heals 7 HP per breakpoint)
- SoulBreakpoint: 10 (every 10 souls = 1 breakpoint)
- DebuffDuration: 4.0s
- **Implemented:**
  - Deals flat + 5% max HP magic damage to target
  - Marks target for 4 seconds (debuff)
  - Heals Yorick based on APHeal + soul scaling
  - Soul scaling: Every 10 souls = +7 bonus heal per cast

### Shyvana (TFT16_Shyvana) ✅ IMPLEMENTED
**Ability:** Dragon Transformation
- TransformHP: 600/1500/9999 bonus HP
- TransformDurability: 20%/50%/90% damage reduction
- DivebombADDamage: 100/350/3000
- FireDamagePerSecond: 185/500/12345
- SpellDuration: 3.0s
- **Implemented:**
  - Dragon form transformation (permanent until combat end)
  - Bonus HP and durability on transform
  - Divebomb damage + dash on initial transform
  - Fire breath AOE damage on subsequent casts

### Fiddlesticks (TFT16_Fiddlesticks) ✅ IMPLEMENTED
**Ability:** Crowstorm
- FearDuration: 1.25/2.0/99s
- ManaLossPerSecond: 22 mana/sec
- NearestBonusDamage: 33%
- DamagePerSecond: 100/300/6666
- AOERadius: 2 hex
- **Implemented:**
  - Fear (stun) application to enemies in AOE
  - Mana drain on enemies (3s worth)
  - 33% bonus damage to 2 nearest enemies
  - AOE damage in 2-hex radius

### Kindred (TFT16_Kindred) ✅ IMPLEMENTED
**Ability:** Lamb's Respite
- ShieldAmount: 350/700/10000
- Duration: 2.5/4.0/99s
- NumExtraArrows: 1/2/10
- HealPercentage: 8%
- ADDamage: 25/75/999
- **Implemented:**
  - 2-hex zone shield placement
  - Shield self + allies in zone (50% for allies)
  - Double attack speed while in zone
  - Extra arrows to nearby enemies
  - Heal on attack (8% target max HP)

### Lucian & Senna (TFT16_LucianSenna) ✅ IMPLEMENTED
- Duration: 3s channeled
- ADDamage: 75→800 per shot
- NumShots: 12→42
- FlatArmorReduction: 3→15
- **Implemented:**
  - Lucian→Senna Soulbound swap mechanic
  - While Lucian out: Team gets 7% damage amp
  - While Senna out: Team gets 7% damage reduction
  - Armor shred stacking on target

### Aatrox (TFT16_Aatrox) ✅ IMPLEMENTED
- ADDamage: 95→2400 (first hit)
- SecondCastPercentDamage: 1.2x (second hit)
- ThirdCastPercentDamage: 1.6x (third hit)
- ThirdCastExecute: 15% execute
- SunderDuration: 4s
- SecondCastStunDuration: 1s
- **Implemented:**
  - 3-hit combo system
  - Execute on 3rd hit at 15% HP threshold
  - Stun on 2nd cast
  - World Ender untargetable + AD from omnivamp

### Zilean (TFT16_Zilean) ✅ IMPLEMENTED
- MagicDamage: 75/115/1000 (1/2/3-star)
- ExplosionDamage: 150/225/4000
- MaxDurationBeforeKill: 18/16/1s (bomb timer before auto-kill)
- ManaOnKill: 15
- **Implemented:**
  - Visions of the End: Place time bombs on enemies
  - Double bomb: 2 bombs on same target = instant explosion
  - Splash damage to nearby enemies on explosion
  - Mana refund on kill

### Galio (TFT16_Galio) ✅ IMPLEMENTED
- PassiveMRRatio: 1.0→90.0 (MR scaling!)
- **Implemented:**
  - Inspirational Might: Shield all allies + MR/AR scaled damage
  - Enhanced attacks with MR bonus damage
  - Bench mechanic via `trigger_demacia_rally()`:
    - On first Demacia rally, Galio slams in
    - Auto-positions to hit most enemies
    - Entry slam + 1.5s stun to nearby

### Thresh (TFT16_Thresh) ✅ IMPLEMENTED
- Soul drain mechanics
- Box duration
- HealthDrainPerSoul scaling
- **Implemented:**
  - Hook: Pulls nearest enemy to adjacent hex
  - The Box: Deals magic damage on hook
  - Soul drain: Bonus damage + heal based on team's Shadow Isles souls
  - Soul collection integrated via TraitManager.shadow_isles_souls

### Mel (TFT16_Mel) ✅ IMPLEMENTED
- ManaDrainPerSecond variable
- Orb mechanics
- **Implemented:**
  - Radiant Eclipse: Fire orbs at target + final explosion
  - Mana drain passive via `mel_mana_drain_tick()`:
    - Drains 1 mana/sec from nearby enemies
  - Radiant item generation (handled externally)

### Tahm Kench (TFT16_TahmKench) ✅ IMPLEMENTED
- BellyDuration: 2.5s
- DamageReduction: 30%
- **Implemented:**
  - Devour: Swallow enemy, make untargetable, deal damage
  - Tahm gains 30% DR while digesting
  - Glutton trait: Full stat tables by cost and star level
    - Tank roles → HP (55-99999 by cost/star)
    - AD roles → Attack Speed % (16-69444%)
    - AP roles → Ability Power % (10-69444%)
  - AS cap at 5.0, excess converts to AP
  - Pre-combat feeding via `apply_glutton_feeding()`

### Sett (TFT16_Sett) ✅ IMPLEMENTED
- Three-dash distances: 320→600 hex
- **Implemented:**
  - The Show Stopper: Dash to farthest enemy
  - Slam damage: Flat + 9% target max HP
  - AoE 50% splash to nearby enemies

### Annie (TFT16_Annie) ✅ IMPLEMENTED
**Ability:** Enraged Inferno
- Damage: 1500/2250/8000 (first cast board-wide AOE)
- SingleTargetDamage: 240/360/3000 (subsequent casts)
- ManaCostReduction: 140 (mana cost drops from 160→20 after first cast)
- **Implemented:**
  - First cast: Board-wide AOE magic damage to all enemies
  - Mana cost reduction (160→20) after first cast
  - Subsequent casts: Single target magic damage
- **Note:** Tibbers is a SEPARATE unit fielded via Dark Child trait

### Tibbers (TFT16_AnnieTibbers) ✅ IMPLEMENTED
**Ability:** Rage of Embers
- Shield: 1000/1200/9000
- AttackSpeed: 2.0/2.0/5.0 (self AS buff)
- HealPercentHealth: 2.5%/2.5%/100% max HP
- Duration: 4.0s
- Stats: 1500 HP, 90 AD, 0.75 AS, 80 armor/MR, melee
- **IMPORTANT:** Tibbers is NOT a summon - he appears automatically!
  - When you BUY Annie, Tibbers AUTOMATICALLY APPEARS on your bench
  - CANNOT sell Tibbers separately - selling Annie removes Tibbers
  - Can be fielded independently and equip items
- **Implemented:**
  - Separate unit with own mana pool (100 max, 40 starting)
  - Own attack loop and timing (0.35s windup)
  - Rage of Embers: Self shield + AS buff + HP heal
  - Arcanist trait (benefits from Annie's Arcanist bonus)
  - Inherits star level from Annie

### T-Hex (TFT16_THex) ✅ IMPLEMENTED
- 4 missiles
- Shield generation
- **Implemented:**
  - Hextech Arsenal: Gatling gun + self shield
  - HexMech pilot system via `assign_thex_pilot()`:
    - Pilot grants 80% of their HP to T-Hex
    - Role-based bonus stats:
      - Tank: +15/25/40% Omnivamp
      - Fighter: +15/25/40% AD
      - Marksman: +10/18/30% Damage Amp
      - Caster: +2/4/5 Mana Regen
      - Assassin: +30/60/100% Crit Chance
  - On death via `trigger_thex_death()`:
    - Knockback + 1.5s stun to nearby enemies
    - Pilot ejects

### Baron Nashor (TFT16_BaronNashor) ✅ IMPLEMENTED
- 10 acid shots per cast
- 3s refresh (0.25s at 3-star)
- **Implemented:**
  - Wrath of the Void: Primary slam + knockup + acid shots
  - Acid shots: 45% max HP magic damage to random enemies
  - Riftscourge trait via `setup_baron_riftscourge()`:
    - +2 Void trait count
    - After 8s: Void Rift activates
    - Void Rift: 30% damage amp for all Void units
    - Plasma bolt tick: 5% max HP to all enemies

### Zaahen (TFT16_Zaahen) ✅ IMPLEMENTED
**Note:** EXISTS in combat_data.json as TFT16_Zaahen with Immortal trait
- AOEDamageMultiplier: 0.4
- CastsToUlt: 22
- BigAOEDamageMultiplier: 2.0
- **Implemented:**
  - Divine Challenge 22-cast instant kill
  - Immortal trait resurrection (60% HP)
  - AOE damage to other enemies

### Ryze (TFT16_Ryze) ✅ IMPLEMENTED
- Damage: 300→1500 base
- **Implemented:** 11 trait interactions:
  - Targon: 10% max HP heal
  - Yordle: 12% damage reduction
  - Bilgewater: 25% explosion to nearby
  - Void: 30% MR shred
  - Shadow Isles: 5% + soul scaling bonus damage
  - Piltover: 40% overcharge bonus damage
  - Demacia: 12% HP execute threshold
  - Freljord: Chill (30% AS slow) + 6% max HP true damage
  - Zaun: Poison ticks
  - Shurima: Knockup + gold chance tracking
  - Noxus/Ionia: Damage reduction to allies

### Sylas (TFT16_Sylas) ✅ IMPLEMENTED
- Chainbreaker trait
- **Implemented:**
  - Trifold ability rotation with smart selection:
    1. Jarvan: AoE stun + damage (prioritized with many enemies)
    2. Garen: Execute at 15% HP threshold (prioritized vs low HP targets)
    3. Lux: Team shield + line damage (prioritized when Sylas low HP)
  - Cannot cast same ability twice in a row

### Brock (TFT16_Brock) ✅ IMPLEMENTED
- PassivePercentAoE: 50%
- NumRocks for board effect
- **Implemented:**
  - Seismic Slam: Board-wide slam with distance falloff
    - 15% reduction per hex, minimum 40% effectiveness
    - Damage: base + 2% enemy max HP
    - Stun with falloff
  - Passive AoE via `brock_passive_aoe()`:
    - Attacks deal 50% damage to nearby enemies

### Aurelion Sol (TFT16_AurelionSol) ✅ IMPLEMENTED
- Star Forger trait
- 8 stardust thresholds: 25→1543
- Damage scales through tiers
- BonusStardustPerOneStar: 20%
- BonusStardustPerTwoStar: 33%
- BonusStardustPerThreeStar: 100%
- **Implemented:** Stardust accumulation, ability upgrades at thresholds

---

## Shadow Isles Soul Scaling ✅ IMPLEMENTED
All Shadow Isles units have soul-based mechanics:
- **Thresh:** HealthDrainPerSoul
- **Gwen:** SnipPerSoulBreakpoint (bonus snips from souls)
- **Kalista:** SoulsPerSpearBreakpoint (bonus spears from souls)
- **Viego:** BaseAttackSpeed from souls
- **Yorick:** HealPerSoulBreakpoint (bonus healing from souls)
- Soul multipliers: 1.0x → 1.3x → 1.6x → 1.9x
- Stat bonuses: 18-33% AD/AP

**Status:** ✅ FULLY IMPLEMENTED in `TraitManager`:
- `shadow_isles_souls` counter tracks collected souls
- `record_shadow_isles_death()` awards souls on enemy death
- Soul count scales by victim cost (1-7) and star level (1-3)
- `get_shadow_isles_stat_bonus()` returns AD/AP bonus
- `apply_shadow_isles_stats()` applies bonuses at combat start

---

## Implementation Summary

### ✅ Fully Implemented (60+ Champions)
- **Excess Damage:** Caitlyn, Lissandra
- **Summons:** Malzahar, Wukong, Annie/Tibbers
- **Dashes:** Yasuo, Vayne, Renekton, Ambessa, LeBlanc, Fizz, Diana, Loris, Sett
- **Line Abilities:** Lux, Seraphine, Yunara, Senna
- **Executes:** Aatrox, Darius, Zaahen (Divine Challenge), Sylas (Garen), Ryze (Demacia)
- **Stacking:** Veigar (AP), Draven (gold), Seraphine (crystals), Aurelion Sol (stardust), Viego
- **Synergies:** Yasuo+Yone, Diana+Leona, Lucian+Senna (Soulbound), Neeko+Nidalee (Huntress)
- **Trait-Dependent:** Ryze (11 trait effects), Sylas (3 stolen abilities)
- **Soul Scaling:** Thresh, Gwen, Kalista, Viego, Yorick (Shadow Isles)
- **Complex Mechanics:** Tahm Kench (Glutton), Galio (Bench), T-Hex (Pilot), Baron (Riftscourge)
- **Tanks:** Taric (90% DR + Invuln), Skarner (Armor aura + Impale), Leona (Flat DR)
- **Board-Wide:** Brock (Seismic), Xerath (Random blasts), Zilean (Double bombs)
- **Special:** Zaahen (Immortal resurrection), Kindred (zone shield), Rift Herald (scaling DR), Mel (Mana drain)

### ✅ All Priority Champions Now Implemented
1. **Lucian → Senna** transition ✅
2. **Shadow Isles** soul collection system ✅
3. **Ryze** trait-dependent ability selection ✅
4. **Sylas** trifold ability rotation ✅
5. **Tahm Kench** glutton feeding ✅
6. **Galio** bench mechanic ✅
7. **T-Hex** pilot system ✅
8. **Baron Nashor** riftscourge ✅

### Implementation Location
All champion ability handlers are in: `simulator/core/champion_abilities.py`

The `ChampionAbilities` class contains:
- `cast()` - Main dispatcher that routes to champion-specific handlers
- `_cast_<champion>()` - Individual ability implementations
- `check_immortal_resurrection()` - Immortal trait for Zaahen

---

---

## Implemented Traits (2026-02-04)

12 traits have been implemented in TraitManager. Stat-buffing traits auto-apply at combat start.

### Stat-Buffing Traits (10)
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

### Champion Synergy Traits (2)
| Trait | Champions | Effect |
|-------|-----------|--------|
| **Huntress** | Neeko + Nidalee | While Neeko alive: Nidalee immune to basic attacks + 50% durability |
| **Dark Child** | Annie + Tibbers | Tibbers is a separate unit on bench, inherits Annie's star level |

**Note:** Trait names use display names (e.g., "Arcanist") not backend API names (e.g., "TFT16_Sorcerer").

---

*Last Updated: 2026-02-04*
