"""Ryze Emblem Encounter Optimizer.

The Ryze encounter offers the player 3 random emblems to choose from.
Emblems can be ANY trait — both region (Bilgewater, Freljord, etc.) and
class (Slayer, Longshot, Invoker, etc.). All 22 emblems are in the pool.

Ryze's ability gains unique effects for each active region trait on his team,
so this module helps evaluate which emblems maximize region coverage while
also considering class trait synergies for the broader team.

Region traits Ryze benefits from (12 total):
  Targon, Yordle, Bilgewater, Void, Shadow Isles, Piltover,
  Demacia, Freljord, Zaun, Shurima, Noxus, Ionia

Each active region gives Ryze a different bonus on cast:
  - Targon: 10% HP heal
  - Yordle: 12% damage reduction
  - Bilgewater: 25% explosion damage
  - Void: 30% resist ignore
  - Shadow Isles: 5% + soul scaling bonus
  - Piltover: 40% overcharge damage
  - Demacia: 12% execute threshold
  - Freljord: Chill + 6% max HP true damage
  - Zaun: Poison ticks
  - Shurima: Knockup + gold chance
  - Noxus: DR to nearby allies
  - Ionia: Reduced damage taken
"""

import random
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field

# Region traits that give Ryze bonus effects
# Maps display name (used in combat) -> minimum count needed
RYZE_REGION_TRAITS = {
    'Targon': 2,
    'Yordle': 3,
    'Bilgewater': 3,
    'Void': 2,
    'Shadow Isles': 2,
    'Piltover': 2,
    'Demacia': 2,
    'Freljord': 2,
    'Zaun': 2,
    'Shurima': 2,
    'Noxus': 3,
    'Ionia': 3,
}

# Map display trait names to internal (origin_class_stats) names
_DISPLAY_TO_INTERNAL = {
    'Targon': 'targon',
    'Yordle': 'yordle',
    'Bilgewater': 'bilgewater',
    'Void': 'void',
    'Shadow Isles': 'shadow_isles',
    'Piltover': 'piltover',
    'Demacia': 'demacia',
    'Freljord': 'freljord',
    'Zaun': 'zaun',
    'Shurima': 'shurima',
    'Noxus': 'noxus',
    'Ionia': 'ionia',
    'Ixtal': 'ixtal',
}

_INTERNAL_TO_DISPLAY = {v: k for k, v in _DISPLAY_TO_INTERNAL.items()}

# All 22 emblems in the game (class + region).
# The Ryze encounter can offer ANY of these, not just region emblems.
# Imported from the canonical source in set16_items.py.
try:
    from simulator.data.set16_items import EMBLEM_TO_TRAIT
    ALL_EMBLEMS = dict(EMBLEM_TO_TRAIT)
except ImportError:
    ALL_EMBLEMS = {}

# Champion data: name -> (cost, [internal trait names])
# Loaded from origin_class_stats
try:
    from simulator.game.stats.origin_class_stats import origin_class
    from simulator.game.stats.pool_stats import COST_1, COST_2, COST_3, COST_4, COST_5, COST_7

    _ALL_COSTS = {}
    for cost, pool in [(1, COST_1), (2, COST_2), (3, COST_3), (4, COST_4), (5, COST_5), (7, COST_7)]:
        for name in pool:
            _ALL_COSTS[name] = cost

    CHAMPION_DATA = {}
    for name, traits in origin_class.items():
        if name in _ALL_COSTS:
            CHAMPION_DATA[name] = (_ALL_COSTS[name], traits)
except ImportError:
    CHAMPION_DATA = {}


@dataclass
class EmblemAnalysis:
    """Result of analyzing a single emblem's value."""
    emblem_name: str
    trait_granted: str
    is_region: bool           # True if this emblem grants a region trait
    new_regions_activated: int
    regions_reinforced: int   # Existing regions that get +1 count
    total_active_regions: int
    class_synergy: bool       # True if trait already active on board
    best_target_unit: Optional[str] = None
    score: float = 0.0


@dataclass
class CompRecommendation:
    """A recommended team composition for Ryze."""
    units: List[str]
    active_regions: List[str]
    region_count: int
    total_cost: int
    emblem_slots: List[str]  # Suggested emblems to add


def get_champion_regions(name: str) -> Set[str]:
    """Get the region traits (display names) for a champion."""
    if name not in CHAMPION_DATA:
        return set()

    _, traits = CHAMPION_DATA[name]
    regions = set()
    for t in traits:
        display = _INTERNAL_TO_DISPLAY.get(t)
        if display and display in RYZE_REGION_TRAITS:
            regions.add(display)
    return regions


