# TFT Set 16 Champion Data Review

Generated from CommunityDragon 16.3 + combat_data.json

**Total: 106 champions | Implemented: 60 | Unimplemented: 41**

Status: Y = implemented, **N = needs review**, S = summon/special

## Summons & Special Units (cost 11)

| Status | Champion | Ability | HP | AD | AS | Range | Armor | MR | Mana | Traits | Variables |
|--------|----------|---------|---:|---:|---:|------:|------:|---:|-----:|--------|-----------|
| S | Atakhan | Punish the Unworthy | 320 | 50 | 0.75 | 1 | 0 | 20 | 40/85 |  | Omnivamp, NumAttacksToCleave, CleaveDamage, CleaveHexRange (+9) |
| S | Frozen Tower | Ancient Sentinel | 400 | 0 | 0.2 | 1 | 30 | 30 | 0/0 |  |  |
| S | MalzaharVoidling | Placeholder Name | 500 | 50 | 0.8 | 1 | 20 | 20 | 0/100 |  | DataValue, OtherValue |
| S | Sand Soldier | Stand Guard | 750 | 0 | 0.8 | 1 | 50 | 50 | 0/100 |  | ExplosionDamage |
| S | Tibbers | Rage of Embers | 1500 | 90 | 0.75 | 1 | 80 | 80 | 40/100 | Arcanist | HealPercentHealth, Duration, AttackSpeed, Shield |

## 5-Cost Champions (24)

