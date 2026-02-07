"""
TFT Set 16 Item Database

Contains all item categories:
- Base craftable items (components + completed)
- Artifact items (from Ornn/Blacksmith)
- Radiant items (upgraded versions)
- Emblem items (trait spatulas)
- Piltover modules (2/4/6 tier rewards)
- Bilgewater store items

Stats format:
- ad: percentage bonus (0.35 = 35% bonus AD)
- ap: flat ability power
- attack_speed: percentage (0.15 = 15% AS)
- armor/magic_resist: flat values
- hp: flat health
- crit_chance: percentage (0.35 = 35%)
- crit_multiplier: bonus (0.10 = +10% crit damage)
- damage_amp: percentage (0.15 = 15% more damage)
- omnivamp: percentage (0.20 = 20% healing from damage)
"""

# =============================================================================
# BASE CRAFTABLE ITEMS
# =============================================================================

BASE_COMPONENTS = {
    "BFSword": {"ad": 0.10},
    "RecurveBow": {"attack_speed": 0.10},
    "NeedlesslyLargeRod": {"ap": 10},
    "TearOfTheGoddess": {"mana_regen": 1},
    "ChainVest": {"armor": 20},
    "NegatronCloak": {"magic_resist": 20},
    "GiantsBelt": {"hp": 150},
    "Spatula": {},
    "SparringGloves": {"crit_chance": 0.20},
}

BASE_COMPLETED = {
    # AD Items
    "Deathblade": {"ad": 0.55, "damage_amp": 0.10},
    "InfinityEdge": {"ad": 0.35, "crit_chance": 0.35, "crit_multiplier": 0.10},
    "GiantSlayer": {"ad": 0.15, "ap": 15, "attack_speed": 0.15, "damage_amp": 0.15},
    "LastWhisper": {"ad": 0.15, "attack_speed": 0.20, "crit_chance": 0.20},
    "Bloodthirster": {"ad": 0.15, "ap": 15, "magic_resist": 20, "omnivamp": 0.20},
    "SteraksGage": {"ad": 0.40, "hp": 300},
    "EdgeOfNight": {"ad": 0.10, "ap": 10, "attack_speed": 0.15, "armor": 20},

    # Attack Speed Items
    "RedBuff": {"attack_speed": 0.45, "damage_amp": 0.06},  # Burn effect
    "GuinsoosRageblade": {"ap": 10, "attack_speed": 0.10},  # Stacking AS
    "KrakensFury": {"ad": 0.10, "attack_speed": 0.10, "magic_resist": 20},  # Stacking AD
    "TitansResolve": {"attack_speed": 0.10, "armor": 20},  # Stacking stats
    "NashorsTooth": {"ap": 18, "attack_speed": 0.10, "crit_chance": 0.20, "hp": 150},

    # AP Items
    "RabadonsDeathcap": {"ap": 50, "damage_amp": 0.15},
    "JeweledGauntlet": {"ap": 35, "crit_chance": 0.35, "crit_multiplier": 0.10},
    "HextechGunblade": {"ad": 0.20, "ap": 20, "omnivamp": 0.15, "mana_regen": 1},
    "SpearOfShojin": {"ad": 0.15, "ap": 15, "mana_regen": 1},  # Mana on cast
    "BlueBuff": {"ad": 0.15, "ap": 15, "mana_regen": 1},  # +10% AD/AP amp (combat_start)
    "Morellonomicon": {"ap": 20, "hp": 150, "mana_regen": 1},  # Burn + anti-heal
    "ArchangelsStaff": {"ap": 30, "mana_regen": 1},  # Stacking AP
    "IonicSpark": {"ap": 15, "hp": 250, "magic_resist": 35},  # MR shred aura
    "VoidStaff": {"ap": 35, "attack_speed": 0.15, "mana_regen": 1},  # MR shred on hit

    # Tank Items
    "WarmogsArmor": {"hp": 500, "bonus_hp_pct": 0.18},  # +18% max HP
    "GargoyleStoneplate": {"armor": 30, "magic_resist": 30, "hp": 100},
    "SunfireCape": {"armor": 20, "hp": 150, "bonus_hp_pct": 0.08},  # +8% max HP, AOE burn
    "DragonsClaw": {"magic_resist": 75, "bonus_hp_pct": 0.09},  # +9% max HP
    "BrambleVest": {"armor": 65, "bonus_hp_pct": 0.09},  # +9% max HP, reflect damage
    "SpiritVisage": {"hp": 300, "mana_regen": 2},  # Missing HP heal
    "SteadfastHeart": {"armor": 20, "crit_chance": 0.20, "hp": 250},
    "ProtectorsVow": {"armor": 25, "magic_resist": 25, "mana_regen": 1},  # Shield
    "Evenshroud": {"hp": 250, "magic_resist": 20},  # Resist shred aura

    # Utility Items
    "Quicksilver": {"attack_speed": 0.15, "crit_chance": 0.20, "magic_resist": 20},
    "Crownguard": {"ap": 20, "armor": 20, "hp": 100},  # Shield on cast
    "HandOfJustice": {"crit_chance": 0.20, "mana_regen": 1},  # Heal or damage
    "AdaptiveHelm": {"magic_resist": 20, "mana_regen": 3},
    "ThiefsGloves": {"crit_chance": 0.20, "hp": 150},
    "StrikersFlail": {"attack_speed": 0.10, "crit_chance": 0.20, "hp": 150},
    "TacticiansCrown": {},   # +1 max team size (Spatula + Spatula)
    "TacticiansCape": {},    # +1 max team size (Spatula + Frying Pan)
    "TacticiansShield": {},  # +1 max team size (Frying Pan + Frying Pan)

    # Legacy API name aliases - these are internal Riot API names for existing items.
    # Kept for backward compatibility with test/fetch code that references old names.
    # Source: metatft.com, wiki.leagueoflegends.com (API names map to display names)
    # Stats are NOT duplicated here - lookups redirect via ITEM_ALIASES below.
}

