#!/usr/bin/env python3
"""
Validate champion data from CommunityDragon against our implementations.

Checks for:
1. Missing or empty ability data
2. Suspicious stat values
3. Champions without implemented ability handlers
4. Ability variable mismatches

Usage:
    python scripts/validate_champion_data.py
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
SIMULATOR_DIR = PROJECT_ROOT / "simulator"
COMBAT_DATA_PATH = SIMULATOR_DIR / "data" / "combat_data.json"
ABILITIES_PATH = SIMULATOR_DIR / "core" / "champion_abilities.py"


def load_combat_data() -> Dict:
    """Load the combat_data.json file."""
    with open(COMBAT_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_implemented_handlers() -> Set[str]:
    """Find all _cast_<champion> methods in champion_abilities.py."""
    if not ABILITIES_PATH.exists():
        print(f"Warning: {ABILITIES_PATH} not found")
        return set()

    with open(ABILITIES_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all def _cast_<name> methods
    pattern = r"def _cast_(\w+)\s*\("
    matches = re.findall(pattern, content)

    # Normalize names (lowercase, no underscores)
    return {m.lower().replace("_", "") for m in matches}


def normalize_champion_name(api_name: str) -> str:
    """Normalize champion API name for comparison."""
    # TFT16_Aatrox -> aatrox
    # TFT16_KogMaw -> kogmaw
    # TFT16_AnnieTibbers -> annietibbers
    name = api_name.replace("TFT16_", "").lower()
    return name


def validate_stats(stats: Dict) -> List[str]:
    """Check for suspicious stat values."""
    issues = []

    # Helper to safely get numeric values
    def get_num(key, default=0):
        val = stats.get(key, default)
        return val if val is not None else default

    # Check for zeros or missing values
    if get_num("hp", 0) <= 0:
        issues.append("HP is 0 or negative")
    if get_num("ad", 0) <= 0:
        issues.append("AD is 0 or negative")
    if get_num("attackSpeed", 0) <= 0:
        issues.append("Attack speed is 0 or negative")

    # Check for unreasonably high values
    if get_num("hp", 0) > 10000:
        issues.append(f"HP suspiciously high: {get_num('hp')}")
    if get_num("ad", 0) > 500:
        issues.append(f"AD suspiciously high: {get_num('ad')}")

    # Check range for typical values
    if get_num("range", 1) > 10:
        issues.append(f"Range suspiciously high: {get_num('range')}")

    return issues


def validate_ability(ability: Dict) -> List[str]:
    """Check for missing or suspicious ability data."""
    issues = []

    name = ability.get("name", "")
    variables = ability.get("variables", {})

    if not name or name == "Unknown":
        issues.append("Missing ability name")

    if not variables:
        issues.append("No ability variables")

    # Check for suspiciously empty variable arrays
    for var_name, values in variables.items():
        if not values or all(v == 0 for v in values):
            issues.append(f"Variable '{var_name}' is empty or all zeros")

    return issues


def main():
    print("=" * 70)
    print("TFT CHAMPION DATA VALIDATION")
    print("=" * 70)

    # Load data
    data = load_combat_data()
    champions = data.get("champions", {})
    implemented = find_implemented_handlers()

    print(f"\nLoaded {len(champions)} champions from combat_data.json")
    print(f"Found {len(implemented)} implemented ability handlers")

    # Track issues
    critical_issues = []  # Missing ability names, zero HP, etc.
    warnings = []  # Empty variables, high values, etc.
    unimplemented = []  # No handler in champion_abilities.py

    # Validate each champion
    for api_name, champ in champions.items():
        if not api_name.startswith("TFT16_"):
            continue

        name = champ.get("name", api_name)
        normalized = normalize_champion_name(api_name)
        cost = champ.get("cost", 0)

        # Check if implemented
        if normalized not in implemented:
            unimplemented.append((api_name, name, cost))

        # Validate stats
        stats = champ.get("stats", {})
        stat_issues = validate_stats(stats)
        for issue in stat_issues:
            if "0 or negative" in issue:
                critical_issues.append(f"{name}: {issue}")
            else:
                warnings.append(f"{name}: {issue}")

        # Validate ability
        ability = champ.get("ability", {})
        ability_issues = validate_ability(ability)
        for issue in ability_issues:
            if "Missing ability name" in issue:
                critical_issues.append(f"{name}: {issue}")
            else:
                warnings.append(f"{name}: {issue}")

    # Print results
    print("\n" + "=" * 70)
    print("CRITICAL ISSUES (need immediate attention)")
    print("=" * 70)
    if critical_issues:
        for issue in sorted(critical_issues):
            print(f"  [!] {issue}")
    else:
        print("  None found!")

    print("\n" + "-" * 70)
    print("WARNINGS (may need review)")
    print("-" * 70)
    if warnings:
        for issue in sorted(warnings)[:30]:  # Limit to first 30
            print(f"  [?] {issue}")
        if len(warnings) > 30:
            print(f"  ... and {len(warnings) - 30} more")
    else:
        print("  None found!")

    print("\n" + "-" * 70)
    print("UNIMPLEMENTED CHAMPIONS (no _cast_ handler)")
    print("-" * 70)

    # Sort by cost (highest first) and then by name
    unimplemented.sort(key=lambda x: (-x[2], x[1]))

    by_cost = {}
    for api, name, cost in unimplemented:
        if cost not in by_cost:
            by_cost[cost] = []
        by_cost[cost].append(name)

    for cost in sorted(by_cost.keys(), reverse=True):
        names = by_cost[cost]
        print(f"\n  {cost}-cost ({len(names)}):")
        for name in sorted(names):
            print(f"    - {name}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(
        f"  Total champions:    {len([c for c in champions if c.startswith('TFT16_')])}"
    )
    print(
        f"  Implemented:        {len([c for c in champions if c.startswith('TFT16_') and normalize_champion_name(c) in implemented])}"
    )
    print(f"  Unimplemented:      {len(unimplemented)}")
    print(f"  Critical issues:    {len(critical_issues)}")
    print(f"  Warnings:           {len(warnings)}")

    # Check specific champions we know have issues
    print("\n" + "-" * 70)
    print("SPOT CHECK: Known complex champions")
    print("-" * 70)

    spot_check = [
        "TFT16_Taric",
        "TFT16_AnnieTibbers",
        "TFT16_LucianSenna",
        "TFT16_Senna",
        "TFT16_Tibbers",
        "TFT16_Annie",
    ]

    for api_name in spot_check:
        if api_name in champions:
            champ = champions[api_name]
            ability = champ.get("ability", {})
            print(f"\n  {champ.get('name', api_name)}:")
            print(f"    Ability: {ability.get('name', 'MISSING')}")
            vars = ability.get("variables", {})
            if vars:
                print(f"    Variables: {', '.join(vars.keys())[:60]}...")
            else:
                print("    Variables: NONE")
        else:
            print(f"\n  {api_name}: NOT FOUND in combat_data.json")


if __name__ == "__main__":
    main()