| Status | Champion | Ability | HP | AD | AS | Range | Armor | MR | Mana | Traits | Variables |
|--------|----------|---------|---:|---:|---:|------:|------:|---:|-----:|--------|-----------|
| Y | Aatrox | The Darkin Blade | 1000 | 65 | 0.9 | 1 | 55 | 55 | 0/20 | Darkin, World Ender, Slayer | APDamage, ADDamage, SunderDuration, SecondCastPercentDamage (+3) |
| Y | Annie | Enraged Inferno | 800 | 30 | 0.8 | 4 | 30 | 30 | 0/160 | Dark Child, Arcanist | Damage, SingleTargetDamage, ManaCostReduction, DamageDuration |
| Y | Aurelion Sol | The Skies Descend | 1100 | 50 | 0.8 | 4 | 40 | 40 | 0/85 | Star Forger, Targon | Damage, InitialHexRadius, Threshold1Damage, Threshold1Radius (+16) |
| **N** | Azir | Arise! | 800 | 35 | 0.8 | 4 | 30 | 30 | 20/40 | Shurima, Emperor, Disruptor | BaseMagicDamage, MaxSummons, MaxSummonsDamage, Duration (+1) |
| Y | Baron Nashor | Wrath of the Void | 3000 | 120 | 0.5 | 2 | 85 | 85 | 0/50 | Void, Riftscourge | APDamage, ADDamage, AcidPercentDamage, NumAcidToShoot (+3) |
| Y | Brock | Seismic Slam | 1800 | 270 | 0.5 | 1 | 60 | 60 | 40/100 | Ixtal | PassivePercentAoE, SlamDamageHealth, SlamDamageBase, StunDuration (+5) |
| Y | Fiddlesticks | Crowstorm | 1200 | 50 | 0.9 | 2 | 60 | 60 | 30/70 | Harvester, Vanquisher | FearDuration, ManaLossPerSecond, DamagePerSecond, AOERadius (+3) |
| Y | Galio | Inspirational Might | 1100 | 50 | 0.9 | 1 | 65 | 65 | 90/140 | Demacia, Heroic | NumAttacks, PassiveMRRatio, Shield, ShieldDuration (+2) |
| Y | Kindred | Lamb's Respite | 900 | 73 | 0.9 | 4 | 40 | 40 | 80/200 | Eternal, Quickstriker | Duration, ADDamage, HealPercentage, HexRadius (+2) |
| Y | Lucian & Senna | The Culling | 900 | 65 | 0.8 | 4 | 40 | 40 | 0/70 | Soulbound, Gunslinger | Duration, APDamage, ADDamage, FlatArmorReduction (+3) |
| Y | Mel | Radiant Eclipse | 900 | 50 | 0.8 | 4 | 30 | 30 | 30/200 | Noxus, Disruptor | NumOfOrbs, PassiveDamage, ManaDrainPerSecond, TargetDamage (+3) |
| **N** | Ornn | Call of the Forge | 900 | 70 | 0.55 | 1 | 55 | 55 | 50/150 | Blacksmith, Warden | Damage, SecondaryDamage, SlowDuration |
| Y | Ryze | Runic Overload | 1000 | 35 | 0.9 | 4 | 40 | 40 | 0/45 | Rune Mage | Damage, SplitPercentDamage, TargonHealPercent, YordleDamageReductionPercent (+23) |
| Y | Sett | The Show Stopper | 1000 | 60 | 0.9 | 1 | 50 | 50 | 10/90 | Ionia, The Boss | AoERadius, FlatAPDamage, PercentOfTargetMaxHealth, PercentAoEDamage (+2) |
| Y | Shyvana | Dragon's Descent / Flame Breath | 1200 | 80 | 0.95 | 1 | 60 | 60 | 0/30 | Dragonborn, Juggernaut | TransformHealth, TransformDurability, DivebombADDamage, FireDamagetADDamagePerSecond (+2) |
| Y | Sylas | Stolen Might | 1600 | 65 | 0.9 | 1 | 80 | 80 | 0/30 | Chainbreaker, Arcanist, Defender | JarvanDamage, JarvanStunDuration, JarvanSearchRadius, GarenDamage (+5) |
| Y | T-Hex | Hextech Arsenal | 1400 | 85 | 0.9 | 2 | 80 | 80 | 30/100 | HexMech, Piltover, Gunslinger | NumBullets, BaseShield, PercentHealthShield, ManaCostPerSecond (+10) |
| Y | Tahm Kench | Devour | 1100 | 70 | 0.55 | 1 | 60 | 60 | 10/90 | Bilgewater, Glutton, Bruiser | Damage, StunDuration, BellyDuration, DamageReduction (+2) |
| Y | Thresh | The Box | 1200 | 60 | 0.85 | 1 | 75 | 75 | 0/40 | Shadow Isles, Warden | APPassiveDamage, HealthDrainPerSoul, HealthDrainSoulBreakpoint, TheBoxDuration (+3) |
| **N** | Volibear | The Relentless Storm | 1200 | 55 | 0.9 | 1 | 60 | 60 | 0/20 | Freljord, Bruiser | BiteDamageHealth, BiteDamageBase, PercentDamageIncrease, SlamDamageMultiplier (+6) |
| Y | Xerath | Eye of the Ascendant | 900 | 40 | 0.8 | 4 | 30 | 30 | 0/135 | Shurima, Ascendant | NumberOfBlasts, Damage, SpellRangeInEnemies, XerathCharmExtraBlasts |
| Y | Zaahen | Divine Challenge | 1200 | 60 | 1.1 | 2 | 80 | 80 | 0/40 | Darkin, Immortal | ADDamage, APDamage, AOEDamageMultiplier, CastsToUlt (+1) |
| Y | Ziggs | Mega Inferno Bomb | 900 | 50 | 0.9 | 6 | 30 | 30 | 0/140 | Zaun, Yordle, Longshot | BABounceNumber, BAPercentAD, BAPercentAP, BombAOERange (+2) |
| Y | Zilean | Visions of the End | 900 | 40 | 0.9 | 4 | 30 | 30 | 0/35 | Chronokeeper, Invoker | MagicDamage, ExplosionDamage, ManaOnKill, MaxDurationBeforeKill |

## 4-Cost Champions (25)