def get_champion_traits(name: str) -> Set[str]:
    """Get ALL traits (display names) for a champion."""
    if name not in CHAMPION_DATA:
        return set()

    _, traits = CHAMPION_DATA[name]
    result = set()
    for t in traits:
        display = _INTERNAL_TO_DISPLAY.get(t)
        if display:
            result.add(display)
        else:
            # Class traits: capitalize internal name
            result.add(t.replace('_', ' ').title())
    return result


def count_active_regions(units: List[str], emblems: List[str] = None) -> Dict[str, int]:
    """Count region trait contributions from a list of units + emblems.

    Args:
        units: List of champion names (lowercase)
        emblems: List of emblem names (e.g., 'FreljordEmblem')

    Returns:
        Dict mapping display region name -> count of units contributing
    """
    region_counts: Dict[str, int] = {}

    for name in units:
        for region in get_champion_regions(name):
            region_counts[region] = region_counts.get(region, 0) + 1

    # Emblems add +1 to their trait (whoever wears it)
    if emblems:
        for emblem in emblems:
            trait = ALL_EMBLEMS.get(emblem)
            if trait and trait in RYZE_REGION_TRAITS:
                region_counts[trait] = region_counts.get(trait, 0) + 1

    return region_counts


def get_activated_regions(region_counts: Dict[str, int]) -> List[str]:
    """Return list of regions that meet their activation threshold."""
    activated = []
    for region, min_count in RYZE_REGION_TRAITS.items():
        if region_counts.get(region, 0) >= min_count:
            activated.append(region)
    return activated


def roll_encounter_emblems(count: int = 3) -> List[str]:
    """Simulate the Ryze encounter: randomly offer N emblems from all 22.

    Returns:
        List of emblem names (e.g., ['FreljordEmblem', 'SlayerEmblem', 'VoidEmblem'])
    """
    all_emblem_names = list(ALL_EMBLEMS.keys())
    if len(all_emblem_names) <= count:
        return all_emblem_names[:]
    return random.sample(all_emblem_names, count)


def analyze_emblem(units: List[str], emblem_name: str,
                   existing_emblems: List[str] = None) -> EmblemAnalysis:
    """Analyze the value of a specific emblem for a Ryze comp.

    Evaluates both region activation (for Ryze's ability) and class
    synergy (for the broader team).

    Args:
        units: Current team (lowercase names, should include 'ryze')
        emblem_name: The emblem to evaluate
        existing_emblems: Emblems already equipped

    Returns:
        EmblemAnalysis with scoring
    """
    existing = existing_emblems or []
    trait_granted = ALL_EMBLEMS.get(emblem_name, '?')
    is_region = trait_granted in RYZE_REGION_TRAITS

    # Current state
    current_counts = count_active_regions(units, existing)
    current_activated = set(get_activated_regions(current_counts))

    # State with new emblem
    new_counts = count_active_regions(units, existing + [emblem_name])
    new_activated = set(get_activated_regions(new_counts))

    new_regions = new_activated - current_activated
    reinforced = 0
    for region in current_activated:
        if new_counts.get(region, 0) > current_counts.get(region, 0):
            reinforced += 1

    # Check if the granted trait has class synergy with existing board
    # (e.g., Slayer emblem when you already have Slayer units)
    class_synergy = False
    if not is_region:
        # Check if any unit on the board already has this trait
        trait_lower = trait_granted.lower().replace(' ', '_')
        for name in units:
            if name in CHAMPION_DATA:
                _, unit_traits = CHAMPION_DATA[name]
                if trait_lower in unit_traits:
                    class_synergy = True
                    break

    # Score: region activations are most valuable for Ryze
    # Class synergy has secondary value for overall team strength
    progress_score = 0.0
    if is_region:
        needed = RYZE_REGION_TRAITS[trait_granted]
        current = current_counts.get(trait_granted, 0)
        new = new_counts.get(trait_granted, 0)
        if trait_granted not in current_activated:
            progress_score = new / needed * 5.0

    score = len(new_regions) * 10.0 + reinforced * 1.0 + progress_score
    if class_synergy:
        score += 3.0  # Class synergy bonus for team strength

    # Find best unit to equip the emblem on
    best_target = None
    for unit in units:
        if unit == 'ryze':
            continue
        if is_region:
            unit_regions = get_champion_regions(unit)
            if trait_granted not in unit_regions:
                if best_target is None:
                    best_target = unit
        else:
            # For class emblems, prefer units without this class trait
            if unit in CHAMPION_DATA:
                _, unit_traits = CHAMPION_DATA[unit]
                trait_lower = trait_granted.lower().replace(' ', '_')
                if trait_lower not in unit_traits:
                    if best_target is None:
                        best_target = unit

    return EmblemAnalysis(
        emblem_name=emblem_name,
        trait_granted=trait_granted,
        is_region=is_region,
        new_regions_activated=len(new_regions),
        regions_reinforced=reinforced,
        total_active_regions=len(new_activated),
        class_synergy=class_synergy,
        best_target_unit=best_target,
        score=score,
    )


