#!/usr/bin/env python3
"""
CLI for TFT Item Optimizer

Commands:
    python item_search.py best <unit>           - Get best items for a unit
    python item_search.py build <unit>          - Get best 3-item build
    python item_search.py craft <components>    - Recommend crafts from components
    python item_search.py slam <components>     - Slam vs hold analysis
    python item_search.py distribute            - Distribute items across a comp

Examples:
    python item_search.py best TFT16_Seraphine
    python item_search.py craft BF_Sword Rod Tear
    python item_search.py slam "BF Rod Tear Vest" --stage 3-2 --hp 65
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.item_optimizer import ItemOptimizer, COMPONENTS


# Short names for components
COMPONENT_ALIASES = {
    'bf': 'BF_Sword',
    'sword': 'BF_Sword',
    'bow': 'Recurve_Bow',
    'rod': 'Needlessly_Large_Rod',
    'tear': 'Tear_of_the_Goddess',
    'vest': 'Chain_Vest',
    'armor': 'Chain_Vest',
    'cloak': 'Negatron_Cloak',
    'mr': 'Negatron_Cloak',
    'belt': 'Giants_Belt',
    'hp': 'Giants_Belt',
    'glove': 'Sparring_Gloves',
    'gloves': 'Sparring_Gloves',
    'spat': 'Spatula',
    'spatula': 'Spatula',
}


def normalize_component(name: str) -> str:
    """Convert component alias to full name."""
    name_lower = name.lower().strip()
    if name_lower in COMPONENT_ALIASES:
        return COMPONENT_ALIASES[name_lower]
    # Try exact match
    for full_name in COMPONENTS:
        if name_lower == full_name.lower():
            return full_name
    # Partial match
    for full_name in COMPONENTS:
        if name_lower in full_name.lower():
            return full_name
    return name  # Return as-is


def normalize_unit(name: str) -> str:
    """Normalize unit name to TFT16_Name format."""
    name = name.strip()
    if name.startswith('TFT16_'):
        return name
    return f'TFT16_{name}'


def cmd_best(args):
    """Get best items for a unit."""
    optimizer = ItemOptimizer()
    unit = normalize_unit(args.unit)

    print(f"\nBest Items for {unit.replace('TFT16_', '')}")
    print("=" * 50)

    recs = optimizer.get_best_items(unit, n=args.count, include_special=args.special)

    if not recs:
        print("No item data found for this unit.")
        return

    print(f"{'Item':<30} {'Score':>7} {'Top4':>7} {'Avg':>5} {'Reason'}")
    print("-" * 70)

    for rec in recs:
        item_short = rec.item.replace('TFT_Item_', '').replace('TFT16_Item_', '')
        top4_str = f"{rec.top4_rate:.0%}" if rec.top4_rate > 0 else "-"
        avg_str = f"{rec.avg_place:.2f}" if rec.avg_place > 0 else "-"
        print(f"{item_short:<30} {rec.score:>7.2f} {top4_str:>7} {avg_str:>5}  {rec.reason}")


def cmd_build(args):
    """Get best 3-item build for a unit."""
    optimizer = ItemOptimizer()
    unit = normalize_unit(args.unit)

    print(f"\nBest Build for {unit.replace('TFT16_', '')}")
    print("=" * 50)

    build = optimizer.get_best_build(unit)

    if build:
        items = [i.replace('TFT_Item_', '') for i in build]
        print(f"Recommended: {' + '.join(items)}")
    else:
        print("No build data available.")
        print("\nFalling back to top 3 items:")
        recs = optimizer.get_best_items(unit, n=3)
        for rec in recs:
            print(f"  - {rec.item.replace('TFT_Item_', '')}")


def cmd_craft(args):
    """Recommend crafts from components."""
    optimizer = ItemOptimizer()

    # Parse components
    components = [normalize_component(c) for c in args.components]

    print(f"\nCraft Recommendations")
    print("=" * 50)
    print(f"Components: {[c.replace('_', ' ') for c in components]}")
    print()

    # Load comp if provided
    comp = None
    if args.comp:
        comp = [{'champion': normalize_unit(u)} for u in args.comp.split(',')]
        print(f"Comp: {[u['champion'].replace('TFT16_', '') for u in comp]}")
        print()

    crafts = optimizer.recommend_crafts(components, comp, n=args.count)

    if not crafts:
        print("No valid crafts from these components.")
        return

    print(f"{'Item':<25} {'Components':<35} {'Score':>6}")
    print("-" * 70)

    for craft in crafts:
        item_short = craft['item'].replace('TFT_Item_', '')
        c1, c2 = craft['components']
        c1_short = c1.replace('_', ' ')
        c2_short = c2.replace('_', ' ')
        components_str = f"{c1_short} + {c2_short}"
        print(f"{item_short:<25} {components_str:<35} {craft['score']:>6.2f}")
        print(f"  {craft['reason']}")


def cmd_slam(args):
    """Slam vs hold analysis."""
    optimizer = ItemOptimizer()

    # Parse components
    components = [normalize_component(c) for c in args.components]

    # Load comp if provided
    comp = None
    if args.comp:
        comp = [{'champion': normalize_unit(u)} for u in args.comp.split(',')]

    print(f"\nSlam vs Hold Analysis")
    print("=" * 50)
    print(f"Stage: {args.stage}")
    print(f"HP: {args.hp}")
    print(f"Components: {[c.replace('_', ' ') for c in components]}")
    if comp:
        print(f"Comp: {[u['champion'].replace('TFT16_', '') for u in comp]}")
    print()

    analysis = optimizer.should_slam(
        components=components,
        stage=args.stage,
        comp=comp,
        current_hp=args.hp
    )

    # Decision with color (if terminal supports it)
    decision = analysis['decision']
    confidence = analysis['confidence']

    if decision == 'SLAM':
        print(f">>> SLAM ({confidence:.0%} confidence)")
    elif decision == 'HOLD':
        print(f">>> HOLD ({confidence:.0%} confidence)")
    else:
        print(f">>> FLEXIBLE ({confidence:.0%} confidence)")

    print()
    print("Factors:")
    for factor in analysis['factors']:
        print(f"  - {factor}")

    print()
    print("Best Crafts:")
    for craft in analysis['best_crafts']:
        item_short = craft['item'].replace('TFT_Item_', '')
        print(f"  - {item_short}: {craft['reason']}")


def cmd_distribute(args):
    """Distribute items across a comp."""
    optimizer = ItemOptimizer()

    # Parse comp
    if not args.comp:
        # Use default comp
        comp = [
            {'champion': 'TFT16_Seraphine'},
            {'champion': 'TFT16_Braum'},
            {'champion': 'TFT16_Lissandra'},
            {'champion': 'TFT16_Vi'},
        ]
    else:
        comp = [{'champion': normalize_unit(u)} for u in args.comp.split(',')]

    # Parse items
    if not args.items:
        items = [
            'TFT_Item_Morellonomicon',
            'TFT_Item_JeweledGauntlet',
            'TFT_Item_SpearOfShojin',
            'TFT_Item_DragonsClaw',
            'TFT_Item_GargoyleStoneplate',
            'TFT_Item_Redemption',
        ]
    else:
        items = [f'TFT_Item_{i}' if not i.startswith('TFT_') else i
                 for i in args.items.split(',')]

    print(f"\nItem Distribution")
    print("=" * 50)
    print(f"Comp: {[u['champion'].replace('TFT16_', '') for u in comp]}")
    print(f"Items: {[i.replace('TFT_Item_', '') for i in items]}")
    print()

    result = optimizer.optimize_distribution(comp, items)

    print(f"Distribution Score: {result.score:.2f}")
    print()

    for champ, assigned_items in result.assignments.items():
        champ_short = champ.replace('TFT16_', '')
        items_short = [i.replace('TFT_Item_', '') for i in assigned_items]

        print(f"{champ_short}:")
        if items_short:
            for item, rec in zip(items_short, result.details[champ]):
                print(f"  - {item}: {rec.reason}")
        else:
            print("  (no items)")


def main():
    parser = argparse.ArgumentParser(
        description='TFT Item Optimizer CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python item_search.py best Seraphine
    python item_search.py build Shyvana
    python item_search.py craft bf rod tear vest
    python item_search.py slam bf rod tear --stage 3-2 --hp 65
    python item_search.py distribute --comp Seraphine,Braum,Lissandra
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command')

    # best
    p_best = subparsers.add_parser('best', help='Get best items for a unit')
    p_best.add_argument('unit', help='Unit name (e.g., Seraphine, TFT16_Seraphine)')
    p_best.add_argument('-n', '--count', type=int, default=5, help='Number of items')
    p_best.add_argument('--special', action='store_true',
                        help='Include radiants/artifacts/emblems')

    # build
    p_build = subparsers.add_parser('build', help='Get best 3-item build')
    p_build.add_argument('unit', help='Unit name')

    # craft
    p_craft = subparsers.add_parser('craft', help='Recommend crafts from components')
    p_craft.add_argument('components', nargs='+',
                         help='Components (e.g., bf rod tear vest bow)')
    p_craft.add_argument('-n', '--count', type=int, default=5, help='Number of crafts')
    p_craft.add_argument('--comp', help='Comma-separated comp (e.g., Seraphine,Braum)')

    # slam
    p_slam = subparsers.add_parser('slam', help='Slam vs hold analysis')
    p_slam.add_argument('components', nargs='+', help='Components')
    p_slam.add_argument('--stage', default='3-2', help='Current stage (e.g., 3-2)')
    p_slam.add_argument('--hp', type=int, default=80, help='Current HP')
    p_slam.add_argument('--comp', help='Comma-separated comp')

    # distribute
    p_dist = subparsers.add_parser('distribute', help='Distribute items across comp')
    p_dist.add_argument('--comp', help='Comma-separated comp')
    p_dist.add_argument('--items', help='Comma-separated items')

    args = parser.parse_args()

    if args.command == 'best':
        cmd_best(args)
    elif args.command == 'build':
        cmd_build(args)
    elif args.command == 'craft':
        cmd_craft(args)
    elif args.command == 'slam':
        cmd_slam(args)
    elif args.command == 'distribute':
        cmd_distribute(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