| Status | Champion | Ability | HP | AD | AS | Range | Armor | MR | Mana | Traits | Variables |
|--------|----------|---------|---:|---:|---:|------:|------:|---:|-----:|--------|-----------|
| Y | Ambessa | Lacerate | 1100 | 50 | 0.9 | 1 | 60 | 60 | 0/20 | Noxus, Vanquisher | APDamage, ADDamage, SlamDamageMultiplier, DamageFalloff (+1) |
| **N** | Bel'Veth | Endless Banquet | 1000 | 65 | 0.85 | 2 | 50 | 50 | 0/100 | Void, Slayer | AttackSpeedOnTakedown, ASDuration, ADDamage, PercentMaxHealthGain (+3) |
| **N** | Braum | Unbreakable Frost | 1200 | 50 | 0.6 | 1 | 60 | 60 | 60/105 | Freljord, Warden | DamageReduction, Duration, ChillDuration, APDamage (+6) |
| Y | Diana | Lunar Rush | 1300 | 35 | 0.8 | 1 | 70 | 70 | 0/30 | Targon | Shield, HexLimit, TargetDamage, ShieldDuration (+2) |
| **N** | Fizz | Playful Trickster | 1000 | 30 | 0.9 | 1 | 50 | 50 | 0/10 | Bilgewater, Yordle | Damage, DamageOnHit, NumAttacks, HexRange (+1) |
| **N** | Garen | Judgment | 1200 | 65 | 0.6 | 1 | 60 | 60 | 50/130 | Demacia, Defender | SpinDuration, Durability, ADDamage, ArmorMRReduction (+3) |
| **N** | Kai'Sa | Icathian Rain | 850 | 50 | 0.5 | 6 | 30 | 30 | 0/10 | Assimilator, Void, Longshot | NumMissiles, APDamage, ADDamage, NumTargets (+1) |
| Y | Kalista | Endless Rend | 800 | 50 | 0.85 | 4 | 30 | 30 | 20/65 | Shadow Isles, Vanquisher | ADDamage, APDamage, NumberOfEnemies, BaseSpears (+4) |
| Y | Lissandra | Frozen Tomb | 800 | 30 | 0.75 | 4 | 30 | 30 | 20/70 | Freljord, Invoker | StunDuration, TargetDamage, SecondaryDamage, NumOverkillEnemies (+1) |
| Y | Lux | Final Spark | 800 | 30 | 0.75 | 4 | 30 | 30 | 0/50 | Demacia, Arcanist | PrimaryDamage, SecondaryDamage, QDamage, NumQTargets (+1) |
| Y | Miss Fortune | Heartbreaker | 800 | 55 | 0.75 | 4 | 30 | 30 | 0/30 | Bilgewater, Gunslinger | AutoRicochetMutliplier, BaseNumWaves, NumCaststoGainExtraWave, APDamage (+4) |
| **N** | Nasus | Fury of the Sands | 1500 | 60 | 0.65 | 1 | 70 | 70 | 10/70 | Shurima | HealthSteal, Duration, NumEnemies, Resists (+1) |
| Y | Nidalee | Relentless Pounce | 1100 | 45 | 0.9 | 1 | 70 | 70 | 0/40 | Ixtal, Huntress | TargetDamage, SecondaryDamage, TankDamageMult, FighterDamageMult (+1) |
| Y | Renekton | Slice and Dice | 1400 | 75 | 0.9 | 1 | 70 | 70 | 0/30 | Shurima | DashADDamage, SlashADDamage, SlashAPDamage, DashRange (+5) |
| Y | Rift Herald | Warp Armor | 1100 | 60 | 0.6 | 1 | 60 | 60 | 60/125 | Void, Bruiser | APDamage, BonusDurability, DurabilityPerEnemy, BonusHealth (+3) |
| Y | Seraphine | Grand Encore | 800 | 30 | 0.75 | 4 | 30 | 30 | 0/20 | Piltover, Disruptor | NumTargets, PrimarySpellSearchRadius, DamagePerCrystal, CastBreakpoint (+4) |
| Y | Singed | Poison Trail | 1100 | 15 | 0.7 | 1 | 60 | 60 | 0/80 | Zaun, Juggernaut | PoisonCloudDuration, DamagePerSecond, SpellDuration, ArmorMR (+4) |
| Y | Skarner | Impale | 1400 | 65 | 0.65 | 1 | 70 | 70 | 60/120 | Ixtal | ArmorForAllies, ShieldAmount, ShieldDuration, ImpaleDuration (+2) |
| Y | Swain | Nevermove | 1200 | 40 | 0.65 | 1 | 60 | 60 | 50/145 | Noxus, Arcanist, Juggernaut | PercentMaximumHealthHealing, APHealing, PassiveDamage, StunDuration (+4) |
| Y | Taric | Starlight's Touch | 1300 | 70 | 0.65 | 1 | 70 | 70 | 0/80 | Targon | MRForAllies, InvunerabilityHealthThreshold, PassiveDR, InvunerabilityDuration (+7) |
| Y | Veigar | Dark Storm | 800 | 33 | 0.8 | 4 | 30 | 30 | 0/60 | Yordle, Arcanist | IncreasedAPRatio, NumMeteors, Damage, APPerKill (+2) |
| Y | Warwick | Eternal Hunger | 1200 | 60 | 0.9 | 1 | 60 | 60 | 0/90 | Zaun, Quickstriker | AttackSpeed, ADDamage, Omnivamp, AllyAttackSpeed (+1) |
| Y | Wukong | Diverting Trickster | 1050 | 60 | 0.65 | 1 | 60 | 60 | 30/60 | Ionia, Bruiser | ADDamage, Resists, Duration, SummonMaxHealthPercent (+1) |
| Y | Yone | Kin of the Stained Blade | 1100 | 20 | 0.9 | 1 | 60 | 60 | 30/100 | Ionia, Slayer | BasicAttackADDamage, BasicAttackAPDamage, StrikeADDamage, StrikeAPDamage (+7) |
| Y | Yunara | Transcendent State | 800 | 60 | 0.8 | 4 | 30 | 30 | 0/50 | Ionia, Quickstriker | BuffDuration, AttackSpeed, ADDamage, DamageReductionPerEnemyHit (+1) |