def rank_offered_emblems(units: List[str], offered: List[str],
                         existing_emblems: List[str] = None) -> List[EmblemAnalysis]:
    """Rank a set of offered emblems by value for the current comp.

    This is the main entry point for the Ryze encounter: given the 3
    randomly offered emblems, rank them by value.

    Args:
        units: Current team (lowercase names)
        offered: List of offered emblem names (typically 3)
        existing_emblems: Already equipped emblems

    Returns:
        List of EmblemAnalysis sorted by score (best first)
    """
    results = []
    for emblem_name in offered:
        analysis = analyze_emblem(units, emblem_name, existing_emblems)
        results.append(analysis)

    results.sort(key=lambda x: (-x.score, -x.total_active_regions))
    return results


def rank_all_emblems(units: List[str],
                     existing_emblems: List[str] = None) -> List[EmblemAnalysis]:
    """Rank ALL 22 emblems by value for the current comp.

    Useful for general planning (not just a specific encounter offer).

    Args:
        units: Current team (lowercase names)
        existing_emblems: Already equipped emblems

    Returns:
        List of EmblemAnalysis sorted by score (best first)
    """
    results = []
    for emblem_name in ALL_EMBLEMS:
        analysis = analyze_emblem(units, emblem_name, existing_emblems)
        results.append(analysis)

    results.sort(key=lambda x: (-x.score, -x.total_active_regions))
    return results


def find_best_ryze_comp(max_team_size: int = 9,
                        max_cost: int = 50,
                        required_units: List[str] = None,
                        available_emblems: List[str] = None) -> List[CompRecommendation]:
    """Find optimal unit combinations for Ryze that maximize region coverage.

    Uses greedy search to maximize the number of active region traits.

    Args:
        max_team_size: Maximum units on board (typically 9 at level 9)
        max_cost: Maximum total gold cost
        required_units: Units that must be in the comp (e.g., ['ryze'])
        available_emblems: Emblems available to use

    Returns:
        Top 5 comp recommendations sorted by region count
    """
    required = set(required_units or ['ryze'])
    emblems = available_emblems or []

    # Start with required units
    comp = list(required)
    used_cost = sum(CHAMPION_DATA.get(u, (0, []))[0] for u in comp)
    remaining_slots = max_team_size - len(comp)

    # Get all candidate champions (not already in comp, not 7-cost unless required)
    candidates = []
    for name, (cost, traits) in CHAMPION_DATA.items():
        if name in required:
            continue
        if cost == 7 and name not in required:
            continue  # 7-costs are expensive, skip for general planning
        regions = get_champion_regions(name)
        if regions:  # Only consider units that contribute region traits
            candidates.append((name, cost, regions))

    # Greedy: repeatedly add the unit that activates the most new regions
    results = []
    _greedy_search(comp, used_cost, remaining_slots, max_cost,
                   candidates, emblems, results, depth=0)

    # Sort by region count
    results.sort(key=lambda r: (-r.region_count, r.total_cost))
    return results[:5]


def _greedy_search(comp: List[str], used_cost: int, remaining_slots: int,
                   max_cost: int, candidates: List, emblems: List[str],
                   results: List[CompRecommendation], depth: int):
    """Greedy search for best comp (explores top-3 choices at each step)."""
    if remaining_slots <= 0 or depth > 12:
        # Evaluate this comp
        region_counts = count_active_regions(comp, emblems)
        activated = get_activated_regions(region_counts)
        results.append(CompRecommendation(
            units=list(comp),
            active_regions=activated,
            region_count=len(activated),
            total_cost=used_cost,
            emblem_slots=list(emblems),
        ))
        return

    # Score each candidate by marginal region value
    current_counts = count_active_regions(comp, emblems)
    current_activated = set(get_activated_regions(current_counts))

    scored = []
    for name, cost, regions in candidates:
        if name in comp:
            continue
        if used_cost + cost > max_cost:
            continue

        # How many new regions would this unit help activate?
        test_counts = count_active_regions(comp + [name], emblems)
        test_activated = set(get_activated_regions(test_counts))
        new_regions = len(test_activated - current_activated)

        # Also count partial progress toward new thresholds
        partial = 0
        for region in regions:
            if region not in current_activated:
                current = current_counts.get(region, 0)
                needed = RYZE_REGION_TRAITS.get(region, 999)
                if current + 1 < needed:
                    partial += (current + 1) / needed  # Progress fraction

        score = new_regions * 10 + partial * 3 + len(regions) * 0.5
        scored.append((score, name, cost, regions))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        # No more candidates fit - evaluate current comp
        _greedy_search(comp, used_cost, 0, max_cost, candidates, emblems, results, depth)
        return

    # Explore top-3 choices to get variety
    for score, name, cost, regions in scored[:3]:
        comp.append(name)
        _greedy_search(comp, used_cost + cost, remaining_slots - 1,
                       max_cost, candidates, emblems, results, depth + 1)
        comp.pop()


