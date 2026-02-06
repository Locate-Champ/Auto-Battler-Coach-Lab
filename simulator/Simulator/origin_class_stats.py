# TFT Set 16 Origin/Class Stats
# Updated from Set 4 to Set 16 trait data
# Source: simulator/data/traits.json and simulator/data/combat_data.json

# Champion -> trait mapping
# Keys are lowercase champion names matching pool_stats.py
origin_class = {
    # 1-cost
    'anivia': ['freljord', 'invoker'],
    'blitzcrank': ['zaun', 'juggernaut'],
    'briar': ['noxus', 'slayer', 'juggernaut'],
    'caitlyn': ['piltover', 'longshot'],
    'illaoi': ['bilgewater', 'bruiser'],
    'jarvaniv': ['demacia', 'defender'],
    'jhin': ['ionia', 'gunslinger'],
    'kogmaw': ['void', 'arcanist', 'longshot'],
    'lulu': ['yordle', 'arcanist'],
    'qiyana': ['ixtal', 'slayer'],
    'rumble': ['yordle', 'defender'],
    'shen': ['ionia', 'bruiser'],
    'sona': ['demacia', 'invoker'],
    'viego': ['shadow_isles', 'quickstriker'],

    # 2-cost
    'aphelios': ['targon'],
    'ashe': ['freljord', 'quickstriker'],
    'bard': ['caretaker'],
    'chogath': ['void', 'juggernaut'],
    'ekko': ['zaun', 'disruptor'],
    'graves': ['bilgewater', 'gunslinger'],
    'neeko': ['ixtal', 'arcanist', 'defender'],
    'orianna': ['piltover', 'invoker'],
    'poppy': ['demacia', 'yordle', 'juggernaut'],
    'reksai': ['void', 'vanquisher'],
    'sion': ['noxus', 'bruiser'],
    'teemo': ['yordle', 'longshot'],
    'tristana': ['yordle', 'gunslinger'],
    'tryndamere': ['freljord', 'slayer'],
    'twistedfate': ['bilgewater', 'quickstriker'],
    'vi': ['piltover', 'zaun', 'defender'],
    'xinzhao': ['demacia', 'ionia', 'warden'],
    'yasuo': ['ionia', 'slayer'],
    'yorick': ['shadow_isles', 'warden'],

    # 3-cost
    'ahri': ['ionia', 'arcanist'],
    'darius': ['noxus', 'defender'],
    'draven': ['noxus', 'quickstriker'],
    'drmundo': ['zaun', 'bruiser'],
    'gangplank': ['bilgewater', 'slayer', 'vanquisher'],
    'gwen': ['shadow_isles', 'disruptor'],
    'jinx': ['zaun', 'gunslinger'],
    'kennen': ['ionia', 'yordle', 'defender'],
    'kobuko': ['yordle', 'bruiser', 'invoker'],
    'leblanc': ['noxus', 'invoker'],
    'leona': ['targon'],
    'loris': ['piltover', 'warden'],
    'malzahar': ['void', 'disruptor'],
    'milio': ['ixtal', 'invoker'],
    'nautilus': ['bilgewater', 'juggernaut', 'warden'],
    'sejuani': ['freljord', 'defender'],
    'vayne': ['demacia', 'longshot'],
    'zoe': ['targon'],

    # 4-cost
    'ambessa': ['noxus', 'vanquisher'],
    'belveth': ['void', 'slayer'],
    'braum': ['freljord', 'warden'],
    'diana': ['targon'],
    'fizz': ['bilgewater', 'yordle'],
    'garen': ['demacia', 'defender'],
    'kaisa': ['assimilator', 'void', 'longshot'],
    'kalista': ['shadow_isles', 'vanquisher'],
    'lissandra': ['freljord', 'invoker'],
    'lux': ['demacia', 'arcanist'],
    'missfortune': ['bilgewater', 'gunslinger'],
    'nasus': ['shurima'],
    'nidalee': ['ixtal', 'huntress'],
    'renekton': ['shurima'],
    'seraphine': ['piltover', 'disruptor'],
    'singed': ['zaun', 'juggernaut'],
    'skarner': ['ixtal'],
    'swain': ['noxus', 'arcanist', 'juggernaut'],
    'taric': ['targon'],
    'veigar': ['yordle', 'arcanist'],
    'warwick': ['zaun', 'quickstriker'],
    'wukong': ['ionia', 'bruiser'],
    'yone': ['ionia', 'slayer'],
    'yunara': ['ionia', 'quickstriker'],

    # 5-cost
    'aatrox': ['darkin', 'world_ender', 'slayer'],
    'annie': ['dark_child', 'arcanist'],
    'aurelionsol': ['star_forger', 'targon'],
    'azir': ['shurima', 'emperor', 'disruptor'],
    'baronnashor': ['void', 'riftscourge'],
    'brock': ['ixtal'],
    'fiddlesticks': ['harvester', 'vanquisher'],
    'galio': ['demacia', 'heroic'],
    'kindred': ['eternal', 'quickstriker'],
    'lucian': ['soulbound', 'gunslinger'],
    'mel': ['noxus', 'disruptor'],
    'ornn': ['blacksmith', 'warden'],
    'ryze': ['rune_mage'],
    'sett': ['ionia', 'the_boss'],
    'shyvana': ['dragonborn', 'juggernaut'],
    'sylas': ['chainbreaker', 'arcanist', 'defender'],
    'tahmkench': ['bilgewater', 'glutton', 'bruiser'],
    'thex': ['hexmech', 'piltover', 'gunslinger'],
    'thresh': ['shadow_isles', 'warden'],
    'volibear': ['freljord', 'bruiser'],
    'xerath': ['shurima', 'ascendant'],
    'zaahen': ['darkin', 'immortal'],
    'ziggs': ['zaun', 'yordle', 'longshot'],
    'zilean': ['chronokeeper', 'invoker'],

    # Special/summon units (not in pool, but may appear in combat)
    'annietibbers': ['arcanist'],
    'azirsoldier': [],
    'freljordprop': [],
    'malzaharvoidling': [],
    'piltoverinvention': [],
    'riftherald': ['void', 'bruiser'],
    'atakhan': [],
}