# =============================================================================
# ARTIFACT ITEMS (from Ornn/Blacksmith)
# =============================================================================

ARTIFACT_ITEMS = {
    # --- Returning items (stats verified against vntft.com Set 16) ---
    "AegisOfDawn": {"armor": 50, "hp": 200},  # Every 2.5s steal 5 Armor within 1 hex, heal 15x holder Armor
    "AegisOfDusk": {"magic_resist": 70, "hp": 200},  # Every 2.5s steal 5 MR within 1 hex, deal 15x holder MR
    "BlightingJewel": {"ap": 60, "mana_regen": 2},  # Magic damage reduces target MR by 2, if MR=0 grant 2 Mana
    "CappaJuice": {"ad": 0.25, "ap": 25, "attack_speed": 0.20},  # +1% AD/AP per Hat on takedown, -20% hats on death
    "Dawncore": {"ad": 0.10, "ap": 15},  # Reduce max Mana by 10, subsequent casts -10% max Mana (min 10)
    "EternalPact": {"ap": 40, "mana_regen": 1},  # Pact with highest HP ally; +10 mana regen +40% AP if they die
    "Fishbones": {"ad": 0.50, "attack_speed": 0.50},  # Attacks target random enemies
    "HellfireHatchet": {"ad": 0.20, "hp": 150, "omnivamp": 0.20},  # 2% max HP bonus phys on attacks, +1% AS per 1% missing HP
    "HorizonFocus": {"armor": 20, "hp": 250, "magic_resist": 20, "mana_regen": 2},  # Stun → 30% max HP magic damage
    "LesserMirroredPersona": {"ad": 0.10, "ap": 10, "attack_speed": 0.10, "armor": 10, "hp": 100, "magic_resist": 10},
    "LichBane": {"ap": 55, "attack_speed": 0.10},  # First attack after cast: bonus magic damage (scales with stage)
    "LightshieldCrest": {"armor": 55, "magic_resist": 55},  # Every 3s shield lowest HP ally for 70% combined resists
    "LudensTempest": {"ad": 0.50, "ap": 50},  # 100% overkill + 100 as magic damage to 3 nearest enemies
    "MirroredPersona": {"ad": 0.10, "ap": 10, "attack_speed": 0.10, "armor": 10, "hp": 100, "magic_resist": 10},
    "Mittens": {"attack_speed": 0.65},  # Shrinks holder, +move speed, immune to Chill/Burn/Wound
    "ProwlersClaw": {"ad": 0.35, "crit_chance": 0.45, "hp": 200},  # On kill: cleanse + dash, next 2 crits +50% crit damage
    "RapidFirecannon": {"attack_speed": 0.65},  # +1 range, +1 more per kill
    "SeekersArmguard": {"ap": 25, "armor": 10, "magic_resist": 10, "omnivamp": 0.20},  # Takedowns: +20 Armor/MR/AP
    "SilvermereDawn": {"ad": 1.40, "armor": 80, "magic_resist": 80},  # Stun immune, attacks stun 0.8s, AS locked 0.5
    "StatikkShiv": {"ap": 15, "attack_speed": 0.50},  # Every 3rd attack: 30+40% AP magic damage to 4 enemies
    "TalismanOfAscension": {"hp": 450, "ap": 20, "ad": 0.20},  # After 22s: +100% max HP, +120% damage amp
    "TheIndomitable": {"hp": 500, "armor": 20, "magic_resist": 20},  # -move speed, +15% max HP, stun immune, pull target
    "TitanicHydra": {"hp": 300, "ad": 0.20, "attack_speed": 0.20},  # 3% max HP + 8% AD as bonus phys to target + adjacent
    "VoidGauntlet": {"hp": 300},  # Combat start: store 30% max HP (+2.5%/s). On death: stored HP as magic damage in 4 hexes
    "WitsEnd": {"hp": 400, "armor": 20, "magic_resist": 20, "attack_speed": 0.25},  # On-hit magic damage (scales), heal 30% magic dealt
    "ZhonyasParadox": {"ap": 25, "armor": 25, "magic_resist": 25},  # At 40% HP: invulnerable 3s (once)

    # --- New Set 16 artifacts ---
    "DeathfireGrasp": {"ap": 50},  # Combat start: 20% max HP magic damage, +25% damage amp 10s (+35% vs target)
    "DeathsDefiance": {"ad": 0.25, "armor": 40, "attack_speed": 0.15, "omnivamp": 0.25},  # 50% damage dealt over 4s (non-lethal)
    "Flickerblade": {"ap": 10, "attack_speed": 0.12},  # +6% stacking AS, every 5 attacks +2% AD/AP
    "GamblersBlade": {"attack_speed": 0.45},  # +1% AS per gold (up to 30). 6% chance to drop 1 gold on attack
    "GoldCollector": {"ad": 0.40, "crit_chance": 0.20},  # Execute below 12% HP, 33% chance to drop gold
    "Hullcrusher": {"armor": 50, "magic_resist": 50},  # No adjacent allies: +400 HP, +10% AD, +10% AP
    "InfinityForce": {"hp": 300},  # +30% AD, +30 AP, +30 Armor, +30 MR, +30% AS (in effect)
    "Manazane": {"ad": 0.15, "ap": 10, "attack_speed": 0.10},  # After first cast: +120 Mana over 5s
    "MogulsMail": {"hp": 300},  # +1 Armor/MR +5 HP per hit taken (35 stacks), full stacks: 1 gold/12s
    "SnipersFocus": {"ad": 0.25, "ap": 25, "attack_speed": 0.20},  # +2 range, +9% damage amp per hex distance
    "TrickstersGlass": {"armor": 10, "magic_resist": 10, "attack_speed": 0.10, "crit_chance": 0.15},  # Clone 70% HP +30% mana
    "TheDarkinAegis": {"hp": 200, "armor": 25, "magic_resist": 25},  # Darkin. 1% max HP/s aura, 2% heal on deaths
    "TheDarkinBow": {"ad": 0.10, "attack_speed": 0.25},  # Darkin. Every 10 attacks: 500% AD arrow
    "TheDarkinScythe": {"hp": 250, "ad": 0.25},  # Darkin. Every 4s: 200% AD slash adjacent
    "TheDarkinStaff": {"ap": 40, "mana_regen": 2},  # Darkin. Per 20 mana spent: tendril 50 magic damage
}

