#!/usr/bin/env python3
"""
TFT Set 16 Diagnostic Dashboard
Analyzes match history to identify improvement opportunities
"""

import pandas as pd
import json
import re
from collections import defaultdict
from datetime import datetime

# ============================================================================
# DATA LOADING
# ============================================================================

def load_champions():
    """Load champion reference data"""
    champs = {}
    with open('champions.jsonl', 'r') as f:
        for line in f:
            c = json.loads(line)
            api_name = c.get('apiName', '')
            # Extract clean name for matching
            name = c.get('name', '')
            champs[api_name] = {
                'name': name,
                'cost': c.get('cost', 0),
                'role': c.get('role'),
                'traits': c.get('traits', []),
                'stats': c.get('stats', {})
            }
            # Also map by character name variants
            char_name = c.get('characterName', '')
            if char_name:
                champs[char_name] = champs[api_name]
    return champs

def load_traits():
    """Load trait reference data"""
    traits = {}
    with open('traits.jsonl', 'r') as f:
        for line in f:
            t = json.loads(line)
            api_name = t.get('apiName', '')
            traits[api_name] = {
                'name': t.get('name', ''),
                'effects': t.get('effects', [])
            }
    return traits

def parse_unit_string(unit_str):
    """
    Parse unit string like: 'Viego_3*(Bloodthirster,TitansResolve,HextechGunblade)'
    Returns: (name, star_level, [items])
    """
    if not unit_str:
        return None, None, []
    
    # Pattern: Name_StarLevel*(items) or Name_StarLevel*()
    match = re.match(r'([A-Za-z0-9_]+)_(\d)\*\((.*?)\)', unit_str.strip())
    if match:
        name = match.group(1)
        star = int(match.group(2))
        items_str = match.group(3)
        items = [i.strip() for i in items_str.split(',') if i.strip()]
        return name, star, items
    return None, None, []

def parse_traits_string(traits_str):
    """
    Parse traits string like: 'Blacksmith:1 | KindredUnique:1 | Magus:1'
    Returns: dict of {trait_name: count}
    """
    if not traits_str or pd.isna(traits_str):
        return {}
    
    traits = {}
    for part in traits_str.split('|'):
        part = part.strip()
        if ':' in part:
            name, count = part.rsplit(':', 1)
            try:
                traits[name.strip()] = int(count)
            except ValueError:
                pass
    return traits

def parse_match_data(df, champs):
    """Parse all match data into structured format"""
    parsed_games = []
    
    for idx, row in df.iterrows():
        game = {
            'match_id': row['match_id'],
            'placement': row['placement'],
            'level': row['level'],
            'gold_left': row['gold_left'],
            'last_round': row['last_round'],
            'game_length_sec': row['game_length_sec'],
            'total_damage': row['total_damage_to_players'],
            'players_eliminated': row['players_eliminated'],
            'units': [],
            'traits': parse_traits_string(row['traits_active']),
            'top4': row['placement'] <= 4,
            'win': row['placement'] == 1
        }
        
        # Parse units
        units_str = row['final_board_units']
        if units_str and not pd.isna(units_str):
            for unit_part in units_str.split('|'):
                name, star, items = parse_unit_string(unit_part)
                if name:
                    # Look up champion data
                    champ_key = f'TFT16_{name}'
                    champ_data = champs.get(champ_key, champs.get(name, {}))
                    
                    game['units'].append({
                        'name': name,
                        'star': star,
                        'items': items,
                        'cost': champ_data.get('cost', 0),
                        'role': champ_data.get('role'),
                        'item_count': len(items)
                    })
        
        # Calculate board value
        game['board_value'] = sum(
            u['cost'] * (3 ** (u['star'] - 1)) for u in game['units']
        )
        
        # Identify primary carry (unit with most items)
        if game['units']:
            carry = max(game['units'], key=lambda x: (x['item_count'], x['cost'], x['star']))
            game['primary_carry'] = carry['name']
            game['carry_items'] = carry['items']
            game['carry_star'] = carry['star']
        else:
            game['primary_carry'] = None
            game['carry_items'] = []
            game['carry_star'] = 0
        
        parsed_games.append(game)
    
    return parsed_games

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_trait_performance(games):
    """Analyze win rate by trait"""
    trait_stats = defaultdict(lambda: {'games': 0, 'top4': 0, 'wins': 0, 'avg_placement': []})
    
    for game in games:
        for trait, count in game['traits'].items():
            # Skip unique traits (single champion)
            if 'Unique' in trait:
                continue
            key = f"{trait}:{count}"
            trait_stats[key]['games'] += 1
            trait_stats[key]['top4'] += int(game['top4'])
            trait_stats[key]['wins'] += int(game['win'])
            trait_stats[key]['avg_placement'].append(game['placement'])
    
    # Calculate rates
    results = []
    for trait, stats in trait_stats.items():
        if stats['games'] >= 3:  # Minimum sample size
            results.append({
                'trait': trait,
                'games': stats['games'],
                'top4_rate': stats['top4'] / stats['games'] * 100,
                'win_rate': stats['wins'] / stats['games'] * 100,
                'avg_placement': sum(stats['avg_placement']) / len(stats['avg_placement'])
            })
    
    return sorted(results, key=lambda x: x['avg_placement'])

