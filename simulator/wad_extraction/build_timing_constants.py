"""
Build timing_constants.json by combining:
1. Champion stats from CommunityDragon TFT data
2. Animation timing from extracted WAD BIN files

This creates a comprehensive dataset for the TFT combat simulator.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Constants
SCRIPT_DIR = Path(__file__).parent
JSON_DIR = SCRIPT_DIR / "json" / "TFTSet16" / "data" / "characters"
CDRAGON_FILE = SCRIPT_DIR / "cdragon_tft_en_us.json"
OUTPUT_FILE = SCRIPT_DIR.parent / "data" / "timing_constants.json"

# Standard animation FPS for League/TFT (usually 30 FPS)
ANIMATION_FPS = 30.0


def load_cdragon_champions() -> Dict[str, Dict]:
    """Load champion stats from CommunityDragon."""
    with open(CDRAGON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    champions = {}
    for set_data in data.get('setData', []):
        if set_data.get('number') != 16:
            continue
        if 'champions' not in set_data:
            continue

        for champ in set_data['champions']:
            api_name = champ.get('apiName', '')
            if api_name.startswith('TFT16_'):
                champions[api_name] = champ
        break  # Only need first Set 16 entry

    return champions


def extract_animation_timing(champ_dir: Path) -> Dict[str, Any]:
    """Extract timing data from animation BIN files."""
    timing = {
        'attack_frames': {},
        'spell_frames': {},
        'tick_durations': {},
        'event_frames': {}
    }

    anim_file = champ_dir / 'animations' / 'skin0.json'
    if not anim_file.exists():
        return timing

    try:
        with open(anim_file, 'r', encoding='utf-8') as f:
            anim = json.load(f)
    except (json.JSONDecodeError, IOError):
        return timing

    for key, val in anim.items():
        if not isinstance(val, dict) or 'mClipDataMap' not in val:
            continue

        clip_map = val['mClipDataMap']
        for clip_name, clip_data in clip_map.items():
            if not isinstance(clip_data, dict):
                continue

            # Get tick duration if present
            if 'mTickDuration' in clip_data:
                timing['tick_durations'][clip_name] = clip_data['mTickDuration']

            # Get event timing (particle spawns, sounds, etc.)
            if 'mEventDataMap' in clip_data:
                for event_name, event_data in clip_data['mEventDataMap'].items():
                    if isinstance(event_data, dict) and 'mStartFrame' in event_data:
                        # Categorize by clip type
                        if 'attack' in clip_name.lower():
                            if 'attack_frames' not in timing:
                                timing['attack_frames'] = {}
                            timing['attack_frames'][clip_name] = event_data['mStartFrame']
                        elif 'spell' in clip_name.lower() or 'ult' in clip_name.lower():
                            if 'spell_frames' not in timing:
                                timing['spell_frames'] = {}
                            timing['spell_frames'][clip_name] = event_data['mStartFrame']
                        else:
                            timing['event_frames'][f"{clip_name}_{event_name}"] = event_data['mStartFrame']

    return timing


def frames_to_seconds(frames: float, fps: float = ANIMATION_FPS) -> float:
    """Convert animation frames to seconds."""
    return frames / fps


def build_champion_timing(api_name: str, cdragon_data: Dict, anim_timing: Dict) -> Dict[str, Any]:
    """Build comprehensive timing data for a champion."""
    stats = cdragon_data.get('stats', {})
    ability = cdragon_data.get('ability', {})

    # Calculate attack timing
    # Attack windup is typically the frame when the projectile/damage happens
    attack_frames = anim_timing.get('attack_frames', {})
    attack1_frame = None
    attack2_frame = None

    for name, frame in attack_frames.items():
        name_lower = name.lower()
        if 'attack1' in name_lower and attack1_frame is None:
            attack1_frame = frame
        elif 'attack2' in name_lower and attack2_frame is None:
            attack2_frame = frame
        elif 'crit' in name_lower:
            # Crit animations often have timing too
            pass

    # Use average attack frame or estimate
    if attack1_frame and attack2_frame:
        avg_attack_frame = (attack1_frame + attack2_frame) / 2
    elif attack1_frame:
        avg_attack_frame = attack1_frame
    elif attack2_frame:
        avg_attack_frame = attack2_frame
    else:
        avg_attack_frame = None

    # Get spell timing
    spell_frames = anim_timing.get('spell_frames', {})
    spell_cast_frame = None
    for name, frame in spell_frames.items():
        if spell_cast_frame is None or frame < spell_cast_frame:
            spell_cast_frame = frame

    # Build timing constants
    timing = {
        'api_name': api_name,
        'display_name': cdragon_data.get('name', api_name.replace('TFT16_', '')),
        'cost': cdragon_data.get('cost', 0),
        'traits': cdragon_data.get('traits', []),

        # Combat stats
        'stats': {
            'hp': stats.get('hp', 0),
            'damage': stats.get('damage', 0),
            'armor': stats.get('armor', 0),
            'magic_resist': stats.get('magicResist', 0),
            'attack_speed': stats.get('attackSpeed', 1.0),
            'crit_chance': stats.get('critChance', 0.25),
            'crit_multiplier': stats.get('critMultiplier', 1.4),
            'range': stats.get('range', 1),
            'mana': stats.get('mana', 0),
            'initial_mana': stats.get('initialMana', 0),
        },

        # Timing constants (in seconds)
        'timing': {
            # Attack timing
            'attack_windup_frames': avg_attack_frame,
            'attack_windup_seconds': frames_to_seconds(avg_attack_frame) if avg_attack_frame else None,
            'attack1_frame': attack1_frame,
            'attack2_frame': attack2_frame,

            # Spell timing
            'spell_cast_frame': spell_cast_frame,
            'spell_cast_seconds': frames_to_seconds(spell_cast_frame) if spell_cast_frame else None,

            # Source information
            'source': 'extracted' if avg_attack_frame or spell_cast_frame else 'inferred',
            'confidence': 'high' if avg_attack_frame else 'low',
        },

        # Ability data
        'ability': {
            'name': ability.get('name', '').strip() if ability.get('name') else None,
            'variables': {
                var['name']: var['value']
                for var in ability.get('variables', [])
                if 'name' in var and 'value' in var
            }
        },

        # Raw animation data for reference
        '_raw_animation': {
            'attack_frames': attack_frames,
            'spell_frames': spell_frames,
            'tick_durations': anim_timing.get('tick_durations', {}),
        }
    }

    return timing


def main():
    print("Building timing_constants.json...")

    # Load CommunityDragon data
    print("Loading CommunityDragon champion data...")
    cdragon_champions = load_cdragon_champions()
    print(f"  Found {len(cdragon_champions)} Set 16 champions")

    # Process each champion
    timing_constants = {}
    extracted_count = 0
    inferred_count = 0

    for api_name, cdragon_data in cdragon_champions.items():
        # Find animation data
        champ_folder = api_name.lower()
        champ_dir = JSON_DIR / champ_folder

        anim_timing = {}
        if champ_dir.exists():
            anim_timing = extract_animation_timing(champ_dir)

        # Build timing data
        champion_timing = build_champion_timing(api_name, cdragon_data, anim_timing)
        timing_constants[api_name] = champion_timing

        if champion_timing['timing']['source'] == 'extracted':
            extracted_count += 1
        else:
            inferred_count += 1

    # Summary
    print(f"\nProcessed {len(timing_constants)} champions:")
    print(f"  - Extracted timing: {extracted_count}")
    print(f"  - Inferred timing: {inferred_count}")

    # Save output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(timing_constants, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to: {OUTPUT_FILE}")

    # Also save a summary version without raw data
    summary_file = OUTPUT_FILE.parent / "timing_constants_summary.json"
    summary = {}
    for api_name, data in timing_constants.items():
        summary[api_name] = {
            'display_name': data['display_name'],
            'cost': data['cost'],
            'traits': data['traits'],
            'stats': data['stats'],
            'timing': {k: v for k, v in data['timing'].items() if not k.startswith('_')},
        }

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Saved summary to: {summary_file}")


if __name__ == "__main__":
    main()
