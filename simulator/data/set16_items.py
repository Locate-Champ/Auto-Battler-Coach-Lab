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
    "NashorsTooth": {"ap": 20, "attack_speed": 0.10, "crit_chance": 0.20, "hp": 150},

    # AP Items
    "RabadonsDeathcap": {"ap": 50, "damage_amp": 0.15},
    "JeweledGauntlet": {"ap": 35, "crit_chance": 0.35, "crit_multiplier": 0.10},
    "HextechGunblade": {"ad": 0.20, "ap": 20, "omnivamp": 0.15},
    "SpearOfShojin": {"ad": 0.15, "ap": 15, "mana_regen": 1},  # Mana on cast
    "BlueBuff": {"ad": 0.15, "ap": 15, "mana_regen": 5},  # Bonus after cast
    "Morellonomicon": {"ap": 20, "hp": 150, "mana_regen": 1},  # Burn + anti-heal
    "ArchangelsStaff": {"ap": 30, "mana_regen": 1},  # Stacking AP
    "IonicSpark": {"ap": 15, "hp": 250, "magic_resist": 35},  # MR shred aura
    "VoidStaff": {"ap": 35, "attack_speed": 0.15, "mana_regen": 1},  # MR shred on hit

    # Tank Items
    "WarmogsArmor": {"hp": 500},
    "GargoyleStoneplate": {"armor": 25, "magic_resist": 25, "hp": 100},
    "SunfireCape": {"armor": 20, "hp": 150},  # AOE burn
    "DragonsClaw": {"magic_resist": 75},
    "BrambleVest": {"armor": 65},  # Reflect damage
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
    "TacticiansCrown": {},
}

# =============================================================================
# ARTIFACT ITEMS (from Ornn/Blacksmith)
# =============================================================================

