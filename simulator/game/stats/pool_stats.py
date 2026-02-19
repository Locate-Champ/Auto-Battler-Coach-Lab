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

# 30 copies each (Set 16 - source: tftodds.com, wiki.leagueoflegends.com, esportstales.com)
COST_1 = {
    'anivia': 30,
    'blitzcrank': 30,
    'briar': 30,
    'caitlyn': 30,
    'illaoi': 30,
    'jarvaniv': 30,
    'jhin': 30,
    'kogmaw': 30,
    'lulu': 30,
    'qiyana': 30,
    'rumble': 30,
    'shen': 30,
    'sona': 30,
    'viego': 30,
}

# 25 copies each (Set 16 - source: tftodds.com, wiki.leagueoflegends.com, esportstales.com)
COST_2 = {
    'aphelios': 25,
    'ashe': 25,
    'bard': 25,
    'chogath': 25,
    'ekko': 25,
    'graves': 25,
    'neeko': 25,
    'orianna': 25,
    'poppy': 25,
    'reksai': 25,
    'sion': 25,
    'teemo': 25,
    'tristana': 25,
    'tryndamere': 25,
    'twistedfate': 25,
    'vi': 25,
    'xinzhao': 25,
    'yasuo': 25,
    'yorick': 25,
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

# 10 copies each (Set 16 - source: tftodds.com, wiki.leagueoflegends.com, esportstales.com)
COST_4 = {
    'ambessa': 10,
    'belveth': 10,
    'braum': 10,
    'diana': 10,
    'fizz': 10,
    'garen': 10,
    'kaisa': 10,
    'kalista': 10,
    'lissandra': 10,
    'lux': 10,
    'missfortune': 10,
    'nasus': 10,
    'nidalee': 10,
    'renekton': 10,
    'seraphine': 10,
    'singed': 10,
    'skarner': 10,
    'swain': 10,
    'taric': 10,
    'veigar': 10,
    'warwick': 10,
    'wukong': 10,
    'yone': 10,
    'yunara': 10,
    'riftherald': 10,  # Unlockable 4-cost (Void/Bruiser) - Source: metatft.com, tftactics.gg
}

# 9 copies each (Set 16 - source: tftodds.com, wiki.leagueoflegends.com, Riot Lore & Legends overview)
COST_5 = {
    'aatrox': 9,
    'annie': 9,
    'azir': 9,
    'fiddlesticks': 9,
    'galio': 9,
    'kindred': 9,
    'lucian': 9,
    'mel': 9,
    'ornn': 9,
    'sett': 9,
    'shyvana': 9,
    'tahmkench': 9,
    'thex': 9,
    'thresh': 9,
    'volibear': 9,
    'xerath': 9,
    'ziggs': 9,
    'zilean': 9,
}

# 9 copies each (same pool size and shop odds as 5-cost)
# The only difference from 5-cost is the increased gold cost (7g).
COST_7 = {
    'aurelionsol': 9,
    'baronnashor': 9,
    'brock': 9,
    'ryze': 9,
    'sylas': 9,
    'zaahen': 9,
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

base_pool_values = [30, 25, 18, 10, 9, 0, 9]