## 3-Cost Champions (18)

| Status | Champion | Ability | HP | AD | AS | Range | Armor | MR | Mana | Traits | Variables |
|--------|----------|---------|---:|---:|---:|------:|------:|---:|-----:|--------|-----------|
| **N** | Ahri | Fox-Fire | 650 | 30 | 0.8 | 4 | 25 | 25 | 0/30 | Ionia, Arcanist | Damage, NormalNumBolts, SpecialCastNumBolts, NumCasts (+3) |
| Y | Darius | Decimate | 900 | 50 | 0.65 | 1 | 50 | 50 | 20/65 | Noxus, Defender | PercentMaximumHealthHealing, APHealing, ADDamage, PhysicalDamagePerSecond (+3) |
| **N** | Dr. Mundo | Maximum Dosage | 900 | 50 | 0.6 | 1 | 50 | 50 | 0/60 | Zaun, Bruiser | Duration, PercentHealthHealingPerSecond, APHealPerSecond, HealTickRate (+2) |
| Y | Draven | Spinning Axes | 650 | 58 | 0.75 | 4 | 25 | 25 | 60/100 | Noxus, Quickstriker | GoldAmount, ADDamage, BaseDamage, TotalTakedown |
| Y | Gangplank | Powder Kegs | 850 | 45 | 0.8 | 1 | 55 | 55 | 0/50 | Bilgewater, Slayer, Vanquisher | ADDamage, APDamage, NumofBarrels, FalloffDamage (+2) |
| Y | Gwen | Snip Snip! | 850 | 40 | 0.8 | 2 | 55 | 55 | 0/30 | Shadow Isles, Disruptor | SnipCount, SnipPerSoulBreakpoint, SoulBreakpoint, Damage (+3) |
| **N** | Jinx | Switcheroo! | 650 | 50 | 0.75 | 4 | 25 | 25 | 0/18 | Zaun, Gunslinger | ADDamage, APDamage, NumAttacks, NumMissiles |
| **N** | Kennen | Slicing Maelstrom | 900 | 50 | 0.65 | 1 | 50 | 50 | 70/125 | Ionia, Yordle, Defender | Shield, Damage, Duration, NumBolts (+5) |
| **N** | Kobuko & Yuumi | You & Me! | 950 | 20 | 0.65 | 1 | 50 | 50 | 30/90 | Yordle, Bruiser, Invoker | YuumiCadence, YuumiHeal, YuumiAS, ASDuration (+4) |
| Y | LeBlanc | Distortions | 650 | 35 | 0.75 | 4 | 25 | 25 | 0/60 | Noxus, Invoker | NumTargets, Damage, SecondaryDamage, NearbyEnemyHexRadius (+1) |
| Y | Leona | Solar Flare | 1000 | 50 | 0.65 | 1 | 60 | 60 | 70/120 | Targon | FlatDR, NumEnemies, StunDuration, Damage (+3) |
| Y | Loris | Piltover Tussle | 950 | 60 | 0.6 | 1 | 50 | 50 | 70/140 | Piltover, Warden | Shield, Damage, KnockupDuration, ShieldDuration |
| Y | Malzahar | Void Swarm | 650 | 30 | 0.8 | 4 | 25 | 25 | 0/35 | Void, Disruptor | NumMinions, NumAttacks, Damage, MinionDuration (+1) |
| Y | Milio | Ultra Mega Fire Kick!!! | 650 | 30 | 0.75 | 4 | 30 | 30 | 0/60 | Ixtal, Invoker | NumBounces, MagicDamage, MagicDamageAOE, HexRange (+1) |
| **N** | Nautilus | Titan's Wrath | 900 | 50 | 0.6 | 1 | 50 | 50 | 60/120 | Bilgewater, Juggernaut, Warden | APShield, PercentHealthShield, ShieldDuration, MRDamageRatio (+1) |
| **N** | Sejuani | Winter's Wrath | 900 | 60 | 0.6 | 1 | 50 | 50 | 40/80 | Freljord, Defender | Shield, ShieldDuration, Damage, ChillDuration (+5) |
| Y | Vayne | Tumble | 650 | 70 | 0.9 | 6 | 25 | 25 | 0/40 | Demacia, Longshot | APDamage, ADDamage, HexDashRange |
| **N** | Zoe | Double Trouble Bubble | 800 | 35 | 0.8 | 4 | 25 | 25 | 30/60 | Targon | ShredDuration, NumEnemies, Damage, SlowDuration |