def print_emblem_report(units: List[str], existing_emblems: List[str] = None):
    """Print a human-readable report of emblem values for a Ryze comp."""
    existing = existing_emblems or []

    # Current state
    region_counts = count_active_regions(units, existing)
    activated = get_activated_regions(region_counts)

    print("=" * 60)
    print("RYZE EMBLEM ENCOUNTER OPTIMIZER")
    print("=" * 60)
    print(f"\nTeam: {', '.join(units)}")
    if existing:
        print(f"Equipped emblems: {', '.join(existing)}")
    print(f"\nRegion trait counts:")
    for region, count in sorted(region_counts.items()):
        threshold = RYZE_REGION_TRAITS.get(region, '?')
        status = "ACTIVE" if region in activated else f"need {threshold}"
        print(f"  {region}: {count} ({status})")

    print(f"\nActive regions for Ryze: {len(activated)}/12")
    for r in activated:
        print(f"  + {r}")

    print(f"\n{'=' * 60}")
    print("ALL EMBLEM RANKINGS (best to worst):")
    print(f"{'=' * 60}")

    rankings = rank_all_emblems(units, existing)
    for i, analysis in enumerate(rankings):
        region_tag = "REGION" if analysis.is_region else "CLASS "
        new_str = f"+{analysis.new_regions_activated} NEW" if analysis.new_regions_activated > 0 else ""
        reinforce_str = f"+{analysis.regions_reinforced} reinforced" if analysis.regions_reinforced > 0 else ""
        synergy_str = "class synergy" if analysis.class_synergy else ""
        details = ", ".join(filter(None, [new_str, reinforce_str, synergy_str]))
        print(f"  {i+1:2d}. [{region_tag}] {analysis.emblem_name:25s} -> {analysis.trait_granted:15s} "
              f"[{analysis.total_active_regions} regions] {details}")
        if analysis.best_target_unit:
            print(f"      Best on: {analysis.best_target_unit}")


def print_encounter_simulation(units: List[str], existing_emblems: List[str] = None):
    """Simulate a Ryze encounter and show the analysis."""
    offered = roll_encounter_emblems(3)

    print("=" * 60)
    print("RYZE ENCOUNTER: 3 Random Emblems Offered")
    print("=" * 60)
    print(f"\nTeam: {', '.join(units)}")
    print(f"Offered: {', '.join(offered)}")

    rankings = rank_offered_emblems(units, offered, existing_emblems)
    print(f"\nRecommended pick order:")
    for i, analysis in enumerate(rankings):
        region_tag = "REGION" if analysis.is_region else "CLASS "
        print(f"  {i+1}. [{region_tag}] {analysis.emblem_name} -> {analysis.trait_granted} "
              f"(score: {analysis.score:.1f})")
        if analysis.best_target_unit:
            print(f"     Best on: {analysis.best_target_unit}")


def print_comp_recommendations(max_team_size: int = 9,
                                available_emblems: List[str] = None):
    """Print recommended Ryze comps."""
    emblems = available_emblems or []

    print("=" * 60)
    print(f"BEST RYZE COMPS (max {max_team_size} units)")
    if emblems:
        print(f"With emblems: {', '.join(emblems)}")
    print("=" * 60)

    recs = find_best_ryze_comp(max_team_size=max_team_size,
                                available_emblems=emblems)

    for i, rec in enumerate(recs):
        print(f"\n--- Comp #{i+1} ({rec.region_count} regions, {rec.total_cost}g) ---")
        print(f"  Units: {', '.join(rec.units)}")
        print(f"  Active: {', '.join(rec.active_regions)}")


# -- CLI --

if __name__ == '__main__':
    import sys

    # Example: analyze a typical Ryze comp
    example_comp = [
        'ryze',          # Rune Mage (no region)
        'braum',         # Freljord, Warden
        'lissandra',     # Freljord, Invoker
        'diana',         # Targon
        'leona',         # Targon
        'aphelios',      # Targon
        'illaoi',        # Bilgewater, Bruiser
        'gangplank',     # Bilgewater, Slayer, Vanquisher
        'graves',        # Bilgewater, Gunslinger
    ]

    print_emblem_report(example_comp)

    print("\n")
    print_encounter_simulation(example_comp)

    print("\n")
    print_comp_recommendations(max_team_size=9)

    if len(sys.argv) > 1 and sys.argv[1] == '--with-emblems':
        emblems = sys.argv[2:]
        print("\n")
        print_emblem_report(example_comp, emblems)
