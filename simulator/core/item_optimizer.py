#!/usr/bin/env python3
"""
TFT Item Optimizer

Given a team composition and available items/components, find optimal item
assignments by analyzing win rates and running combat simulations.

Features:
1. Item recommendations per unit based on MetaTFT data
2. Optimal item distribution across a comp
3. Component-to-item crafting recommendations
4. Slam vs Hold analysis

Usage:
    from core.item_optimizer import ItemOptimizer

    optimizer = ItemOptimizer()

    # Get best items for a unit
    best = optimizer.get_best_items('TFT16_Seraphine', n=3)

    # Find optimal item distribution for a comp
    comp = [
        {'champion': 'TFT16_Seraphine', 'star': 2},
        {'champion': 'TFT16_Braum', 'star': 2},
    ]
    available_items = ['TFT_Item_Leviathan', 'TFT_Item_DragonsClaw', ...]
    result = optimizer.optimize_distribution(comp, available_items)
"""

import json
import random
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.combat_engine import CombatEngine


# Item components and their combinations
COMPONENTS = {
    'BF_Sword': 'BF',
    'Recurve_Bow': 'Bow',
    'Needlessly_Large_Rod': 'Rod',
    'Tear_of_the_Goddess': 'Tear',
    'Chain_Vest': 'Vest',
    'Negatron_Cloak': 'Cloak',
    'Giants_Belt': 'Belt',
    'Sparring_Gloves': 'Glove',
    'Spatula': 'Spat',
}

# Component combinations -> completed items
# Format: (component1, component2) -> item_name
ITEM_RECIPES = {
    ('BF_Sword', 'BF_Sword'): 'TFT_Item_Deathblade',
    ('BF_Sword', 'Recurve_Bow'): 'TFT_Item_GiantSlayer',
    ('BF_Sword', 'Needlessly_Large_Rod'): 'TFT_Item_HextechGunblade',
    ('BF_Sword', 'Tear_of_the_Goddess'): 'TFT_Item_SpearOfShojin',
    ('BF_Sword', 'Chain_Vest'): 'TFT_Item_GuardianAngel',
    ('BF_Sword', 'Negatron_Cloak'): 'TFT_Item_Bloodthirster',
    ('BF_Sword', 'Giants_Belt'): 'TFT_Item_SteraksGage',
    ('BF_Sword', 'Sparring_Gloves'): 'TFT_Item_InfinityEdge',

    ('Recurve_Bow', 'Recurve_Bow'): 'TFT_Item_LastWhisper',
    ('Recurve_Bow', 'Needlessly_Large_Rod'): 'TFT_Item_GuinsoosRageblade',
    ('Recurve_Bow', 'Tear_of_the_Goddess'): 'TFT_Item_StatikkShiv',
    ('Recurve_Bow', 'Chain_Vest'): 'TFT_Item_TitansResolve',
    ('Recurve_Bow', 'Negatron_Cloak'): 'TFT_Item_RunaansHurricane',
    ('Recurve_Bow', 'Giants_Belt'): 'TFT_Item_RedBuff',
    ('Recurve_Bow', 'Sparring_Gloves'): 'TFT_Item_MadredsBloodrazor',

    ('Needlessly_Large_Rod', 'Needlessly_Large_Rod'): 'TFT_Item_RabadonsDeathcap',
    ('Needlessly_Large_Rod', 'Tear_of_the_Goddess'): 'TFT_Item_ArchangelsStaff',
    ('Needlessly_Large_Rod', 'Chain_Vest'): 'TFT_Item_IonicSpark',
    ('Needlessly_Large_Rod', 'Negatron_Cloak'): 'TFT_Item_Morellonomicon',
    ('Needlessly_Large_Rod', 'Giants_Belt'): 'TFT_Item_Leviathan',
    ('Needlessly_Large_Rod', 'Sparring_Gloves'): 'TFT_Item_JeweledGauntlet',

    ('Tear_of_the_Goddess', 'Tear_of_the_Goddess'): 'TFT_Item_BlueBuff',
    ('Tear_of_the_Goddess', 'Chain_Vest'): 'TFT_Item_FrozenHeart',
    ('Tear_of_the_Goddess', 'Negatron_Cloak'): 'TFT_Item_Crownguard',
    ('Tear_of_the_Goddess', 'Giants_Belt'): 'TFT_Item_Redemption',
    ('Tear_of_the_Goddess', 'Sparring_Gloves'): 'TFT_Item_HandOfJustice',

    ('Chain_Vest', 'Chain_Vest'): 'TFT_Item_BrambleVest',
    ('Chain_Vest', 'Negatron_Cloak'): 'TFT_Item_GargoyleStoneplate',
    ('Chain_Vest', 'Giants_Belt'): 'TFT_Item_SunfireCape',
    ('Chain_Vest', 'Sparring_Gloves'): 'TFT_Item_Quicksilver',

    ('Negatron_Cloak', 'Negatron_Cloak'): 'TFT_Item_DragonsClaw',
    ('Negatron_Cloak', 'Giants_Belt'): 'TFT_Item_NightHarvester',
    ('Negatron_Cloak', 'Sparring_Gloves'): 'TFT_Item_AdaptiveHelm',

    ('Giants_Belt', 'Giants_Belt'): 'TFT_Item_WarmogsArmor',
    ('Giants_Belt', 'Sparring_Gloves'): 'TFT_Item_UnstableConcoction',

    ('Sparring_Gloves', 'Sparring_Gloves'): 'TFT_Item_ThiefsGloves',
}