def analyze_carry_performance(games, champs):
    """Analyze performance by primary carry"""
    carry_stats = defaultdict(lambda: {'games': 0, 'top4': 0, 'wins': 0, 'placements': []})
    
    for game in games:
        if game['primary_carry']:
            carry = game['primary_carry']
            carry_stats[carry]['games'] += 1
            carry_stats[carry]['top4'] += int(game['top4'])
            carry_stats[carry]['wins'] += int(game['win'])
            carry_stats[carry]['placements'].append(game['placement'])
    
    results = []
    for carry, stats in carry_stats.items():
        if stats['games'] >= 3:
            # Get champion cost
            champ_key = f'TFT16_{carry}'
            champ_data = champs.get(champ_key, champs.get(carry, {}))
            cost = champ_data.get('cost', 0)
            
            results.append({
                'carry': carry,
                'cost': cost,
                'games': stats['games'],
                'top4_rate': stats['top4'] / stats['games'] * 100,
                'win_rate': stats['wins'] / stats['games'] * 100,
                'avg_placement': sum(stats['placements']) / len(stats['placements'])
            })
    
    return sorted(results, key=lambda x: x['avg_placement'])

def analyze_item_performance(games):
    """Analyze item effectiveness on carries"""
    item_stats = defaultdict(lambda: {'games': 0, 'top4': 0, 'placements': []})
    
    for game in games:
        for item in game['carry_items']:
            # Clean item name
            item_clean = item.replace('Item_', '').replace('TFT4_', '').replace('TFT5_', '')
            item_stats[item_clean]['games'] += 1
            item_stats[item_clean]['top4'] += int(game['top4'])
            item_stats[item_clean]['placements'].append(game['placement'])
    
    results = []
    for item, stats in item_stats.items():
        if stats['games'] >= 3:
            results.append({
                'item': item,
                'games': stats['games'],
                'top4_rate': stats['top4'] / stats['games'] * 100,
                'avg_placement': sum(stats['placements']) / len(stats['placements'])
            })
    
    return sorted(results, key=lambda x: x['avg_placement'])

def analyze_level_performance(games):
    """Analyze performance by final level"""
    level_stats = defaultdict(lambda: {'games': 0, 'top4': 0, 'placements': []})
    
    for game in games:
        lvl = game['level']
        level_stats[lvl]['games'] += 1
        level_stats[lvl]['top4'] += int(game['top4'])
        level_stats[lvl]['placements'].append(game['placement'])
    
    results = []
    for level, stats in level_stats.items():
        results.append({
            'level': level,
            'games': stats['games'],
            'top4_rate': stats['top4'] / stats['games'] * 100,
            'avg_placement': sum(stats['placements']) / len(stats['placements'])
        })
    
    return sorted(results, key=lambda x: x['level'])

