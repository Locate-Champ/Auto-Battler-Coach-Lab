#!/usr/bin/env python3
"""
TFT Position Search CLI

Command-line interface for running positioning optimization searches.

Usage:
    python position_search.py --help

Examples:
    # Basic search with default comp
    python position_search.py

    # Custom comp (JSON format)
    python position_search.py --comp '[{"champion":"TFT16_Draven","star":2},{"champion":"TFT16_Leona","star":2}]'

    # More thorough search
    python position_search.py --configs 1000 --sims 20

    # Exhaustive search (small teams only)
    python position_search.py --strategy exhaustive

    # Save results to file
    python position_search.py --output results.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.positioning_optimizer import PositioningOptimizer


# Pre-defined team compositions for quick testing
PRESET_COMPS = {
    'demo': [
        {'champion': 'TFT16_Leona', 'star': 2, 'items': []},
        {'champion': 'TFT16_Draven', 'star': 2, 'items': []},
        {'champion': 'TFT16_Lux', 'star': 2, 'items': []},
    ],
    'small_frontline': [
        {'champion': 'TFT16_Leona', 'star': 2, 'items': []},
        {'champion': 'TFT16_Yasuo', 'star': 2, 'items': []},
    ],
    'standard_4': [
        {'champion': 'TFT16_Leona', 'star': 2, 'items': []},
        {'champion': 'TFT16_Draven', 'star': 2, 'items': []},
        {'champion': 'TFT16_Lux', 'star': 2, 'items': []},
        {'champion': 'TFT16_Yasuo', 'star': 2, 'items': []},
    ],
    # Real meta comp: Piltover/Seraphine (level 8, ~920k games played)
    'piltover_seraphine': [
        {'champion': 'TFT16_Azir', 'star': 2, 'items': []},
        {'champion': 'TFT16_Braum', 'star': 2, 'items': []},
        {'champion': 'TFT16_Lissandra', 'star': 2, 'items': []},
        {'champion': 'TFT16_Loris', 'star': 2, 'items': []},
        {'champion': 'TFT16_Orianna', 'star': 2, 'items': []},
        {'champion': 'TFT16_Sejuani', 'star': 2, 'items': []},
        {'champion': 'TFT16_Seraphine', 'star': 2, 'items': []},
        {'champion': 'TFT16_Vi', 'star': 2, 'items': []},
    ],
    # Real meta comp: Diana/Targon (level 8)
    'diana_targon': [
        {'champion': 'TFT16_AurelionSol', 'star': 2, 'items': []},
        {'champion': 'TFT16_Diana', 'star': 2, 'items': []},
        {'champion': 'TFT16_Neeko', 'star': 2, 'items': []},
        {'champion': 'TFT16_Seraphine', 'star': 2, 'items': []},
        {'champion': 'TFT16_Shyvana', 'star': 2, 'items': []},
        {'champion': 'TFT16_Swain', 'star': 2, 'items': []},
        {'champion': 'TFT16_Taric', 'star': 2, 'items': []},
        {'champion': 'TFT16_Vi', 'star': 2, 'items': []},
    ],
}


def parse_comp(comp_str: str) -> list:
    """Parse comp from JSON string or preset name."""
    if comp_str in PRESET_COMPS:
        return PRESET_COMPS[comp_str]

    try:
        return json.loads(comp_str)
    except json.JSONDecodeError as e:
        print(f"Error parsing comp JSON: {e}")
        print("Use --presets to see available preset comps")
        sys.exit(1)


def print_results_table(results: list, limit: int = 10):
    """Print results in a nice table format."""
    print(f"\nTop {min(limit, len(results))} Configurations:")
    print("-" * 70)
    print(f"{'Rank':<6} {'Win Rate':<12} {'Avg Damage':<12} {'Survivors':<12} Positions")
    print("-" * 70)

    for i, res in enumerate(results[:limit]):
        positions_str = ', '.join(f'({p[0]},{p[1]})' for p in res.config.positions)
        print(f"{i+1:<6} {res.win_rate:>10.1%}  {res.avg_damage_dealt:>10.0f}  {res.avg_survivors:>10.2f}  {positions_str}")


def main():
    parser = argparse.ArgumentParser(
        description="TFT Position Search - Find optimal board positions for your comp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python position_search.py --preset demo
    python position_search.py --comp '[{"champion":"TFT16_Draven","star":2}]'
    python position_search.py --configs 1000 --sims 20 --seed 42
    python position_search.py --strategy exhaustive --preset small_frontline

Positioning Strategies (used with 'strategic'):
    - standard:   Tanks front (rows 0-1), carries back (rows 2-3)
    - solo_tank:  1 tank in front, everyone else in back 2 rows
    - spread:     No units adjacent (anti-AOE, zone defense)
    - corner:     All units clumped in one corner
    - diagonal:   Units on diagonal lines
    - bait:       Weak unit in front corner, carry in opposite back corner
        """
    )

    # Comp specification
    comp_group = parser.add_mutually_exclusive_group()
    comp_group.add_argument('--comp', type=str, help='Team composition as JSON array')
    comp_group.add_argument('--preset', type=str, choices=list(PRESET_COMPS.keys()),
                           default='demo', help='Use a preset composition')

    # Search parameters
    parser.add_argument('--strategy', type=str, choices=['exhaustive', 'sampled', 'strategic'],
                       default='strategic', help='Position generation strategy')
    parser.add_argument('--configs', type=int, default=500,
                       help='Number of configurations to evaluate (for sampled/strategic)')
    parser.add_argument('--sims', type=int, default=10,
                       help='Simulations per opponent board')
    parser.add_argument('--seed', type=int, default=None,
                       help='Random seed for reproducibility')

    # Output options
    parser.add_argument('--output', '-o', type=str, help='Save results to JSON file')
    parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')
    parser.add_argument('--top', type=int, default=10, help='Number of top results to show')

    # Info commands
    parser.add_argument('--presets', action='store_true', help='List available preset comps')
    parser.add_argument('--champions', action='store_true', help='List available champions')
    parser.add_argument('--strategies', action='store_true', help='List positioning strategies')

    args = parser.parse_args()

    # Handle info commands
    if args.presets:
        print("Available preset compositions:")
        print("-" * 40)
        for name, comp in PRESET_COMPS.items():
            units = ', '.join(f"{u['champion'].replace('TFT16_', '')}({u['star']}*)" for u in comp)
            print(f"  {name}: {units}")
        return

    if args.champions:
        from core.combat_engine import CombatEngine
        engine = CombatEngine()
        print(f"Available champions ({len(engine.champions)}):")
        print("-" * 40)
        for name in sorted(engine.champions.keys()):
            print(f"  {name}")
        return

    if args.strategies:
        print("Positioning Strategies (used with --strategy strategic):")
        print("-" * 60)
        print()
        print("The 'strategic' strategy mixes 10 positioning approaches:")
        print()
        print("  STANDARD (25%)")
        print("    Tanks in front rows (0-1), carries in back rows (2-3)")
        print("    Classic TFT positioning that protects backline carries")
        print()
        print("  SOLO TANK (10%)")
        print("    One itemized tank alone in front row, everyone else back")
        print("    Forces enemy to focus tank while carries deal damage safely")
        print()
        print("  SPREAD (10%)")
        print("    No units adjacent to each other (zone defense)")
        print("    Counters AOE abilities like Lux ult, Sejuani stun, etc.")
        print()
        print("  CORNER STACK (8%)")
        print("    All units clumped in one corner")
        print("    Assassins jump to opposite corner, leaving your corner safe")
        print()
        print("  DIAGONAL (7%)")
        print("    Units arranged on diagonal lines")
        print("    Controls enemy pathing and spreads incoming damage")
        print()
        print("  BAIT (8%)")
        print("    Weak/sacrificial unit in front corner to pull aggro")
        print("    Main carry protected in opposite back corner")
        print()
        print("  ANTI-ZEPHYR (8%)")
        print("    Carry in unpredictable position, tank in Zephyr-bait spot")
        print("    Counters enemy Zephyr targeting your carry")
        print()
        print("  CLUMP FOR BUFFS (8%)")
        print("    Group carries together for item auras (Locket, Zeke's, Chalice)")
        print("    Good for Protector trait, healing auras, etc.")
        print()
        print("  V-SHAPE FRONTLINE (8%)")
        print("    Tanks form V shape to funnel enemies into kill zone")
        print("    Groups enemies for your AOE abilities")
        print()
        print("  SPLIT CARRY (8%)")
        print("    Two carries on opposite sides of board")
        print("    Counters assassins and single-target burst")
        print()
        return

    # Parse comp
    if args.comp:
        comp = parse_comp(args.comp)
    else:
        comp = PRESET_COMPS[args.preset]

    # Print header
    if not args.quiet:
        print("=" * 60)
        print("TFT Position Search")
        print("=" * 60)
        print()
        print("Composition:")
        for unit in comp:
            items_str = f" [{', '.join(unit.get('items', []))}]" if unit.get('items') else ""
            print(f"  - {unit['champion']} ({unit.get('star', 1)}*){items_str}")
        print()

    # Run optimization
    start_time = time.perf_counter()

    optimizer = PositioningOptimizer()
    result = optimizer.optimize(
        comp,
        strategy=args.strategy,
        num_configs=args.configs,
        sims_per_opponent=args.sims,
        seed=args.seed,
        verbose=not args.quiet
    )

    elapsed = time.perf_counter() - start_time

    # Print results
    if not args.quiet:
        print()
        print(optimizer.visualize_board(result['best_positions'], "Optimal Positions"))
        print_results_table(result['all_results'], args.top)

        print()
        print(f"Search completed in {elapsed:.2f}s")
        print(f"Configurations evaluated: {result['statistics']['configs_evaluated']}")
        print(f"Total simulations: {result['statistics']['total_simulations']}")
    else:
        # Minimal output
        print(f"Best win rate: {result['best_result']['win_rate']:.1%}")
        print(f"Positions: {result['best_result']['positions']}")

    # Save to file if requested
    if args.output:
        output_data = {
            'comp': comp,
            'parameters': {
                'strategy': args.strategy,
                'configs': args.configs,
                'sims_per_opponent': args.sims,
                'seed': args.seed,
            },
            'best_result': {
                'win_rate': result['best_result']['win_rate'],
                'avg_damage': result['best_result']['avg_damage'],
                'avg_survivors': result['best_result']['avg_survivors'],
                'positions': result['best_result']['positions'],
                'positions_by_champion': result['best_positions']
            },
            'statistics': result['statistics'],
            'elapsed_seconds': elapsed,
            'top_results': [
                {
                    'win_rate': r.win_rate,
                    'avg_damage': r.avg_damage_dealt,
                    'avg_survivors': r.avg_survivors,
                    'positions': r.config.positions
                }
                for r in result['all_results'][:100]
            ]
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