# =============================================================================
# RADIANT ITEMS (upgraded versions)
# =============================================================================

RADIANT_ITEMS = {
    # Radiant versions have ~50% more stats than base
    "RadiantDeathblade": {"ad": 0.80, "damage_amp": 0.15},
    "RadiantInfinityEdge": {"ad": 0.50, "crit_chance": 0.50, "crit_multiplier": 0.15},
    "RadiantGiantSlayer": {"ad": 0.25, "ap": 25, "attack_speed": 0.25, "damage_amp": 0.25},
    "RadiantLastWhisper": {"ad": 0.25, "attack_speed": 0.30, "crit_chance": 0.30},
    "RadiantBloodthirster": {"ad": 0.25, "ap": 25, "magic_resist": 30, "omnivamp": 0.30},
    "RadiantRabadonsDeathcap": {"ap": 75, "damage_amp": 0.25},
    "RadiantJeweledGauntlet": {"ap": 50, "crit_chance": 0.50, "crit_multiplier": 0.15},
    "RadiantWarmogsArmor": {"hp": 800},
    "RadiantGargoyleStoneplate": {"armor": 40, "magic_resist": 40, "hp": 200},
    "RadiantDragonsClaw": {"magic_resist": 120},
    "RadiantBrambleVest": {"armor": 100},
    "RadiantSpearOfShojin": {"ad": 0.25, "ap": 25, "mana_regen": 2},
    "RadiantGuinsoosRageblade": {"ap": 20, "attack_speed": 0.20},
    "RadiantBlueBuff": {"ad": 0.25, "ap": 25, "mana_regen": 8},
    "RadiantEdgeOfNight": {"ad": 0.15, "ap": 15, "attack_speed": 0.25, "armor": 30},  # Untargetable + full heal at 60% HP
}