## 2-Cost Champions (19)

| Status | Champion | Ability | HP | AD | AS | Range | Armor | MR | Mana | Traits | Variables |
|--------|----------|---------|---:|---:|---:|------:|------:|---:|-----:|--------|-----------|
| Y | Aphelios | Incendiary Onslaught | 650 | 20 | 0.75 | 4 | 20 | 20 | 0/40 | Targon | NumAttacks, NumTargets, AttackSpeed, SeverumADDamage (+3) |
| **N** | Ashe | True Ice Arrow | 550 | 53 | 0.7 | 4 | 20 | 20 | 20/80 | Freljord, Quickstriker | APDamage, ADDamage, AOEPercent, Duration (+3) |
| Y | Bard | Traveler's Call | 750 | 30 | 0.75 | 4 | 20 | 20 | 0/55 | Caretaker | Damage, NumMissilesBase, PercentDamageOnCurrentTarget, EnemyHexSearchRadius |
| **N** | Cho'Gath | Rupture | 850 | 50 | 0.6 | 1 | 45 | 45 | 40/100 | Void, Juggernaut | KnockupDuration, APDamage, PercentMaximumHealthDamage, DelayTime (+1) |
| **N** | Ekko | Parallel Convergence | 750 | 35 | 0.85 | 1 | 45 | 45 | 0/40 | Zaun, Disruptor | HexRange, Duration, BaseBonusMagicDamage, BaseMagicDamage (+1) |
| **N** | Graves | Collateral Damage | 700 | 50 | 0.7 | 2 | 45 | 45 | 0/50 | Bilgewater, Gunslinger | ADDamage, APDamage, AttackDamageMultiplier, BonusAS (+1) |
| **N** | Neeko | Pop Blossom | 850 | 50 | 0.6 | 1 | 45 | 45 | 15/65 | Ixtal, Arcanist, Defender | Shield, ShieldDuration, Damage, ChillDuration |
| **N** | Orianna | Command: Protect | 550 | 30 | 0.7 | 4 | 20 | 20 | 20/50 | Piltover, Invoker | ShieldDuration, TargetDamage, ExplosionDamage, Shield (+1) |
| **N** | Poppy | Hammer Shock | 850 | 50 | 0.7 | 1 | 45 | 45 | 40/80 | Demacia, Yordle, Juggernaut | PrimaryDamage, KnockupDuration, KnockupDelay, ShieldAmt (+3) |
| **N** | Rek'Sai | Burrow | 750 | 50 | 0.85 | 1 | 45 | 45 | 0/30 | Void, Vanquisher | APDamage, ADDamage, SpellAttackDamage, NumAttacks (+1) |
| **N** | Sion | Soul Furnace | 650 | 50 | 0.55 | 1 | 40 | 40 | 0/70 | Noxus, Bruiser | HealthPerTakedown, PercentHealthShield, APShield, DamagePercentHealth (+1) |
| **N** | Teemo | Toxic Dart | 550 | 35 | 0.75 | 6 | 20 | 20 | 0/30 | Yordle, Longshot | PrimaryDamage, DOtDuration, DamagePerSecond |
| **N** | Tristana | Buster Shot | 550 | 55 | 0.75 | 4 | 20 | 20 | 0/50 | Yordle, Gunslinger | ADDamage, APDamage, HexKnockback, StunDuration (+1) |
| **N** | Tryndamere | Undying Rage | 750 | 60 | 0.75 | 1 | 45 | 45 | 0/50 | Freljord, Slayer | ADDamage, Duration, DR, ArmorIgnore (+2) |
| **N** | Twisted Fate | Stacked Deck | 550 | 50 | 0.75 | 4 | 20 | 20 | 0/3 | Bilgewater, Quickstriker | BonusAPDamage, NumAttacks, BaseDamage, LineRange (+4) |
| **N** | Vi | Relentless Force | 700 | 60 | 0.85 | 1 | 40 | 40 | 0/30 | Piltover, Zaun, Defender | Shield, ShieldDuration, ADDamage, KnockupDuration (+3) |
| Y | Xin Zhao | Three Talon Strike | 850 | 50 | 0.65 | 1 | 45 | 45 | 15/70 | Demacia, Ionia, Warden | ADDamage, Heal, StunDuration |
| Y | Yasuo | Sweeping Blade | 750 | 45 | 0.8 | 1 | 45 | 45 | 0/30 | Ionia, Slayer | ADDamage, APDamage, YasuoADPercent, AttributeBrothersDamageToYasuo |
| Y | Yorick | Mourning Mist | 850 | 60 | 0.6 | 1 | 45 | 45 | 15/75 | Shadow Isles, Warden | PercentHealthDamage, FlatDamage, HealPerSoulBreakpoint, SoulBreakpoint (+4) |

