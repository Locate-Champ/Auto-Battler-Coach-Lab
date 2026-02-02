"""
Extract Set 16 champion data from CommunityDragon TFT JSON.

Extracts comprehensive champion data including:
- Base stats (HP, AD, AS, Armor, MR, Range, Mana)
- Ability details and damage values
- Traits

Output: set16_champions.json with complete champion data
"""

import json
from pathlib import Path


def extract_set16_champions():
    """Extract all TFT Set 16 champions from the CommunityDragon data."""

    input_file = Path(__file__).parent / "cdragon_tft_en_us.json"
    output_file = Path(__file__).parent / "set16_champions.json"

    print(f"Loading {input_file.name}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Find Set 16 data
    set16_data = None
    for set_entry in data.get('setData', []):
        if set_entry.get('mutator') == 'TFTSet16':
            set16_data = set_entry
            break

    if not set16_data:
        print("ERROR: Could not find TFTSet16 data!")
        return

    print(f"Found Set 16: {set16_data.get('name')}")

    # Extract champions (only TFT16_ prefixed ones - the actual playable units)
    champions = {}
    all_champions = set16_data.get('champions', [])

    print(f"Total champions in set data: {len(all_champions)}")

    for champ in all_champions:
        api_name = champ.get('apiName', '')

        # Only include actual Set 16 champions (not PvE units, training dummies, etc.)
        if not api_name.startswith('TFT16_'):
            continue

        # Skip summons and carousel units
        if any(skip in api_name.lower() for skip in ['soldier', 'turret', 'tibbers', 'carousel', 'voidling']):
            continue

        stats = champ.get('stats', {})
        ability = champ.get('ability', {})

        # Parse ability variables into a cleaner format
        ability_vars = {}
        for var in ability.get('variables', []):
            name = var.get('name', '')
            values = var.get('value', [])
            if name and values:
                # values are typically [base, 1star, 2star, 3star, 4star?, ...]
                ability_vars[name] = {
                    'base': values[0] if len(values) > 0 else None,
                    '1star': values[1] if len(values) > 1 else None,
                    '2star': values[2] if len(values) > 2 else None,
                    '3star': values[3] if len(values) > 3 else None,
                }

        champion_data = {
            'apiName': api_name,
            'name': champ.get('name', '').strip(),
            'cost': champ.get('cost', 0),
            'traits': champ.get('traits', []),
            'role': champ.get('role', ''),
            'stats': {
                'hp': stats.get('hp'),
                'damage': stats.get('damage'),
                'attackSpeed': stats.get('attackSpeed'),
                'armor': stats.get('armor'),
                'magicResist': stats.get('magicResist'),
                'range': stats.get('range'),
                'mana': stats.get('mana'),
                'initialMana': stats.get('initialMana'),
                'critChance': stats.get('critChance'),
                'critMultiplier': stats.get('critMultiplier'),
            },
            'ability': {
                'name': ability.get('name', ''),
                'desc': ability.get('desc', ''),
                'variables': ability_vars,
            }
        }

        champions[api_name] = champion_data

    print(f"Extracted {len(champions)} Set 16 champions")

    # Also extract traits
    traits = {}
    for trait in set16_data.get('traits', []):
        api_name = trait.get('apiName', '')
        if api_name.startswith('TFT16_'):
            traits[api_name] = {
                'name': trait.get('name', ''),
                'desc': trait.get('desc', ''),
                'effects': trait.get('effects', [])
            }

    print(f"Extracted {len(traits)} Set 16 traits")

    # Create output
    output = {
        'set': 16,
        'patch': 'TFTSet16',
        'champions': champions,
        'traits': traits,
    }

    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to: {output_file}")

    # Print summary by cost
    print("\n=== Champions by Cost ===")
    for cost in range(1, 6):
        cost_champs = [c for c in champions.values() if c['cost'] == cost]
        print(f"{cost}-cost ({len(cost_champs)}): {', '.join(sorted([c['name'] for c in cost_champs]))}")

    return output


if __name__ == '__main__':
    extract_set16_champions()