# =============================================================================
# EMBLEM ITEMS (trait spatulas)
# =============================================================================

# 22 emblems - stats verified against vntft.com Set 16
EMBLEM_ITEMS = {
    "BilgewaterEmblem": {"mana_regen": 1},
    "BruiserEmblem": {"hp": 250},
    "DefenderEmblem": {"armor": 30, "magic_resist": 30},
    "DemaciaEmblem": {"armor": 25, "magic_resist": 25, "mana_regen": 3},
    "FreljordEmblem": {"hp": 400},
    "GunslingerEmblem": {"ad": 0.20, "hp": 150},
    "InvokerEmblem": {"mana_regen": 3},
    "IoniaEmblem": {"ad": 0.25, "ap": 25},
    "IxtalEmblem": {"hp": 250},
    "JuggernautEmblem": {"armor": 30, "magic_resist": 30},
    "LongshotEmblem": {"hp": 150, "attack_speed": 0.20},
    "MagusEmblem": {"hp": 150, "attack_speed": 0.20},  # JSONL: MagusEmblemItem = Disruptor
    "NoxusEmblem": {"ad": 0.25, "ap": 25},
    "PiltoverEmblem": {"hp": 150},
    "QuickstrikerEmblem": {"attack_speed": 0.25},  # JSONL: RapidfireEmblemItem
    "SlayerEmblem": {"ad": 0.20},
    "SorcererEmblem": {"ap": 25},  # Display: Arcanist Emblem
    "VanquisherEmblem": {"ad": 0.15, "ap": 15, "crit_chance": 0.20},
    "VoidEmblem": {"ad": 0.10, "ap": 10, "attack_speed": 0.20},
    "WardenEmblem": {"hp": 250},
    "YordleEmblem": {"ad": 0.20, "ap": 20, "armor": 30, "magic_resist": 30},
    "ZaunEmblem": {"hp": 350, "crit_chance": 0.20},
}

# Emblem name → display trait name it grants (for trait counting in combat)
# Verified: 22 emblems matching items.jsonl. NO Shadow Isles, Targon,
# Harvester, Disruptor, or Shurima emblems exist in the game.
EMBLEM_TO_TRAIT = {
    "BilgewaterEmblem": "bilgewater",
    "BruiserEmblem": "bruiser",
    "DefenderEmblem": "defender",
    "DemaciaEmblem": "demacia",
    "FreljordEmblem": "freljord",
    "GunslingerEmblem": "gunslinger",
    "InvokerEmblem": "invoker",
    "IoniaEmblem": "ionia",
    "IxtalEmblem": "ixtal",
    "JuggernautEmblem": "juggernaut",
    "LongshotEmblem": "longshot",
    "MagusEmblem": "disruptor",  # TFT16_Magus API name = Disruptor trait
    "NoxusEmblem": "noxus",
    "PiltoverEmblem": "piltover",
    "QuickstrikerEmblem": "quickstriker",
    "SlayerEmblem": "slayer",
    "SorcererEmblem": "arcanist",  # Sorcerer emblem grants Arcanist trait
    "VanquisherEmblem": "vanquisher",
    "VoidEmblem": "void",
    "WardenEmblem": "warden",
    "YordleEmblem": "yordle",
    "ZaunEmblem": "zaun",
}

# =============================================================================
# PILTOVER MODULES (trait rewards at 2/4/6)
# =============================================================================

# Piltover modules fire at combat start after 8 seconds
# Tier 1 (2 Piltover): Basic modules
# Tier 2 (4 Piltover): Better modules
# Tier 3 (6 Piltover): Best modules + T-Hex upgrades