ARTIFACT_ITEMS = {
    "AegisOfDawn": {"armor": 50, "hp": 200},  # Armor steal
    "AegisOfDusk": {"magic_resist": 70, "hp": 200},  # MR steal
    "BlightingJewel": {"ap": 60},  # MR reduction on damage
    "CappaJuice": {"ad": 0.25, "ap": 25, "attack_speed": 0.20},  # AD/AP on takedown
    "CorruptVampiricScepter": {"attack_speed": 0.60},  # 60% damage as healing
    "Dawncore": {"ad": 0.15, "ap": 0.15},  # Reduces mana cost per cast
    "EternalPact": {"ap": 40, "mana_regen": 1},  # Shield ally with AP
    "Fishbones": {"ad": 0.50, "attack_speed": 0.50},  # Jinx's rockets
    "ForbiddenIdol": {"armor": 25, "hp": 200, "magic_resist": 25},  # Shield to heal
    "HellfireHatchet": {"ad": 0.20, "hp": 150, "omnivamp": 0.20},  # Max HP damage
    "HorizonFocus": {"armor": 20, "hp": 250, "magic_resist": 20, "mana_regen": 2},  # % HP damage
    "InnervatingLocket": {"hp": 150, "mana_regen": 2},  # Heal + mana on cast
    "LesserMirroredPersona": {"ad": 0.10, "ap": 10, "attack_speed": 0.10, "armor": 10, "hp": 100, "magic_resist": 10},
    "LichBane": {"ap": 55, "attack_speed": 0.10},  # Empowered auto after ability
    "LightshieldCrest": {"armor": 55, "magic_resist": 55},  # Shield from resists
    "LudensTempest": {"ad": 0.50, "ap": 50},  # Overkill splash damage
    "MendingEchoes": {"hp": 200, "mana_regen": 2},  # Increased healing
    "MirroredPersona": {"ad": 0.10, "ap": 10, "attack_speed": 0.10, "armor": 10, "hp": 100, "magic_resist": 10},
    "Mittens": {"attack_speed": 0.65},  # Damage reduction
    "NavoriFlickerblades": {"ap": 10, "attack_speed": 0.12},  # Stacking AD/AP/AS
    "ProwlersClaw": {"ad": 0.35, "crit_chance": 0.45, "crit_multiplier": 0.50, "hp": 200},
    "RapidFirecannon": {"attack_speed": 0.65},  # Extra range
    "SeekersArmguard": {"ap": 25, "armor": 10, "magic_resist": 10, "omnivamp": 0.20},
    "ShadowPuppet": {"attack_speed": 0.10, "armor": 10, "magic_resist": 10},  # Clone on death
    "SilvermereDawn": {"ad": 1.40, "armor": 80, "magic_resist": 80},  # Stun on hit
    "SpectralCutlass": {"ad": 0.40, "crit_chance": 0.20, "hp": 300},  # Teleport to enemy side
    "StatikkShiv": {"ap": 15, "attack_speed": 0.50},  # Chain lightning every 3rd attack
    "SuspiciousTrenchCoat": {"hp": 400, "attack_speed": 0.30},  # Split into 3 at 60% HP
    "TalismanOfAscension": {"ap": 25, "armor": 25, "magic_resist": 25},  # +100% HP/dmg after 22s
    "TheIndomitable": {"hp": 600, "armor": 40, "magic_resist": 40},  # Pull target into melee
    "TitanicHydra": {"ad": 0.30, "hp": 400},  # 3% max HP splash damage
    "UnendingDespair": {"armor": 30, "hp": 400, "magic_resist": 30},  # Damage on shield break
    "VoidGauntlet": {"ap": 30, "armor": 30, "magic_resist": 30},  # Death AoE damage
    "WitsEnd": {"attack_speed": 0.40, "magic_resist": 40},  # On-hit magic damage + heal
    "ZhonyasParadox": {"ap": 30, "armor": 40},  # Untargetable at 50% HP
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

EMBLEM_ITEMS = {
    "BilgewaterEmblem": {"hp": 150},
    "BruiserEmblem": {"hp": 150},
    "DefenderEmblem": {"hp": 150},
    "DemaciaEmblem": {"hp": 150},
    "FreljordEmblem": {"hp": 150},
    "GunslingerEmblem": {"hp": 150},
    "InvokerEmblem": {"hp": 150},
    "IoniaEmblem": {"hp": 150},
    "IxtalEmblem": {"hp": 150},
    "JuggernautEmblem": {"hp": 150},
    "LongshotEmblem": {"hp": 150},
    "NoxusEmblem": {"hp": 150},
    "PiltoverEmblem": {"hp": 150},
    "QuickstrikerEmblem": {"hp": 150},
    "ShurimaEmblem": {"hp": 150},
    "SorcererEmblem": {"hp": 150},
    "VoidEmblem": {"hp": 150},
    "WardenEmblem": {"hp": 150},
    "YordleEmblem": {"hp": 150},
    "ZaunEmblem": {"hp": 150},
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
    "ArmorNullifier": {"effect": "Piltover deal 25% more damage, 35% vs tanks"},
    "BlastShield": {"effect": "All allies gain 20% max HP shield"},
    "ContinuumCogs": {"effect": "All allies gain 2 mana regen and 12 AP"},
    "EMP": {"effect": "Increase enemy mana costs by 15"},
    "GigantificationRay": {"effect": "Piltover gain 23% max HP and grow larger"},
    "KineticBarrier": {"effect": "Piltover gain 60 Armor and 20 MR (or opposite)"},
    "MagnetronCoil": {"effect": "Piltover gain 18% damage amp + 1% per cast"},
    "MomentumDrive": {"effect": "Cleanse CC, team gains 50% tenacity"},
    "OverclockedCapacitors": {"effect": "Team gains 22% attack speed"},
    "TunedOscillator": {"effect": "Increase healing/shielding by 25%"},

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
# BILGEWATER STORE
# =============================================================================

# Bilgewater trait gives Serpent currency based on:
# - 3 Bilgewater: 15 per round, 2 per takedown
# - 5 Bilgewater: 35 per round, 2 per takedown
# - 7 Bilgewater: 65 per round, 2 per takedown
# - 10 Bilgewater: 150 per round, 2 per takedown + 2x item stats

BILGEWATER_STORE = {
    # Champions available for purchase with Serpents
    "champions": {
        "Fizz_1star": {"cost": 30},
        "Fizz_2star": {"cost": 90},
        "Gangplank_1star": {"cost": 60},
        "Gangplank_2star": {"cost": 180},
        "Graves_1star": {"cost": 30},
        "Graves_2star": {"cost": 90},
        "Illaoi_1star": {"cost": 30},
        "Illaoi_2star": {"cost": 90},
        "MissFortune_1star": {"cost": 60},
        "MissFortune_2star": {"cost": 180},
        "Nautilus_1star": {"cost": 45},
        "Nautilus_2star": {"cost": 135},
        "TahmKench_1star": {"cost": 30},
        "TahmKench_2star": {"cost": 90},
        "TwistedFate_1star": {"cost": 45},
        "TwistedFate_2star": {"cost": 135},
    },
    # Items available (max 8 purchases)
    "items": {
        "Component": {"cost": 25},  # Random component
        "CompletedItem": {"cost": 50},  # Random completed item
        "Emblem": {"cost": 75},  # Random emblem
        "Gold": {"cost": 10, "amount": 3},  # 3 gold
    },
    "max_purchases": 8,
}

# =============================================================================
# BLACKSMITH TRAIT (Ornn)
# =============================================================================

BLACKSMITH_CONFIG = {
    "rounds_to_craft": 4,
    "artifact_multiplier": 3.0,  # Artifacts 3x more common
    "hp_per_item": {
        1: 250,  # 1-star Ornn
        2: 450,  # 2-star Ornn
        3: 2000,  # 3-star Ornn
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
}

# Aliases for common names
ITEM_ALIASES = {
    "Gargoyle": "GargoyleStoneplate",
    "RunaansHurricane": "KrakensFury",
    "StatikkShiv": "Artifact_StatikkShiv",  # Base StatikkShiv is actually Void Staff
    "Redemption": "SpiritVisage",
    "GuardianAngel": "EdgeOfNight",
    "FrozenHeart": "ProtectorsVow",
}