## 1-Cost Champions (15)

| Status | Champion | Ability | HP | AD | AS | Range | Armor | MR | Mana | Traits | Variables |
|--------|----------|---------|---:|---:|---:|------:|------:|---:|-----:|--------|-----------|
| **N** | Anivia | Frostbite | 500 | 30 | 0.75 | 4 | 20 | 20 | 0/40 | Freljord, Invoker | Damage, ManaRefund |
| **N** | Blitzcrank | Static Field | 700 | 50 | 0.55 | 1 | 40 | 40 | 60/105 | Zaun, Juggernaut | Shield, Duration, HexRadius, MRDamageRatio |
| **N** | Briar | Blood Frenzy | 650 | 42 | 0.75 | 1 | 35 | 35 | 0/40 | Noxus, Slayer, Juggernaut | HexSearchRadius, BonusAD, DecayingAttackSpeed, Duration |
| Y | Caitlyn | Ace in the Hole | 500 | 45 | 0.75 | 6 | 15 | 15 | 0/80 | Piltover, Longshot | ADDamage, APDamage |
| Y | Illaoi | Tentacle Smash | 700 | 50 | 0.6 | 1 | 40 | 40 | 40/100 | Bilgewater, Bruiser | APHeal, PercentHealthHeal, Damage |
| **N** | Jarvan IV | Demacian Standard | 700 | 55 | 0.6 | 1 | 40 | 40 | 30/100 | Demacia, Defender | Shield, ShieldDuration, AttackSpeed, AttackSpeedDuration |
| **N** | Jhin | Curtain Call | 444 | 44 | 0.7 | 4 | 24 | 24 | 0/70 | Ionia, Gunslinger | ADDamage, APDamage, FourthShotDamageMult, SpellFixedAS |
| **N** | Kog'Maw | Caustic Spittle | 500 | 20 | 0.7 | 6 | 15 | 15 | 0/30 | Void, Arcanist, Longshot | Damage, ArmorReduction, PercentToSecondaryEnemies |
| **N** | Lulu | Whimsy | 500 | 25 | 0.7 | 4 | 15 | 15 | 20/70 | Yordle, Arcanist | Damage, StunDuration, SecondaryDamage |
| S | Piltover Invention | Piltover Customs Special | 1 | 65 | 0.9 | 33 | 65 | 65 | 0/0 |  |  |
| **N** | Qiyana | Clear The Brush | 650 | 42 | 0.75 | 1 | 35 | 35 | 0/30 | Ixtal, Slayer | HexDistance, ADDamage, APDamage, DashHexRange |
| Y | Rumble | Junkyard Titan | 700 | 45 | 0.6 | 1 | 40 | 40 | 40/110 | Yordle, Defender | APShield, Duration, PercentArmorDamage |
| **N** | Shen | Stand United | 700 | 65 | 0.65 | 1 | 40 | 40 | 30/90 | Ionia, Bruiser | Shield, Duration |
| **N** | Sona | Power Chord | 500 | 20 | 0.7 | 4 | 15 | 15 | 0/30 | Demacia, Invoker | Damage, HealAmount, NumEnemies |
| Y | Viego | Blade of the Ruined King | 650 | 40 | 0.75 | 1 | 35 | 35 | 0/30 | Shadow Isles, Quickstriker | ADDamage, StackingDamage, SoulsForAttackSpeed, AttackSpeedPerSoulBreakpoint (+1) |

