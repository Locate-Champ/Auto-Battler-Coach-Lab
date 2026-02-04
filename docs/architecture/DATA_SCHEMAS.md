# Data Schema Reference

## Match Data (tft_since_16_2_enhanced.csv)

```python
{
    "match_id": "NA1_5470047531",           # Riot match ID
    "game_datetime": 1768959662960,          # Unix timestamp (ms)
    "game_length_sec": 2105.72,              # Game duration
    "queue_id": 1100,                        # Queue type (1100 = ranked)
    "game_version": "Linux Version 16.1...", # Patch version string
    "placement": 5,                          # TARGET: 1-8
    "level": 8,                              # Final level (6-10)
    "gold_left": 39,                         # Remaining gold
    "last_round": 28,                        # Final round survived
    "time_eliminated": 1708.66,              # Seconds until elimination
    "total_damage_to_players": 71,           # Damage dealt to enemy HP
    "players_eliminated": 0,                 # Enemies knocked out
    "aug1": float or NaN,                    # Augment 1 ID
    "aug2": float or NaN,                    # Augment 2 ID
    "aug3": float or NaN,                    # Augment 3 ID
    "traits_active": "Brawler:1 | Void:3",   # Pipe-delimited, Trait:Count
    "final_board_units": "KogMaw_2*() | ..."  # Complex format below
}
```

### Unit String Format
```
UnitName_StarLevel*(Item1,Item2,Item3)

Examples:
- KogMaw_2*()                                    # 2-star Kog'Maw, no items
- BelVeth_2*(TheDarkinBow,TitansResolve,RunaansHurricane)  # 2-star with 3 items
- Vayne_3*(HextechGunblade,RunaansHurricane,MadredsBloodrazor)  # 3-star maxed
```

### Parsing Regex
```python
import re

# Parse traits
def parse_traits(trait_str):
    if pd.isna(trait_str):
        return {}
    return dict(re.findall(r'(\w+):(\d+)', trait_str))

# Parse units
def parse_units(unit_str):
    if pd.isna(unit_str):
        return []
    pattern = r'(\w+)_(\d)\*\(([^)]*)\)'
    return [(name, int(stars), items.split(',') if items else []) 
            for name, stars, items in re.findall(pattern, unit_str)]
```

---

## Champion Data (champions.jsonl)

```python
{
    "apiName": "TFT16_Tristana",       # Riot internal name
    "name": "Tristana",                 # Display name
    "cost": 2,                          # Shop cost (1-5)
    "role": "ADCaster",                 # Tactical role
    "traits_pipe": "Yordle|Gunslinger", # Pipe-delimited traits
    "ability_name": "Buster Shot",      # Ability name
    "ability_desc": "...",              # Ability description (has placeholders)
    "stat_armor": 20.0,
    "stat_attackSpeed": 0.75,
    "stat_critChance": 0.25,
    "stat_critMultiplier": 1.4,
    "stat_damage": 55.0,
    "stat_hp": 550.0,
    "stat_initialMana": 0.0,
    "stat_magicResist": 20.0,
    "stat_mana": 50.0,
    "stat_range": 4.0
}
```

---

## Carry Performance (carry_performance_corrected.csv)

```python
{
    "carry": "Fiddlesticks",  # Champion name
    "cost": 5,                 # Shop cost
    "games": 12,               # Games played as carry
    "top4_rate": 0.833,        # Top 4 finish rate
    "win_rate": 0.25,          # 1st place rate
    "avg_placement": 2.75      # Average placement
}
```

---

## Trait Performance (trait_performance_corrected.csv)

```python
{
    "trait": "Sorcerer",       # Trait name
    "games": 45,               # Games with trait active
    "top4_rate": 0.622,        # Top 4 rate
    "win_rate": 0.133,         # Win rate
    "avg_placement": 4.12      # Avg placement
}
```

---

## Item Performance (item_performance_corrected.csv)

```python
{
    "item": "JeweledGauntlet",  # Item name (internal)
    "games": 28,                # Games built
    "top4_rate": 0.678,         # Top 4 rate
    "avg_placement": 3.89       # Avg placement
}
```

---

## Augments (augments.jsonl)

```python
{
    "apiName": "TFT16_Augment_...",  # Internal ID
    "name": "...",                    # Display name
    "desc": "...",                    # Effect description
    "tier": "Gold",                   # Silver/Gold/Prismatic
    # ... effect variables
}
```

---

## Traits (traits.jsonl)

```python
{
    "apiName": "Set16_Void",
    "name": "Void",
    "desc": "...",
    "breakpoints": [2, 4, 6],  # Activation thresholds
    # ... effect variables
}
```

---

## Early Game Meta (tft_set16_3_early_game_*.csv)

```python
{
    "Patch": 16.3,
    "Stage": 2,              # Game stage (2-5)
    "CompRank": 1,           # Rank in stage meta
    "WinRatePct": 52.3,      # Win rate %
    "FinalPlace": 4.2,       # Avg final placement
    "PlayRate": 3.5,         # Play rate %
    "Unit": "Kaisa",         # Core unit
    "StarLevel": 2           # Typical star level
}
```