# Set 16 does not have the Chosen mechanic (that was Set 4).
# Kept empty for compatibility.
chosen = []

# Trait tier breakpoints: trait_name -> [minUnits for each tier level]
tiers = {
    # Origins / Regions
    'bilgewater': [3, 5, 7, 10],
    'demacia': [3, 5, 7, 11],
    'freljord': [3, 5, 7],
    'ionia': [3, 5, 7, 10],
    'ixtal': [3, 5, 7],
    'noxus': [3, 5, 7, 10],
    'piltover': [2, 4, 6],
    'shadow_isles': [2, 3, 4, 5],
    'shurima': [2, 3, 4],
    'void': [2, 4, 6, 9],
    'yordle': [2, 4, 6, 8, 10],
    'zaun': [3, 5, 7],

    # Classes
    'arcanist': [2, 4, 6],
    'bruiser': [2, 4, 6],
    'defender': [2, 4, 6],
    'disruptor': [2, 4],
    'gunslinger': [2, 4],
    'invoker': [2, 4],
    'juggernaut': [2, 4, 6],
    'longshot': [2, 3, 4, 5],
    'quickstriker': [2, 3, 4, 5],
    'slayer': [2, 4, 6],
    'vanquisher': [2, 3, 4, 5],
    'warden': [2, 3, 4, 5],

    # Unique / Pair traits (single tier)
    'ascendant': [1],
    'assimilator': [1],
    'blacksmith': [1],
    'caretaker': [1],
    'chainbreaker': [1],
    'chosen_wolves': [2],
    'chronokeeper': [1],
    'dark_child': [1],
    'darkin': [1, 2, 3],
    'dragonborn': [1],
    'dragonguards': [2],
    'emperor': [1],
    'eternal': [1],
    'glutton': [1],
    'harvester': [1],
    'heroic': [1],
    'hexmech': [1],
    'huntress': [1],
    'immortal': [1],
    'poison_pals': [2],
    'riftscourge': [1],
    'rune_mage': [1],
    'sentinels_of_light': [2],
    'soulbound': [1],
    'star_forger': [1],
    'targon': [1],
    'the_boss': [1],
    'timewinders': [1, 2],
    'world_ender': [1],
}

# =============================================================================
# Trait stat values for Set 16
# Format: stat_category = { 'trait_name': [no_trait, tier1, tier2, ...] }
# Values from traits.json, rounded for readability
# =============================================================================

# Attack damage (% bonus AD)
AD = {
    'slayer': [0, 0.22, 0.33, 0.44],
    'gunslinger': [0, 0.22, 0.40],
    'shadow_isles': [0, 0.18, 0.20, 0.25, 0.33],  # ADAP applies to both AD and AP
}

# Ability power (flat AP bonus for trait units)
SP = {
    'arcanist': [0, 25, 40, 60],
}

# Ability power (flat AP for team)
SP_secondary = {
    'arcanist': [0, 18, 25, 40],  # AllyAP
}

