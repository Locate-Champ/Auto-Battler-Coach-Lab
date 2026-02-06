# TFT Set 16 Pool Stats
# Updated from Set 4 to Set 16 champion roster

# Cumulative level roll odds (Set 16, patch 16.4)
# Index = level - 1.  Values > 1 (sentinel 10) mean "impossible for higher costs."
# Source: Riot patch notes 16.1 + 16.4, verified against tftodds.com
level_percentage = [
    [1, 10, 10, 10, 10],           # Level 1:  100/0/0/0/0
    [1, 10, 10, 10, 10],           # Level 2:  100/0/0/0/0
    [.75, 1, 10, 10, 10],          # Level 3:  75/25/0/0/0
    [.55, .85, 1, 10, 10],         # Level 4:  55/30/15/0/0
    [.45, .78, .98, 1, 10],        # Level 5:  45/33/20/2/0
    [.30, .70, .95, 1, 10],        # Level 6:  30/40/25/5/0
    [.16, .46, .89, .99, 1],       # Level 7:  16/30/43/10/1  (16.4: 3-cost 40→43%)
    [.15, .35, .67, .97, 1],       # Level 8:  15/20/32/30/3
    [.10, .27, .52, .85, 1],       # Level 9:  10/17/25/33/15
    [.05, .15, .35, .75, 1],       # Level 10: 5/10/20/40/25
]

# 29 copies each
COST_1 = {
    'anivia': 29,
    'blitzcrank': 29,
    'briar': 29,
    'caitlyn': 29,
    'illaoi': 29,
    'jarvaniv': 29,
    'jhin': 29,
    'kogmaw': 29,
    'lulu': 29,
    'qiyana': 29,
    'rumble': 29,
    'shen': 29,
    'sona': 29,
    'viego': 29,
}

# 22 copies each
COST_2 = {
    'aphelios': 22,
    'ashe': 22,
    'bard': 22,
    'chogath': 22,
    'ekko': 22,
    'graves': 22,
    'neeko': 22,
    'orianna': 22,
    'poppy': 22,
    'reksai': 22,
    'sion': 22,
    'teemo': 22,
    'tristana': 22,
    'tryndamere': 22,
    'twistedfate': 22,
    'vi': 22,
    'xinzhao': 22,
    'yasuo': 22,
    'yorick': 22,
}

# 18 copies each
COST_3 = {
    'ahri': 18,
    'darius': 18,
    'draven': 18,
    'drmundo': 18,
    'gangplank': 18,
    'gwen': 18,
    'jinx': 18,
    'kennen': 18,
    'kobuko': 18,
    'leblanc': 18,
    'leona': 18,
    'loris': 18,
    'malzahar': 18,
    'milio': 18,
    'nautilus': 18,
    'sejuani': 18,
    'vayne': 18,
    'zoe': 18,
}

# 12 copies each
COST_4 = {
    'ambessa': 12,
    'belveth': 12,
    'braum': 12,
    'diana': 12,
    'fizz': 12,
    'garen': 12,
    'kaisa': 12,
    'kalista': 12,
    'lissandra': 12,
    'lux': 12,
    'missfortune': 12,
    'nasus': 12,
    'nidalee': 12,
    'renekton': 12,
    'seraphine': 12,
    'singed': 12,
    'skarner': 12,
    'swain': 12,
    'taric': 12,
    'veigar': 12,
    'warwick': 12,
    'wukong': 12,
    'yone': 12,
    'yunara': 12,
    'riftherald': 12,  # Unlockable 4-cost (Void/Bruiser) - Source: metatft.com, tftactics.gg
}

# 10 copies each
COST_5 = {
    'aatrox': 10,
    'annie': 10,
    'azir': 10,
    'fiddlesticks': 10,
    'galio': 10,
    'kindred': 10,
    'lucian': 10,
    'mel': 10,
    'ornn': 10,
    'sett': 10,
    'shyvana': 10,
    'tahmkench': 10,
    'thex': 10,
    'thresh': 10,
    'volibear': 10,
    'xerath': 10,
    'ziggs': 10,
    'zilean': 10,
}

# 10 copies each (same pool size and shop odds as 5-cost)
# The only difference from 5-cost is the increased gold cost (7g).
COST_7 = {
    'aurelionsol': 10,
    'baronnashor': 10,
    'brock': 10,
    'ryze': 10,
    'sylas': 10,
    'zaahen': 10,
}

# Set 16 does not have the Chosen mechanic (that was Set 4).
# Kept for compatibility but not used in Set 16.
chosen_stats = [
    [1.0, 10, 10, 10, 10],
    [1.0, 10, 10, 10, 10],
    [1.0, 10, 10, 10, 10],
    [1.0, 10, 10, 10, 10],
    [.8, 1.0, 10, 10, 10],
    [.4, .95, 1.0, 10, 10],
    [0, .6, 1.0, 10, 10],
    [0, .4, .98, 1.0, 10],
    [0, 0, .6, 1.0, 10],
    [0, 0, 0, .6, 1.0]
]

cost_star_values = [
    [1, 3, 9],
    [2, 5, 17],
    [3, 8, 26],
    [4, 11, 35],
    [5, 14, 44],
    [0, 0, 0],     # 6-cost placeholder (unused in Set 16)
    [7, 21, 63],   # 7-cost: buy=7g, 2-star=21g, 3-star=63g
]

base_pool_values = [29, 22, 18, 12, 10, 0, 10]