PILTOVER_MODULES = {
    # Tier 1-2 modules
    "AccelerationGate": {"effect": "Piltover units restore 35% max mana over 2s after cast"},
    "ArmorNullifier": {"effect": "Piltover deal 25% more damage, 45% vs tanks"},  # 16.3: tank amp 35%→45%
    "BlastShield": {"effect": "All allies gain 18% max HP shield"},  # 16.4: 20%→18%
    "ContinuumCogs": {"effect": "All allies gain 2 mana regen and 15 AP"},  # 16.3: 12→15 AP
    "EMP": {"effect": "Increase enemy mana costs by 15"},
    "GigantificationRay": {"effect": "Piltover gain 28% max HP and grow larger"},  # 16.4: 23%→28%
    "KineticBarrier": {"effect": "Piltover gain 65 Armor and 30 MR (or opposite)"},  # 16.4: 60/20→65/30
    "MagnetronCoil": {"effect": "Piltover gain 18% damage amp + 1% per cast"},
    "MomentumDrive": {"effect": "Cleanse CC, team gains 50% tenacity"},
    "OverclockedCapacitors": {"effect": "Team gains 25% attack speed"},  # 16.4: 22%→25%
    "TunedOscillator": {"effect": "Increase healing/shielding by 28%"},  # 16.4: 25%→28%

    # Tier 2-3 modules
    "ElectricalOverload": {"effect": "Deal 100 + 10% max HP true damage to all enemies"},
    "MicroRockets": {"effect": "Fire missiles dealing 66% of Piltover damage dealt"},
    "MiningDrill": {"effect": "Gain 1 gold or 1 Boot per Piltover cast"},
    "90CaliberNets": {"effect": "Stun 3 highest damage enemies for 2s"},
    "SuperiorLifeform": {"effect": "Clone 2 strongest Piltover (40% HP, 50% damage)"},

    # Tier 3 only
    "EchoEngine": {"effect": "Repeat other module effects every 7s"},
    "UnstableCore": {"effect": "If 10+ Piltover casts: 30% max HP true damage, else 15%"},
    "Upgrade": {"effect": "Upgrade random item to Radiant, +15% AS, +300 HP"},
}

# Piltover tier unlock rules
PILTOVER_TIERS = {
    2: ["AccelerationGate", "BlastShield", "ContinuumCogs", "EMP", "KineticBarrier",
        "MomentumDrive", "OverclockedCapacitors", "TunedOscillator"],
    4: ["ArmorNullifier", "GigantificationRay", "MagnetronCoil", "ElectricalOverload",
        "MicroRockets", "MiningDrill", "90CaliberNets", "SuperiorLifeform"],
    6: ["EchoEngine", "UnstableCore", "Upgrade"],  # Plus T-Hex
}

# =============================================================================
# BILGEWATER STORE (Black Market)
# =============================================================================

# Bilgewater trait gives Silver Serpent currency:
# - (3) 15 per round, +1 per takedown
# - (5) 35 per round, +1 per takedown, improved loot
# - (7) 65 per round, +1 per takedown, superior loot
# - (10) 150 per round, +1 per takedown, 2x stats, fire cannons
#
# The Black Market sells stat buffs, equippable items, units, and lesser dupes.
# Each category has escalating costs per successive purchase.
# Source: littlebuddybot.com Bilgewater tables (patch 16.3)

# ── Equippable Bilgewater items (stats from tft.tools / user-provided tables) ──

BILGEWATER_ITEMS = {
    # --- Tier 1 items (available at 5 Bilgewater) ---
    "CaptainsBrew": {
        "display_name": "Captain's Brew",
        "tier": 1,
        "stats": {"ad": 0.10, "hp": 100, "ap": 10},
        "effect": "burn_chill",
        "effect_desc": "Attacks and Abilities Burn and Chill enemies for 2 seconds",
    },
    "LuckyEyepatch": {
        "display_name": "Lucky Doubloon",
        "tier": 1,
        "stats": {"attack_speed": 0.20, "crit_chance": 0.20},
        "effect": "bonus_serpents_takedown",
        "effect_desc": "On takedown, generate an additional 1 Silver Serpent",
        "bonus_serpents_per_takedown": 1,
    },

    # --- Tier 2 items (available at 7 Bilgewater) ---
    "FreebootersFrock": {
        "display_name": "Barknuckles",
        "tier": 2,
        "stats": {"hp": 300, "armor": 35, "magic_resist": 35},
        "effect": "tank_aura",
        "effect_desc": "Above 50% HP, double Armor/MR. Every 4s, 50% Armor+MR magic damage to 2 nearest",
        "double_threshold": 0.50,
        "aura_interval": 4.0,
        "aura_pct": 0.50,
    },
    "BlackmarketExplosives": {
        "display_name": "Blackmarket Explosives",
        "tier": 2,
        "stats": {"ap": 20, "attack_speed": 0.10},
        "effect": "aoe_explosion",
        "effect_desc": "Every 5s, deal 15 + 12% of damage dealt as magic damage to target + 2 nearest",
    },
    "BilgeratCutlass": {
        "display_name": "Cutthroat's Cutlass",
        "tier": 2,
        "stats": {"ad": 0.20, "ap": 20, "omnivamp": 0.15},
        "effect": "bleed",
        "effect_desc": "Damaging enemies causes 35% bleed over 4s",
        "bleed_pct": 0.35,
        "bleed_duration": 4.0,
    },
    "DeadmansDagger": {
        "display_name": "Dead Man's Dagger",
        "tier": 2,
        "stats": {"ad": 0.20, "ap": 20},
        "effect": "execute_on_kill",
        "effect_desc": "Execute below 12% HP. On kill, gain +10% AD and +15% AP",
        "execute_threshold": 0.12,
        "on_kill_ad": 0.10,
        "on_kill_ap": 0.15,
    },
    "FirstMatesFlintlock": {
        "display_name": "First Mate's Flintlock",
        "tier": 2,
        "stats": {"ad": 0.10, "crit_chance": 0.20},
        "effect": "stacking_as_ad",
        "effect_desc": "Every second, gain +3% AD and +3% AS",
    },
    "PileOCitrus": {
        "display_name": "Pile O' Citrus",
        "tier": 2,
        "stats": {"hp": 600},
        "effect": "heal_cleanse",
        "effect_desc": "Every 15s, heal 15% max HP and cleanse. After 15s, gain 10 bonus serpents",
        "heal_interval": 15.0,
        "heal_pct": 0.15,
        "bonus_serpents": 10,
        "serpent_delay": 15.0,
    },
}