# Make recipe lookup bidirectional
for (c1, c2), item in list(ITEM_RECIPES.items()):
    if c1 != c2:
        ITEM_RECIPES[(c2, c1)] = item

# Reverse lookup: item -> components
ITEM_COMPONENTS = {v: k for k, v in ITEM_RECIPES.items()}


@dataclass
class ItemRecommendation:
    """A single item recommendation for a unit."""
    item: str
    score: float  # Combined score (0-1)
    top4_rate: float
    avg_place: float
    games: int
    reason: str


@dataclass
class ItemDistribution:
    """An assignment of items to units in a comp."""
    assignments: Dict[str, List[str]]  # champion -> [items]
    score: float
    details: Dict[str, List[ItemRecommendation]]


class ItemOptimizer:
    """
    Optimizes item assignments for TFT compositions.
    """

    def __init__(self, engine: CombatEngine = None):
        """Initialize optimizer."""
        self.engine = engine or CombatEngine()
        self.item_data = self._load_item_data()

    def _load_item_data(self) -> Optional[Dict]:
        """Load MetaTFT item data if available."""
        data_path = Path(__file__).parent.parent / "data" / "metatft_items.json"
        if data_path.exists():
            try:
                with open(data_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def get_unit_item_data(self, champion_id: str) -> Dict:
        """Get item data for a specific unit."""
        if not self.item_data:
            return {}
        return self.item_data.get(champion_id, {})

    def get_best_items(self, champion_id: str, n: int = 3,
                       available: List[str] = None,
                       exclude: Set[str] = None,
                       include_special: bool = False) -> List[ItemRecommendation]:
        """
        Get the N best items for a champion.

        Args:
            champion_id: Unit ID like 'TFT16_Seraphine'
            n: Number of recommendations
            available: If provided, only consider these items
            exclude: Items to exclude from recommendations
            include_special: Include radiants/artifacts/emblems

        Returns:
            List of ItemRecommendation objects
        """
        unit_data = self.get_unit_item_data(champion_id)
        best_items = unit_data.get('best_items', [])
        frequency_ranked = unit_data.get('frequency_ranked', [])

        recommendations = []
        exclude = exclude or set()
        seen_items = set()

        # First pass: items with win rate data
        for item_info in best_items:
            item_name = item_info.get('item', '')

            # Skip if excluded or not available
            if item_name in exclude:
                continue
            if available and item_name not in available:
                continue

            # Skip radiants/artifacts/emblems unless requested
            if not include_special:
                if any(x in item_name for x in ['Radiant', 'Artifact', 'Emblem', 'Ornn', 'TFT5_', 'TFT4_']):
                    continue

            top4 = item_info.get('top4_rate', 0)
            avg = item_info.get('avg_place', 4.5)
            games = item_info.get('total_games', 0)

            # Calculate score (weighted: top4 rate most important)
            # Normalize avg_place: 1.0 = avg 1, 0.0 = avg 8
            avg_score = (8 - avg) / 7
            score = top4 * 0.7 + avg_score * 0.3

            # Boost if also high frequency (people use it a lot)
            if item_name in frequency_ranked[:5]:
                score *= 1.1  # 10% boost for popular items

            # Determine reason
            if top4 > 0.65:
                reason = f"High win rate ({top4:.0%} top4)"
            elif item_name in frequency_ranked[:3]:
                reason = "Most popular choice"
            else:
                reason = f"Good performance ({top4:.0%} top4)"

            recommendations.append(ItemRecommendation(
                item=item_name,
                score=min(score, 1.0),
                top4_rate=top4,
                avg_place=avg,
                games=games,
                reason=reason
            ))
            seen_items.add(item_name)

        # Second pass: add frequency-ranked items if we don't have enough
        # These are the most commonly used items (validated by community)
        if len(recommendations) < n:
            for rank, item_name in enumerate(frequency_ranked):
                if len(recommendations) >= n * 2:  # Get extras to sort
                    break
                if item_name in seen_items or item_name in exclude:
                    continue
                if available and item_name not in available:
                    continue

                # Skip special items
                if not include_special:
                    if any(x in item_name for x in ['Radiant', 'Artifact', 'Emblem', 'Ornn', 'TFT5_', 'TFT4_']):
                        continue

                # Estimate score based on frequency rank
                # Higher rank = more popular = likely good
                score = 0.8 - (rank * 0.05)  # Top item = 0.8, 5th = 0.55, etc.
                score = max(score, 0.3)

                recommendations.append(ItemRecommendation(
                    item=item_name,
                    score=score,
                    top4_rate=0,  # Unknown
                    avg_place=0,  # Unknown
                    games=0,
                    reason=f"Popular choice (#{rank+1} most used)"
                ))
                seen_items.add(item_name)

        # Sort by score descending
        recommendations.sort(key=lambda x: -x.score)
        return recommendations[:n]

    def get_best_build(self, champion_id: str) -> Optional[List[str]]:
        """
        Get the best 3-item build for a champion.

        Returns list of 3 item names or None.
        """
        unit_data = self.get_unit_item_data(champion_id)
        builds = unit_data.get('best_builds', [])

        for build in builds:
            items = build.get('items', [])
            # Look for 3-item build with craftable items
            if len(items) == 3:
                # Skip if contains radiants/artifacts
                if any('Radiant' in i or 'Artifact' in i or 'Ornn' in i for i in items):
                    continue
                return items

        return None

    def classify_unit_for_items(self, champion_id: str) -> str:
        """
        Classify a unit's item needs: 'carry', 'tank', 'support'.
        """
        champ_data = self.engine.champions.get(champion_id, {})
        traits = champ_data.get('traits', [])
        cost = champ_data.get('cost', 1)
        stats = champ_data.get('stats', {})

        # High-cost units with damage traits are carries
        damage_traits = {'Longshot', 'Arcanist', 'Gunslinger', 'Star Forger',
                         'Emperor', 'Eternal', 'Sorcerer'}
        tank_traits = {'Defender', 'Warden', 'Bastion', 'Juggernaut'}

        has_damage = any(t in damage_traits for t in traits)
        has_tank = any(t in tank_traits for t in traits)

        if cost >= 4 and has_damage:
            return 'carry'
        elif has_tank:
            return 'tank'
        elif cost >= 4:
            return 'secondary_carry'
        else:
            return 'support'

    def optimize_distribution(self, comp: List[Dict],
                              available_items: List[str],
                              max_items_per_unit: int = 3) -> ItemDistribution:
        """
        Find optimal distribution of items across a composition.

        Args:
            comp: List of unit definitions with 'champion' key
            available_items: List of item names to distribute
            max_items_per_unit: Maximum items per unit (default 3)

        Returns:
            ItemDistribution with assignments and scores
        """
        # Classify units by priority
        unit_priorities = []
        for unit_def in comp:
            champ = unit_def['champion']
            role = self.classify_unit_for_items(champ)

            priority = {'carry': 0, 'secondary_carry': 1, 'tank': 2, 'support': 3}
            unit_priorities.append((champ, priority.get(role, 3), role))

        # Sort by priority (carries first)
        unit_priorities.sort(key=lambda x: x[1])

        # Greedy assignment: give best items to highest priority units
        assignments = {unit_def['champion']: [] for unit_def in comp}
        details = {unit_def['champion']: [] for unit_def in comp}
        used_items = set()
        total_score = 0

        for champ, _, role in unit_priorities:
            remaining_slots = max_items_per_unit - len(assignments[champ])
            remaining_items = [i for i in available_items if i not in used_items]

            if remaining_slots <= 0 or not remaining_items:
                continue

            # Get best items for this unit from available
            recs = self.get_best_items(
                champ,
                n=remaining_slots,
                available=remaining_items,
                exclude=used_items
            )

            for rec in recs:
                if len(assignments[champ]) >= max_items_per_unit:
                    break
                if rec.item in used_items:
                    continue

                assignments[champ].append(rec.item)
                details[champ].append(rec)
                used_items.add(rec.item)
                total_score += rec.score

        # Normalize score
        num_assigned = sum(len(items) for items in assignments.values())
        avg_score = total_score / num_assigned if num_assigned > 0 else 0

        return ItemDistribution(
            assignments=assignments,
            score=avg_score,
            details=details
        )

    def recommend_crafts(self, components: List[str],
                         comp: List[Dict] = None,
                         n: int = 3) -> List[Dict]:
        """
        Recommend what items to craft from available components.

        Args:
            components: List of component names
            comp: Optional comp to consider for recommendations
            n: Number of recommendations

        Returns:
            List of craft recommendations with item, components, and reason
        """
        # Find all possible crafts
        possible_crafts = []
        component_counts = {}
        for c in components:
            component_counts[c] = component_counts.get(c, 0) + 1

        checked = set()
        for c1 in components:
            for c2 in components:
                if (c1, c2) in checked or (c2, c1) in checked:
                    continue
                checked.add((c1, c2))

                # Check if we have the components
                if c1 == c2 and component_counts.get(c1, 0) < 2:
                    continue

                item = ITEM_RECIPES.get((c1, c2))
                if item:
                    possible_crafts.append({
                        'item': item,
                        'components': (c1, c2),
                        'score': 0,
                        'reason': ''
                    })

        # Score each craft
        if comp:
            # Score based on how good the item is for units in comp
            for craft in possible_crafts:
                item_name = craft['item']
                best_score = 0
                best_unit = None

                for unit_def in comp:
                    champ = unit_def['champion']
                    recs = self.get_best_items(champ, n=10)

                    for rec in recs:
                        if rec.item == item_name:
                            if rec.score > best_score:
                                best_score = rec.score
                                best_unit = champ
                            break

                craft['score'] = best_score
                if best_unit:
                    craft['reason'] = f"Good for {best_unit.replace('TFT16_', '')}"
                else:
                    craft['reason'] = "Flexible item"
        else:
            # Generic scoring based on item type
            for craft in possible_crafts:
                item_name = craft['item']

                # Offensive items score higher (generally more impactful)
                if any(x in item_name for x in ['InfinityEdge', 'JeweledGauntlet',
                                                  'Deathcap', 'Leviathan', 'Shojin']):
                    craft['score'] = 0.8
                    craft['reason'] = "Strong carry item"
                elif any(x in item_name for x in ['GargoyleStoneplate', 'DragonsClaw',
                                                   'BrambleVest', 'Redemption']):
                    craft['score'] = 0.7
                    craft['reason'] = "Solid tank item"
                else:
                    craft['score'] = 0.5
                    craft['reason'] = "Utility item"

        # Sort by score
        possible_crafts.sort(key=lambda x: -x['score'])
        return possible_crafts[:n]

    def should_slam(self, components: List[str],
                    stage: str,
                    comp: List[Dict] = None,
                    current_hp: int = 100) -> Dict:
        """
        Analyze whether to slam (craft) items now or hold components.

        Args:
            components: Current component inventory
            stage: Current game stage (e.g., '2-1', '3-2')
            comp: Current composition
            current_hp: Current HP

        Returns:
            Dict with recommendation and reasoning
        """
        # Parse stage
        stage_num = float(stage.replace('-', '.')) if '-' in stage else float(stage)

        # Count components
        num_components = len(components)

        # Get possible crafts
        crafts = self.recommend_crafts(components, comp, n=5)

        # Decision factors
        factors = []
        slam_score = 0

        # 1. Stage timing
        if stage_num >= 4.0:
            factors.append("Late game - slam to stabilize")
            slam_score += 0.3
        elif stage_num >= 3.0:
            factors.append("Mid game - consider slamming")
            slam_score += 0.1
        else:
            factors.append("Early game - can hold for better items")
            slam_score -= 0.1

        # 2. HP pressure
        if current_hp < 50:
            factors.append(f"Low HP ({current_hp}) - need power now")
            slam_score += 0.4
        elif current_hp < 70:
            factors.append(f"Moderate HP ({current_hp}) - slight pressure")
            slam_score += 0.1

        # 3. Component overflow
        if num_components >= 6:
            factors.append(f"Bench pressure ({num_components} components)")
            slam_score += 0.2
        elif num_components >= 4:
            factors.append(f"Some components ({num_components})")
            slam_score += 0.1

        # 4. Quality of available crafts
        if crafts:
            best_craft = crafts[0]
            if best_craft['score'] >= 0.7:
                factors.append(f"Strong craft available: {best_craft['item']}")
                slam_score += 0.2
            elif best_craft['score'] >= 0.5:
                factors.append(f"Decent craft available: {best_craft['item']}")
                slam_score += 0.1
            else:
                factors.append("No great crafts available")
                slam_score -= 0.1

        # Make decision
        if slam_score >= 0.4:
            decision = "SLAM"
            confidence = min(slam_score, 1.0)
        elif slam_score <= -0.1:
            decision = "HOLD"
            confidence = min(abs(slam_score), 1.0)
        else:
            decision = "FLEXIBLE"
            confidence = 0.5

        return {
            'decision': decision,
            'confidence': confidence,
            'factors': factors,
            'best_crafts': crafts[:3],
            'slam_score': slam_score
        }


def demo():
    """Demonstrate item optimizer."""
    print("=" * 60)
    print("TFT Item Optimizer Demo")
    print("=" * 60)
    print()

    optimizer = ItemOptimizer()

    # Check if data is loaded
    if not optimizer.item_data:
        print("WARNING: MetaTFT item data not found.")
        print("Run: python fetch_metatft_items.py --save-all")
        print()

    # Demo 1: Best items for a unit
    print("1. Best Items for Seraphine")
    print("-" * 40)
    recs = optimizer.get_best_items('TFT16_Seraphine', n=5)
    for rec in recs:
        item_short = rec.item.replace('TFT_Item_', '')
        print(f"  {item_short:25} | Score: {rec.score:.2f} | {rec.reason}")

    print()

    # Demo 2: Best build
    print("2. Best 3-Item Build for Shyvana")
    print("-" * 40)
    build = optimizer.get_best_build('TFT16_Shyvana')
    if build:
        print(f"  Build: {[i.replace('TFT_Item_', '') for i in build]}")
    else:
        print("  No build data available")

    print()

    # Demo 3: Craft recommendations
    print("3. Craft Recommendations")
    print("-" * 40)
    components = ['BF_Sword', 'Needlessly_Large_Rod', 'Tear_of_the_Goddess',
                  'Chain_Vest', 'Recurve_Bow']
    print(f"  Components: {components}")
    print()

    crafts = optimizer.recommend_crafts(components)
    for craft in crafts:
        item_short = craft['item'].replace('TFT_Item_', '')
        c1, c2 = craft['components']
        print(f"  {item_short:25} ({c1} + {c2})")
        print(f"    {craft['reason']}")

    print()

    # Demo 4: Slam vs Hold
    print("4. Slam vs Hold Analysis")
    print("-" * 40)
    analysis = optimizer.should_slam(
        components=components,
        stage='3-2',
        current_hp=65
    )
    print(f"  Decision: {analysis['decision']} (confidence: {analysis['confidence']:.0%})")
    print(f"  Factors:")
    for factor in analysis['factors']:
        print(f"    - {factor}")

    return optimizer


if __name__ == "__main__":
    demo()
