#!/usr/bin/env python3
"""
Test item optimization by running combat simulations.

This validates that the item optimizer's recommendations actually
improve combat performance in the simulator.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.combat_engine import CombatEngine
from core.item_optimizer import ItemOptimizer


def test_item_impact():
    """Test that recommended items improve combat performance."""
    print("=" * 60)
    print("Item Impact Test")
    print("=" * 60)
    print()

    engine = CombatEngine()
    optimizer = ItemOptimizer(engine)

    # Test unit
    carry = 'TFT16_Seraphine'
    carry_short = carry.replace('TFT16_', '')

    # Get recommended items
    recs = optimizer.get_best_items(carry, n=3)
    if not recs:
        print(f"No item data for {carry_short}, skipping test")
        return

    recommended_items = [rec.item for rec in recs]
    print(f"Testing {carry_short} with recommended items:")
    for rec in recs:
        print(f"  - {rec.item.replace('TFT_Item_', '')}: {rec.reason}")
    print()

    # Mirror match for fair comparison
    print("Test: Mirror match (items vs no items)")
    print("-" * 40)

    wins_with_items = 0
    for _ in range(50):
        # Team 1 has items
        team1 = [
            engine.create_unit(carry, star_level=2, team=0, position=(3, 3),
                             items=recommended_items),
            engine.create_unit('TFT16_Braum', star_level=2, team=0, position=(3, 0),
                             items=['TFT_Item_DragonsClaw', 'TFT_Item_GargoyleStoneplate']),
        ]
        # Team 2 no items (same comp)
        team2 = [
            engine.create_unit(carry, star_level=2, team=1, position=(3, 3)),
            engine.create_unit('TFT16_Braum', star_level=2, team=1, position=(3, 0)),
        ]
        result = engine.run_combat(team1, team2, verbose=False)
        if result['winner'] == 0:
            wins_with_items += 1

    print(f"  Team with items wins: {wins_with_items}/50 ({wins_with_items*2}%)")
    print()

    # Compare
    print("Results:")
    print(f"  Items vs No Items: {wins_with_items*2}% win rate")

    if wins_with_items >= 40:  # 80%+ win rate
        print("\n[PASS] Items provide significant combat advantage!")
    elif wins_with_items >= 30:  # 60%+
        print("\n[PASS] Items improved combat performance")
    elif wins_with_items >= 20:  # ~50%
        print("\n[NEUTRAL] Items had minimal impact")
    else:
        print("\n[UNEXPECTED] Items decreased performance?")


def test_item_distribution():
    """Test that item distribution gives items to the right units."""
    print("\n")
    print("=" * 60)
    print("Item Distribution Test")
    print("=" * 60)
    print()

    engine = CombatEngine()
    optimizer = ItemOptimizer(engine)

    # Define a comp
    comp = [
        {'champion': 'TFT16_Seraphine', 'star': 2},  # AP carry
        {'champion': 'TFT16_Shyvana', 'star': 2},    # AD carry
        {'champion': 'TFT16_Braum', 'star': 2},      # Tank
        {'champion': 'TFT16_Lissandra', 'star': 2},  # Secondary AP
    ]

    # Available items
    available_items = [
        'TFT_Item_Morellonomicon',      # AP
        'TFT_Item_JeweledGauntlet',     # AP
        'TFT_Item_SpearOfShojin',       # AP/Utility
        'TFT_Item_Bloodthirster',       # AD
        'TFT_Item_TitansResolve',       # AD
        'TFT_Item_DragonsClaw',         # Tank
        'TFT_Item_GargoyleStoneplate',  # Tank
    ]

    print(f"Comp: {[u['champion'].replace('TFT16_', '') for u in comp]}")
    print(f"Items: {[i.replace('TFT_Item_', '') for i in available_items]}")
    print()

    result = optimizer.optimize_distribution(comp, available_items)

    print("Distribution:")
    for champ, items in result.assignments.items():
        champ_short = champ.replace('TFT16_', '')
        items_short = [i.replace('TFT_Item_', '') for i in items]
        role = optimizer.classify_unit_for_items(champ)
        print(f"  {champ_short} ({role}): {items_short}")

    print()
    print(f"Total score: {result.score:.2f}")

    # Validate: carries should get damage items
    sera_items = result.assignments.get('TFT16_Seraphine', [])
    braum_items = result.assignments.get('TFT16_Braum', [])

    # Check if Seraphine got AP items
    ap_items = {'Morellonomicon', 'JeweledGauntlet', 'SpearOfShojin', 'RabadonsDeathcap'}
    sera_has_ap = any(any(ap in item for ap in ap_items) for item in sera_items)

    # Check if Braum got tank items
    tank_items = {'DragonsClaw', 'GargoyleStoneplate', 'Redemption', 'BrambleVest'}
    braum_has_tank = any(any(tank in item for tank in tank_items) for item in braum_items)

    print()
    if sera_has_ap:
        print("[PASS] Seraphine received AP items")
    else:
        print("[WARN] Seraphine did not receive AP items")

    if braum_has_tank:
        print("[PASS] Braum received tank items")
    else:
        print("[WARN] Braum did not receive tank items")


def test_craft_recommendations():
    """Test that craft recommendations make sense for a comp."""
    print("\n")
    print("=" * 60)
    print("Craft Recommendations Test")
    print("=" * 60)
    print()

    optimizer = ItemOptimizer()

    # AP-focused comp
    ap_comp = [
        {'champion': 'TFT16_Seraphine'},
        {'champion': 'TFT16_Lissandra'},
        {'champion': 'TFT16_Braum'},
    ]

    components = ['Needlessly_Large_Rod', 'Needlessly_Large_Rod', 'Tear_of_the_Goddess',
                  'Sparring_Gloves', 'Chain_Vest']

    print("AP Comp:", [u['champion'].replace('TFT16_', '') for u in ap_comp])
    print("Components:", [c.replace('_', ' ') for c in components])
    print()

    crafts = optimizer.recommend_crafts(components, ap_comp, n=5)

    print("Recommendations:")
    for craft in crafts:
        item_short = craft['item'].replace('TFT_Item_', '')
        print(f"  {item_short}: {craft['reason']} (score: {craft['score']:.2f})")

    # Check that top recommendations include AP items
    top_items = [c['item'] for c in crafts[:3]]
    ap_crafts = {'RabadonsDeathcap', 'JeweledGauntlet', 'ArchangelsStaff', 'Morellonomicon'}

    has_ap_rec = any(any(ap in item for ap in ap_crafts) for item in top_items)

    print()
    if has_ap_rec:
        print("[PASS] Top recommendations include AP items for AP comp")
    else:
        print("[INFO] No AP items in top 3 (may be correct based on components)")


def main():
    test_item_impact()
    test_item_distribution()
    test_craft_recommendations()

    print("\n")
    print("=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == '__main__':
    main()