def analyze_game_length(games):
    """Analyze performance by game length quartiles"""
    lengths = [g['game_length_sec'] for g in games]
    q1, q2, q3 = pd.Series(lengths).quantile([0.25, 0.5, 0.75])
    
    def get_quartile(length):
        if length <= q1: return 'Fast (Q1)'
        elif length <= q2: return 'Medium-Fast (Q2)'
        elif length <= q3: return 'Medium-Slow (Q3)'
        else: return 'Slow (Q4)'
    
    quartile_stats = defaultdict(lambda: {'games': 0, 'top4': 0, 'placements': []})
    
    for game in games:
        q = get_quartile(game['game_length_sec'])
        quartile_stats[q]['games'] += 1
        quartile_stats[q]['top4'] += int(game['top4'])
        quartile_stats[q]['placements'].append(game['placement'])
    
    results = []
    for quartile, stats in quartile_stats.items():
        results.append({
            'quartile': quartile,
            'games': stats['games'],
            'top4_rate': stats['top4'] / stats['games'] * 100,
            'avg_placement': sum(stats['placements']) / len(stats['placements'])
        })
    
    return results

def analyze_board_value(games):
    """Analyze performance by board value"""
    values = [g['board_value'] for g in games]
    q1, q2, q3 = pd.Series(values).quantile([0.25, 0.5, 0.75])
    
    def get_quartile(value):
        if value <= q1: return 'Low Value (Q1)'
        elif value <= q2: return 'Medium-Low (Q2)'
        elif value <= q3: return 'Medium-High (Q3)'
        else: return 'High Value (Q4)'
    
    quartile_stats = defaultdict(lambda: {'games': 0, 'top4': 0, 'placements': [], 'values': []})
    
    for game in games:
        q = get_quartile(game['board_value'])
        quartile_stats[q]['games'] += 1
        quartile_stats[q]['top4'] += int(game['top4'])
        quartile_stats[q]['placements'].append(game['placement'])
        quartile_stats[q]['values'].append(game['board_value'])
    
    results = []
    for quartile, stats in quartile_stats.items():
        results.append({
            'quartile': quartile,
            'games': stats['games'],
            'top4_rate': stats['top4'] / stats['games'] * 100,
            'avg_placement': sum(stats['placements']) / len(stats['placements']),
            'avg_value': sum(stats['values']) / len(stats['values'])
        })
    
    return results