---

## Unimplemented Champions (Quick Reference)

### 5-Cost (3)
- **Azir** - Arise! (5 vars: BaseMagicDamage, MaxSummons, MaxSummonsDamage, Duration, XerathZapAttacksRequired)
- **Ornn** - Call of the Forge (3 vars: Damage, SecondaryDamage, SlowDuration)
- **Volibear** - The Relentless Storm (10 vars: BiteDamageHealth, BiteDamageBase, PercentDamageIncrease, SlamDamageMultiplier, StormbringerBonusHealth, StormbringerAS)

### 4-Cost (6)
- **Bel'Veth** - Endless Banquet (7 vars: AttackSpeedOnTakedown, ASDuration, ADDamage, PercentMaxHealthGain, TrueDamagePerStack, TrueDamageBase)
- **Braum** - Unbreakable Frost (10 vars: DamageReduction, Duration, ChillDuration, APDamage, ArmorDamage, EnemyAttackCooldown)
- **Fizz** - Playful Trickster (5 vars: Damage, DamageOnHit, NumAttacks, HexRange, ASBoost)
- **Garen** - Judgment (7 vars: SpinDuration, Durability, ADDamage, ArmorMRReduction, PercentofHealImmediately, APHeal)
- **Kai'Sa** - Icathian Rain (5 vars: NumMissiles, APDamage, ADDamage, NumTargets, PercentMissilesOnCurrentTarget)
- **Nasus** - Fury of the Sands (5 vars: HealthSteal, Duration, NumEnemies, Resists, PercentHealthDamagePerSecond)