# ── Stat buff tiers (applied to ALL Bilgewater champions) ──

BILGEWATER_STAT_BUFFS = {
    1: {"hp_pct": 0.04, "attack_speed": 0.04, "ad_ap_pct": 0.03},
    2: {"hp_pct": 0.06, "attack_speed": 0.06, "ad_ap_pct": 0.05},
    3: {"hp_pct": 0.08, "attack_speed": 0.08, "ad_ap_pct": 0.07},
}

# ── Escalating costs per successive purchase (in Silver Serpents) ──

BILGEWATER_COSTS = {
    "tier1_stats": [15, 30, 45, 60, 75, 90, 105],
    "tier2_stats": [30, 60, 90, 120, 150, 180, 210],
    "tier3_stats": [50, 100, 150, 200, 250, 300, 350],
    "tier1_items": [60, 80],           # Max 2 purchases
    "tier2_items": [100, 180, 260, 340],  # Max 4 purchases
    "lesser_dupe": [35, 35],           # Max 2 (flat cost)
    "shop_reroll": 1,                  # Flat cost
}

# ── Unit costs (flat, by gold cost tier) ──

BILGEWATER_UNIT_COSTS = {
    1: 15,   # 1-cost units (Illaoi)
    2: 35,   # 2-cost units (Graves, Twisted Fate)
    3: 50,   # 3-cost units (Gangplank, Nautilus)
    4: 75,   # 4-cost units (Fizz, Miss Fortune)
    5: 100,  # 5-cost units (Tahm Kench)
}

# ── Bilgewater champions by cost tier ──

BILGEWATER_CHAMPIONS = {
    1: [{"api_name": "TFT16_Illaoi", "display_name": "Illaoi"}],
    2: [
        {"api_name": "TFT16_Graves", "display_name": "Graves"},
        {"api_name": "TFT16_TwistedFate", "display_name": "Twisted Fate"},
    ],
    3: [
        {"api_name": "TFT16_Gangplank", "display_name": "Gangplank"},
        {"api_name": "TFT16_Nautilus", "display_name": "Nautilus"},
    ],
    4: [
        {"api_name": "TFT16_Fizz", "display_name": "Fizz"},
        {"api_name": "TFT16_MissFortune", "display_name": "Miss Fortune"},
    ],
    5: [{"api_name": "TFT16_TahmKench", "display_name": "Tahm Kench"}],
}

# ── Store offerings per Bilgewater count ──

BILGEWATER_STORE_LAYOUT = {
    3: ["tier1_stats", "tier1_units", "lesser_dupe"],
    5: ["tier1_stats", "tier2_stats", "tier1_items", "tier2_units", "lesser_dupe"],
    7: ["tier2_stats", "tier3_stats", "tier1_items", "tier2_items",
        "tier2_units", "tier3_units", "lesser_dupe"],
    10: ["tier3_stats", "tier2_items", "tier4_units", "lesser_dupe"],
    # At 10 Bilgewater: 2x all stat buffs + fire cannons
}

# ── Combined store config (for engine import) ──

BILGEWATER_STORE = {
    "items": BILGEWATER_ITEMS,
    "stat_buffs": BILGEWATER_STAT_BUFFS,
    "costs": BILGEWATER_COSTS,
    "unit_costs": BILGEWATER_UNIT_COSTS,
    "champions": BILGEWATER_CHAMPIONS,
    "layout": BILGEWATER_STORE_LAYOUT,
    "bg10_stat_multiplier": 2.0,
    "fire_cannon_damage": 500,
}

