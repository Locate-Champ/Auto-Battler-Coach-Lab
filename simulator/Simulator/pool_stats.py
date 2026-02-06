# TFT Set 16 Pool Stats
# Updated from Set 4 to Set 16 champion roster

# Cumulative level roll odds - the code should never get past the 1
# so the 10s are irrelevant. Only there to catch possible bugs
level_percentage = [
    [1, 10, 10, 10, 10],
    [1, 10, 10, 10, 10],
    [1, 10, 10, 10, 10],
    [.75, 1, 10, 10, 10],
    [.55, .85, 1, 10, 10],
    [.45, .775, .975, 1, 10],
    [.25, .65, .95, 1, 10],
    [.20, .50, .85, .99, 1],
    [.15, .35, .7, .95, 1],
    [.1, .25, .55, .85, 1],
    [.05, .15, .35, .75, 1],
    [.01, .03, .15, .65, 1],
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
}

# 10 copies each
COST_5 = {
    'aatrox': 10,
    'annie': 10,
    'aurelionsol': 10,
    'azir': 10,
    'baronnashor': 10,
    'brock': 10,
    'fiddlesticks': 10,
    'galio': 10,
    'kindred': 10,
    'lucian': 10,
    'mel': 10,
    'ornn': 10,
    'ryze': 10,
    'sett': 10,
    'shyvana': 10,
    'sylas': 10,
    'tahmkench': 10,
    'thex': 10,
    'thresh': 10,
    'volibear': 10,
    'xerath': 10,
    'zaahen': 10,
    'ziggs': 10,
    'zilean': 10,
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
    [5, 14, 44]
]

base_pool_values = [29, 22, 18, 12, 10]