def generate_recommendations(games, trait_perf, carry_perf, item_perf):
    """Generate actionable recommendations"""
    recommendations = []
    
    # Overall stats
    total_games = len(games)
    top4_count = sum(1 for g in games if g['top4'])
    win_count = sum(1 for g in games if g['win'])
    avg_placement = sum(g['placement'] for g in games) / total_games
    
    recommendations.append(f"=== OVERALL PERFORMANCE ===")
    recommendations.append(f"Games Analyzed: {total_games}")
    recommendations.append(f"Top 4 Rate: {top4_count/total_games*100:.1f}%")
    recommendations.append(f"Win Rate: {win_count/total_games*100:.1f}%")
    recommendations.append(f"Average Placement: {avg_placement:.2f}")
    recommendations.append("")
    
    # Best traits
    recommendations.append("=== YOUR BEST TRAITS (Play More) ===")
    best_traits = [t for t in trait_perf if t['top4_rate'] >= 60 and t['games'] >= 5]
    for t in best_traits[:5]:
        recommendations.append(f"  {t['trait']}: {t['top4_rate']:.0f}% top4 ({t['games']} games, avg {t['avg_placement']:.1f})")
    if not best_traits:
        recommendations.append("  No traits with 60%+ top4 rate and 5+ games")
    recommendations.append("")
    
    # Worst traits
    recommendations.append("=== YOUR WORST TRAITS (Avoid) ===")
    worst_traits = [t for t in trait_perf if t['top4_rate'] < 40 and t['games'] >= 5]
    for t in worst_traits[:5]:
        recommendations.append(f"  {t['trait']}: {t['top4_rate']:.0f}% top4 ({t['games']} games, avg {t['avg_placement']:.1f})")
    if not worst_traits:
        recommendations.append("  No traits with <40% top4 rate and 5+ games")
    recommendations.append("")
    
    # Best carries
    recommendations.append("=== YOUR BEST CARRIES ===")
    best_carries = [c for c in carry_perf if c['top4_rate'] >= 60 and c['games'] >= 3]
    for c in best_carries[:5]:
        recommendations.append(f"  {c['carry']} ({c['cost']}â˜…): {c['top4_rate']:.0f}% top4 ({c['games']} games)")
    recommendations.append("")
    
    # Worst carries
    recommendations.append("=== YOUR WORST CARRIES (Stop Forcing) ===")
    worst_carries = [c for c in carry_perf if c['top4_rate'] < 40 and c['games'] >= 3]
    worst_carries = sorted(worst_carries, key=lambda x: x['avg_placement'], reverse=True)
    for c in worst_carries[:5]:
        recommendations.append(f"  {c['carry']} ({c['cost']}â˜…): {c['top4_rate']:.0f}% top4 ({c['games']} games, avg {c['avg_placement']:.1f})")
    recommendations.append("")
    
    # Best items
    recommendations.append("=== YOUR BEST CARRY ITEMS ===")
    best_items = [i for i in item_perf if i['top4_rate'] >= 60 and i['games'] >= 5]
    for i in best_items[:7]:
        recommendations.append(f"  {i['item']}: {i['top4_rate']:.0f}% top4 ({i['games']} games)")
    recommendations.append("")
    
    # Worst items
    recommendations.append("=== ITEMS TO AVOID ON CARRY ===")
    worst_items = [i for i in item_perf if i['top4_rate'] < 40 and i['games'] >= 5]
    worst_items = sorted(worst_items, key=lambda x: x['avg_placement'], reverse=True)
    for i in worst_items[:5]:
        recommendations.append(f"  {i['item']}: {i['top4_rate']:.0f}% top4 ({i['games']} games, avg {i['avg_placement']:.1f})")
    
    return recommendations

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("Loading data...")
    
    # Load reference data
    champs = load_champions()
    traits = load_traits()
    
    # Load match data
    df = pd.read_csv('match_data.csv')
    print(f"Loaded {len(df)} matches")
    
    # Parse matches
    print("Parsing match data...")
    games = parse_match_data(df, champs)
    
    # Run analyses
    print("Analyzing trait performance...")
    trait_perf = analyze_trait_performance(games)
    
    print("Analyzing carry performance...")
    carry_perf = analyze_carry_performance(games, champs)
    
    print("Analyzing item performance...")
    item_perf = analyze_item_performance(games)
    
    print("Analyzing level curve...")
    level_perf = analyze_level_performance(games)
    
    print("Analyzing game length...")
    length_perf = analyze_game_length(games)
    
    print("Analyzing board value...")
    value_perf = analyze_board_value(games)
    
    # Generate report
    print("\n" + "="*70)
    print("TFT SET 16 DIAGNOSTIC REPORT")
    print("="*70 + "\n")
    
    # Recommendations
    recommendations = generate_recommendations(games, trait_perf, carry_perf, item_perf)
    for line in recommendations:
        print(line)
    
    print("\n=== LEVEL CURVE ANALYSIS ===")
    for l in level_perf:
        print(f"  Level {l['level']}: {l['top4_rate']:.0f}% top4 ({l['games']} games)")
    
    print("\n=== GAME LENGTH ANALYSIS ===")
    for g in length_perf:
        print(f"  {g['quartile']}: {g['top4_rate']:.0f}% top4 ({g['games']} games, avg placement {g['avg_placement']:.1f})")
    
    print("\n=== BOARD VALUE ANALYSIS ===")
    for v in value_perf:
        print(f"  {v['quartile']}: {v['top4_rate']:.0f}% top4 (avg value: {v['avg_value']:.0f})")
    
    # Save detailed data for further analysis
    pd.DataFrame(trait_perf).to_csv('trait_performance.csv', index=False)
    pd.DataFrame(carry_perf).to_csv('carry_performance.csv', index=False)
    pd.DataFrame(item_perf).to_csv('item_performance.csv', index=False)
    
    print("\n" + "="*70)
    print("Detailed CSVs saved: trait_performance.csv, carry_performance.csv, item_performance.csv")
    print("="*70)
    
    return games, trait_perf, carry_perf, item_perf

if __name__ == "__main__":
    main()