# =============================================================================
# BLACKSMITH TRAIT (Ornn)
# =============================================================================

BLACKSMITH_CONFIG = {
    "rounds_to_craft": 4,
    "artifact_multiplier": 3.0,  # Artifacts 3x more common
    "hp_per_item": {
        1: 35,   # Patch 16.4: 250→35
        2: 35,   # Patch 16.4: 450→35
        3: 35,   # Patch 16.4: unified to 35 for all star levels
    },
}

# =============================================================================
# COMBINED ITEM DATABASE
# =============================================================================

ALL_ITEMS = {
    **BASE_COMPONENTS,
    **BASE_COMPLETED,
    **{f"Artifact_{k}": v for k, v in ARTIFACT_ITEMS.items()},
    **RADIANT_ITEMS,
    **EMBLEM_ITEMS,
    **{f"Bilgewater_{k}": v.get("stats", {}) for k, v in BILGEWATER_ITEMS.items()},
}

# Aliases for common names
ITEM_ALIASES = {
    "Gargoyle": "GargoyleStoneplate",
    "RunaansHurricane": "KrakensFury",
    "StatikkShiv": "Artifact_StatikkShiv",  # Base StatikkShiv is actually Void Staff
    "Redemption": "SpiritVisage",
    "GuardianAngel": "EdgeOfNight",
    "FrozenHeart": "ProtectorsVow",

    # MetaTFT-style TFT_Item_ aliases (map to internal names)
    "TFT_Item_Deathblade": "Deathblade",
    "TFT_Item_InfinityEdge": "InfinityEdge",
    "TFT_Item_GiantSlayer": "GiantSlayer",
    "TFT_Item_LastWhisper": "LastWhisper",
    "TFT_Item_Bloodthirster": "Bloodthirster",
    "TFT_Item_SteraksGage": "SteraksGage",
    "TFT_Item_EdgeOfNight": "EdgeOfNight",
    "TFT_Item_RedBuff": "RedBuff",
    "TFT_Item_GuinsoosRageblade": "GuinsoosRageblade",
    "TFT_Item_TitansResolve": "TitansResolve",
    "TFT_Item_NashorsTooth": "NashorsTooth",
    "TFT_Item_RabadonsDeathcap": "RabadonsDeathcap",
    "TFT_Item_JeweledGauntlet": "JeweledGauntlet",
    "TFT_Item_HextechGunblade": "HextechGunblade",
    "TFT_Item_SpearOfShojin": "SpearOfShojin",
    "TFT_Item_BlueBuff": "BlueBuff",
    "TFT_Item_Morellonomicon": "Morellonomicon",
    "TFT_Item_ArchangelsStaff": "ArchangelsStaff",
    "TFT_Item_IonicSpark": "IonicSpark",
    "TFT_Item_WarmogsArmor": "WarmogsArmor",
    "TFT_Item_GargoyleStoneplate": "GargoyleStoneplate",
    "TFT_Item_SunfireCape": "SunfireCape",
    "TFT_Item_DragonsClaw": "DragonsClaw",
    "TFT_Item_BrambleVest": "BrambleVest",
    "TFT_Item_Quicksilver": "Quicksilver",
    "TFT_Item_Crownguard": "Crownguard",
    "TFT_Item_HandOfJustice": "HandOfJustice",
    "TFT_Item_AdaptiveHelm": "AdaptiveHelm",
    "TFT_Item_ThiefsGloves": "ThiefsGloves",
    "TFT_Item_SteadfastHeart": "SteadfastHeart",
    "TFT_Item_Evenshroud": "Evenshroud",
    "TFT_Item_StrikersFlail": "StrikersFlail",
    "TFT_Item_StatikkShiv": "Artifact_StatikkShiv",
    # Legacy API name aliases - Riot internal names that map to current display names
    # Source: metatft.com, wiki.leagueoflegends.com, Riot API data
    "TFT_Item_Leviathan": "NashorsTooth",          # API name for Nashor's Tooth (Bow+Belt)
    "TFT_Item_MadredsBloodrazor": "GiantSlayer",    # API name for Giant Slayer (Sword+Bow)
    "TFT_Item_UnstableConcoction": "HandOfJustice",  # API name for Hand of Justice (Tear+Gloves)
    "TFT_Item_NightHarvester": "SteadfastHeart",    # API name for Steadfast Heart (Vest+Gloves)
    "TFT_Item_SpectralGauntlet": "Evenshroud",      # API name for Evenshroud (Cloak+Belt)

    # Components with TFT_Item_ prefix
    "TFT_Item_BFSword": "BFSword",
    "TFT_Item_RecurveBow": "RecurveBow",
    "TFT_Item_NeedlesslyLargeRod": "NeedlesslyLargeRod",
    "TFT_Item_TearOfTheGoddess": "TearOfTheGoddess",
    "TFT_Item_ChainVest": "ChainVest",
    "TFT_Item_NegatronCloak": "NegatronCloak",
    "TFT_Item_GiantsBelt": "GiantsBelt",
    "TFT_Item_SparringGloves": "SparringGloves",
    "TFT_Item_Spatula": "Spatula",

    # Components with underscore-separated names (used by game loop)
    "BF_Sword": "BFSword",
    "Recurve_Bow": "RecurveBow",
    "Needlessly_Large_Rod": "NeedlesslyLargeRod",
    "Tear_of_the_Goddess": "TearOfTheGoddess",
    "Chain_Vest": "ChainVest",
    "Negatron_Cloak": "NegatronCloak",
    "Giants_Belt": "GiantsBelt",
    "Sparring_Gloves": "SparringGloves",

    # Completed items with TFT_Item_ prefix (additional aliases)
    "TFT_Item_RunaansHurricane": "KrakensFury",
    "TFT_Item_Redemption": "SpiritVisage",
    "TFT_Item_GuardianAngel": "EdgeOfNight",
    "TFT_Item_FrozenHeart": "ProtectorsVow",

    # Artifacts with TFT_Item_Artifact_ prefix
    "TFT_Item_Artifact_LichBane": "Artifact_LichBane",
    "TFT_Item_Artifact_StatikkShiv": "Artifact_StatikkShiv",
    "TFT_Item_Artifact_RapidFirecannon": "Artifact_RapidFirecannon",
    "TFT_Item_Artifact_NavoriFlickerblades": "Artifact_Flickerblade",  # Renamed in Set 16
    "TFT_Item_Artifact_Flickerblade": "Artifact_Flickerblade",
    "TFT_Item_Artifact_Fishbones": "Artifact_Fishbones",
    "TFT_Item_Artifact_DeathfireGrasp": "Artifact_DeathfireGrasp",
    "TFT_Item_Artifact_DeathsDefiance": "Artifact_DeathsDefiance",
    "TFT_Item_Artifact_GamblersBlade": "Artifact_GamblersBlade",
    "TFT_Item_Artifact_GoldCollector": "Artifact_GoldCollector",
    "TFT_Item_Artifact_InfinityForce": "Artifact_InfinityForce",
    "TFT_Item_Artifact_SnipersFocus": "Artifact_SnipersFocus",
    "TFT_Item_Artifact_TrickstersGlass": "Artifact_TrickstersGlass",
    "TFT_Item_Artifact_MogulsMail": "Artifact_MogulsMail",
    "TFT_Item_Artifact_Manazane": "Artifact_Manazane",
    "TFT_Item_Artifact_Hullcrusher": "Artifact_Hullcrusher",

    # Darkin items (TFT16_ prefix in API data)
    "TFT16_TheDarkinAegis": "Artifact_TheDarkinAegis",
    "TFT16_TheDarkinBow": "Artifact_TheDarkinBow",
    "TFT16_TheDarkinScythe": "Artifact_TheDarkinScythe",
    "TFT16_TheDarkinStaff": "Artifact_TheDarkinStaff",

    # Bilgewater items (API names from items.jsonl → internal names)
    "TFT16_Item_Bilgewater_BilgeratCutlass": "Bilgewater_BilgeratCutlass",
    "TFT16_Item_Bilgewater_BlackmarketExplosives": "Bilgewater_BlackmarketExplosives",
    "TFT16_Item_Bilgewater_CaptainsBrew": "Bilgewater_CaptainsBrew",
    "TFT16_Item_Bilgewater_DeadmansDagger": "Bilgewater_DeadmansDagger",
    "TFT16_Item_Bilgewater_FirstMatesFlintlock": "Bilgewater_FirstMatesFlintlock",
    "TFT16_Item_Bilgewater_FreebootersFrock": "Bilgewater_FreebootersFrock",
    "TFT16_Item_Bilgewater_LuckyEyepatch": "Bilgewater_LuckyEyepatch",
    "TFT16_Item_Bilgewater_PileOCitrus": "Bilgewater_PileOCitrus",
    # Display name aliases
    "Barknuckles": "Bilgewater_FreebootersFrock",
    "LuckyDoubloon": "Bilgewater_LuckyEyepatch",
    "CutthroatsCutlass": "Bilgewater_BilgeratCutlass",
    "DeadMansDagger": "Bilgewater_DeadmansDagger",
}