### 3-Cost (8)
- **Ahri** - Fox-Fire (7 vars: Damage, NormalNumBolts, SpecialCastNumBolts, NumCasts, NearbyEnemyHexRadius, NumNearbyEnemies)
- **Dr. Mundo** - Maximum Dosage (6 vars: Duration, PercentHealthHealingPerSecond, APHealPerSecond, HealTickRate, ADDamage, PercentMaximumHealthDamage)
- **Jinx** - Switcheroo! (4 vars: ADDamage, APDamage, NumAttacks, NumMissiles)
- **Kennen** - Slicing Maelstrom (9 vars: Shield, Damage, Duration, NumBolts, BoltLimit, MaxStuns)
- **Kobuko & Yuumi** - You & Me! (8 vars: YuumiCadence, YuumiHeal, YuumiAS, ASDuration, SelfHealAP, SelfHealHealthPercent)
- **Nautilus** - Titan's Wrath (5 vars: APShield, PercentHealthShield, ShieldDuration, MRDamageRatio, PassiveTimer)
- **Sejuani** - Winter's Wrath (9 vars: Shield, ShieldDuration, Damage, ChillDuration, SwipeA_HalfLength, SwipeA_HalfWidth)
- **Zoe** - Double Trouble Bubble (4 vars: ShredDuration, NumEnemies, Damage, SlowDuration)

### 2-Cost (14)
- **Ashe** - True Ice Arrow (7 vars: APDamage, ADDamage, AOEPercent, Duration, TrueDamageHealthBreakpoint, SmallArrowDamage)
- **Cho'Gath** - Rupture (5 vars: KnockupDuration, APDamage, PercentMaximumHealthDamage, DelayTime, Heal)
- **Ekko** - Parallel Convergence (5 vars: HexRange, Duration, BaseBonusMagicDamage, BaseMagicDamage, DamageRatio)
- **Graves** - Collateral Damage (5 vars: ADDamage, APDamage, AttackDamageMultiplier, BonusAS, TFBonusAP)
- **Neeko** - Pop Blossom (4 vars: Shield, ShieldDuration, Damage, ChillDuration)
- **Orianna** - Command: Protect (5 vars: ShieldDuration, TargetDamage, ExplosionDamage, Shield, SearchRange)
- **Poppy** - Hammer Shock (7 vars: PrimaryDamage, KnockupDuration, KnockupDelay, ShieldAmt, ShieldDuration, NumShieldedAllies)
- **Rek'Sai** - Burrow (5 vars: APDamage, ADDamage, SpellAttackDamage, NumAttacks, EnemySearchDistance)
- **Sion** - Soul Furnace (5 vars: HealthPerTakedown, PercentHealthShield, APShield, DamagePercentHealth, ShieldDuration)
- **Teemo** - Toxic Dart (3 vars: PrimaryDamage, DOtDuration, DamagePerSecond)
- **Tristana** - Buster Shot (5 vars: ADDamage, APDamage, HexKnockback, StunDuration, KnockbackRadius)
- **Tryndamere** - Undying Rage (6 vars: ADDamage, Duration, DR, ArmorIgnore, AttackSpeed_MustMatchTFT16_Tryndamere_PassiveAS, TryndASBoostFromAshe)
- **Twisted Fate** - Stacked Deck (8 vars: BonusAPDamage, NumAttacks, BaseDamage, LineRange, LineWidth, FalloffDamage)
- **Vi** - Relentless Force (7 vars: Shield, ShieldDuration, ADDamage, KnockupDuration, HexRange, ThirdCastHexRange)

### 1-Cost (10)
- **Anivia** - Frostbite (2 vars: Damage, ManaRefund)
- **Blitzcrank** - Static Field (4 vars: Shield, Duration, HexRadius, MRDamageRatio)
- **Briar** - Blood Frenzy (4 vars: HexSearchRadius, BonusAD, DecayingAttackSpeed, Duration)
- **Jarvan IV** - Demacian Standard (4 vars: Shield, ShieldDuration, AttackSpeed, AttackSpeedDuration)
- **Jhin** - Curtain Call (4 vars: ADDamage, APDamage, FourthShotDamageMult, SpellFixedAS)
- **Kog'Maw** - Caustic Spittle (3 vars: Damage, ArmorReduction, PercentToSecondaryEnemies)
- **Lulu** - Whimsy (3 vars: Damage, StunDuration, SecondaryDamage)
- **Qiyana** - Clear The Brush (4 vars: HexDistance, ADDamage, APDamage, DashHexRange)
- **Shen** - Stand United (2 vars: Shield, Duration)
- **Sona** - Power Chord (3 vars: Damage, HealAmount, NumEnemies)