# Attack speed (% bonus)
AS = {
    'quickstriker_min': [0, 0.10, 0.20, 0.30, 0.40],  # MinBonusAS (random range)
    'quickstriker_max': [0, 0.30, 0.45, 0.60, 0.80],  # MaxBonusAS (random range)
    'quickstriker_team': [0, 0.15, 0.15, 0.15, 0.15],  # TeamwideAS
    'void': [0, 0.08, 0.18, 0.33, 0.40],
    'the_boss': 0.60,  # AttackSpeedPercent (60%)
}

# Magic resist (flat)
MR = {
    'defender': [0, 12, 12, 12],  # TeamwideArmorMR (same for armor and MR)
    'demacia': [0, 12, 35, 35, 150],  # ArmorMR
}

# Armor (flat) - same values as MR for these traits
armor = {
    'defender': [0, 30, 55, 80],  # BonusArmorMR for trait units
    'defender_team': [0, 12, 12, 12],  # TeamwideArmorMR
    'demacia': [0, 12, 35, 35, 150],
}

# Mana generation (% increase)
mana_generation = {
    'invoker': [0, 0.25, 0.40],  # PercentManaIncrease
}

# Health (% bonus for trait units)
health = {
    'bruiser': [0, 0.25, 0.45, 0.65],  # BonusPercentHealth
    'freljord': [0, 0.08, 0.12, 0.16],  # HealthPercent
    'shurima': [0, 0.20, 0.20, 0.20],  # BonusHealth
}

# Health (flat, team-wide)
health_flat = {
    'bruiser': [0, 150, 150, 150],  # TeamFlatHealth
}

# Healing
heal = {
    'the_boss': 0.15,  # HealPercent
    'juggernaut': [0, 0.05, 0.05, 0.05],  # HealRatio (below health breakpoint)
    'shurima': [0, 20, 20, 20],  # HealthRestorePerSecond
}

# Damage amplification (% increase to damage dealt)
damage = {
    'longshot': [0, 0.18, 0.24, 0.28, 0.32],  # BaseDamageAmp
    'longshot_per_hex': [0, 0.02, 0.03, 0.04, 0.05],  # PercentDamageIncrease per hex
    'disruptor': [0, 0.18, 0.40],  # DamageAmp
    'gunslinger_bonus': [0, 100, 200],  # BonusDamage (flat, every NumAttacks)
}

# Damage reduction
damage_reduction = {
    'juggernaut': [0, 0.18, 0.20, 0.26],  # BaseDR
    'juggernaut_increased': [0, 0.25, 0.30, 0.36],  # IncreasedDR (below 50% HP)
    'disruptor': [0, 0.10, 0.10],  # DamageReduction for trait units
    'dragonborn': 0.08,  # AbilityDamageReduction
}

# Shield (% max HP)
shield = {
    'warden': [0, 0.16, 0.20, 0.26, 0.33],  # PercentHealthShield
}

# Lifesteal / omnivamp
lifesteal = {
    'slayer': [0, 0.10, 0.16, 0.20],  # BonusOmnivamp
    'darkin': [0, 0.15, 0.15, 0.15],  # Vamp
}

# Crit chance (flat, not %)
crit_chance = {
    'vanquisher': [0, 15, 20, 25, 30],  # BaseCritChance
}

# Crit damage (flat, not %)
crit_damage = {
    'vanquisher': [0, 15, 20, 25, 30],  # CritDmg
}

# Threshold values (HP %, attack counts, etc.)
threshold = {
    'the_boss': 0.45,  # MaxHealthThreshold - transforms below this HP %
    'juggernaut': 0.50,  # HealthBreakpoint - increased DR below this
    'slayer': 0.50,  # AmountIncrease - bonus at low HP
    'gunslinger': 4,  # NumAttacks - bonus damage proc interval
}

# Traits that should be applied at combat start
initiate_traits = [
    'arcanist',
    'bruiser',
    'defender',
    'invoker',
    'slayer',
    'warden',
    'quickstriker',
    'void',
    'juggernaut',
    'freljord',
    'demacia',
    'shadow_isles',
    'longshot',
    'vanquisher',
    'shurima',
    'yordle',
]

# Traits excluded from chosen mechanic (not applicable in Set 16)
chosen_exclude = [
    'ascendant',
    'assimilator',
    'blacksmith',
    'caretaker',
    'chainbreaker',
    'chronokeeper',
    'dark_child',
    'dragonborn',
    'emperor',
    'eternal',
    'glutton',
    'harvester',
    'heroic',
    'hexmech',
    'huntress',
    'immortal',
    'riftscourge',
    'rune_mage',
    'soulbound',
    'star_forger',
    'targon',
    'the_boss',
    'world_ender',
]

# Fortune mechanic does not exist in Set 16; kept for compatibility
fortune_returns = []
