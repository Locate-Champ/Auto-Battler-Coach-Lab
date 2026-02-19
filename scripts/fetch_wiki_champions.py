#!/usr/bin/env python3
"""
Fetch TFT Set 16 champion data from Community Dragon (CDragon).

Source:
  https://raw.communitydragon.org/16.3/cdragon/tft/en_us.json

This uses Riot's actual game data (patch-current) rather than the wiki,
so spell values reflect the latest balance changes.

Extracts champion stats (hp, ad, armor, mr, mana, spell info, etc.)
and writes them to tft_set16_champions.json in the project root.
"""

import json
import os
import re
import sys
import urllib.request

CDRAGON_URL = "https://raw.communitydragon.org/16.3/cdragon/tft/en_us.json"

TARGET_SET = 16
OUTPUT_FILE = "tft_set16_champions.json"


def fetch_cdragon_data() -> dict:
    """Download the TFT data JSON from Community Dragon."""
    req = urllib.request.Request(CDRAGON_URL, headers={"User-Agent": "TFTCoach/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def clean_ability_desc(desc: str) -> str:
    """Strip HTML/XML tags and placeholder tokens from ability descriptions.

    Converts CDragon markup like:
      <magicDamage>@ModifiedDamage@&nbsp;(%i:scaleAP%)</magicDamage>
    into readable text with variable references preserved.
    """
    if not desc:
        return ""

    # Replace &nbsp; with space
    desc = desc.replace("&nbsp;", " ")

    # Strip XML-style tags (e.g. <magicDamage>, <scaleLevel>, <spellPassive>)
    desc = re.sub(r"<[^>]+>", "", desc)

    # Clean up HTML entities
    desc = desc.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    # Convert <br> variants to newlines
    desc = re.sub(r"<br\s*/?>", "\n", desc)

    # Collapse whitespace
    desc = re.sub(r"[ \t]+", " ", desc)
    desc = re.sub(r"\n ", "\n", desc)
    desc = desc.strip()

    return desc


def resolve_ability_desc(desc: str, variables: list[dict]) -> str:
    """Replace @Variable@ placeholders with actual star-level values.

    Turns '@ModifiedDamage@ (%i:scaleAP%)' into '130/185/255 (AP)'
    using the variable values at indices 1 (1-star), 2 (2-star), 3 (3-star).
    """
    if not desc:
        return ""

    # Build lookup from variable name -> [1star, 2star, 3star]
    var_lookup = {}
    for v in variables:
        name = v["name"]
        vals = v["value"]
        if vals is None:
            continue
        # Index 0 is unused, 1=1star, 2=2star, 3=3star
        star_vals = vals[1:4] if len(vals) >= 4 else vals[1:]
        var_lookup[name] = star_vals

    def replace_var(match):
        var_name = match.group(1)
        # Handle Modified* or other computed names - try exact match first
        if var_name in var_lookup:
            vals = var_lookup[var_name]
            # Format nicely: integers where possible
            parts = []
            for v in vals:
                if v == int(v):
                    parts.append(str(int(v)))
                else:
                    parts.append(f"{v:.2f}".rstrip("0").rstrip("."))
                    if parts[-1] == "":
                        parts[-1] = "0"
            return "/".join(parts)

        # Try without "Modified" prefix - CDragon often computes these
        stripped = var_name.replace("Modified", "")
        if stripped in var_lookup:
            vals = var_lookup[stripped]
            parts = []
            for v in vals:
                if v == int(v):
                    parts.append(str(int(v)))
                else:
                    parts.append(f"{v:.2f}".rstrip("0").rstrip("."))
                    if parts[-1] == "":
                        parts[-1] = "0"
            return "/".join(parts)

        # Leave unresolved vars as-is
        return f"@{var_name}@"

    # Replace @VarName@ patterns
    desc = re.sub(r"@(\w+)@", replace_var, desc)

    # Clean up scaling indicators like (%i:scaleAP%) -> (AP)
    desc = re.sub(r"%i:scale(\w+)%", r"\1", desc)

    return desc


def parse_spell_variables(variables: list[dict]) -> dict:
    """Extract spell variables into a clean dict with star-level values."""
    result = {}
    for v in variables:
        name = v["name"]
        vals = v["value"]
        if vals is None:
            result[name] = None
            continue
        # Index 0 is unused/base, 1=1star, 2=2star, 3=3star, 4=4star(if exists)
        star_vals = {}
        if len(vals) > 1:
            star_vals["1star"] = _round(vals[1])
        if len(vals) > 2:
            star_vals["2star"] = _round(vals[2])
        if len(vals) > 3:
            star_vals["3star"] = _round(vals[3])
        if len(vals) > 4 and vals[4] != vals[3]:
            star_vals["4star"] = _round(vals[4])
        result[name] = star_vals
    return result


def _round(val, precision=2):
    """Round a float to `precision` decimals, return ints as ints, pass None through."""
    if val is None:
        return None
    if isinstance(val, float):
        rounded = round(val, precision)
        if rounded == int(rounded):
            return int(rounded)
        return rounded
    return val


def is_real_champion(entry: dict) -> bool:
    """Filter out non-champion entries (items, summons, props, etc.)."""
    api_name = entry.get("apiName", "")
    cost = entry.get("cost", 0)
    traits = entry.get("traits", [])

    # Must be a TFT16 unit with traits and reasonable cost
    if not api_name.startswith("TFT16_"):
        return False
    if cost > 6 or cost < 1:
        return False
    if len(traits) == 0:
        return False

    # Filter out known summons/props
    skip_keywords = [
        "Soldier",
        "Voidling",
        "Tibbers",
        "Invention",
        "Atakhan",
        "Prop",
        "Carousel",
        "Dragon",
    ]
    for kw in skip_keywords:
        if kw in api_name:
            return False

    return True


def extract_champions(cdragon_data: dict) -> list[dict]:
    """Extract and format all Set 16 champions from CDragon data."""
    champions = []

    # Find set 16 in setData
    set_data = None
    for s in cdragon_data["setData"]:
        if s["number"] == TARGET_SET:
            set_data = s
            break

    if not set_data:
        print(f"ERROR: Set {TARGET_SET} not found in CDragon data.")
        sys.exit(1)

    for entry in set_data["champions"]:
        if not is_real_champion(entry):
            continue

        stats = entry.get("stats", {})
        ability = entry.get("ability", {})
        variables = ability.get("variables", [])

        # Clean and resolve ability description
        raw_desc = clean_ability_desc(ability.get("desc", ""))
        resolved_desc = resolve_ability_desc(raw_desc, variables)

        champion = {
            "name": entry.get("name", "").strip(),
            "apiName": entry.get("apiName", ""),
            "cost": entry.get("cost", 0),
            "traits": entry.get("traits", []),
            "role": entry.get("role"),
            "stats": {
                "hp": _round(stats.get("hp")),
                "ad": _round(stats.get("damage")),
                "armor": _round(stats.get("armor")),
                "mr": _round(stats.get("magicResist")),
                "attackSpeed": _round(stats.get("attackSpeed")),
                "range": _round(stats.get("range")),
                "mana": _round(stats.get("mana")),
                "initialMana": _round(stats.get("initialMana")),
                "critChance": _round(stats.get("critChance")),
                "critMultiplier": _round(stats.get("critMultiplier")),
            },
            "ability": {
                "name": ability.get("name", ""),
                "desc": resolved_desc,
                "variables": parse_spell_variables(variables),
            },
            "icon": entry.get("icon", ""),
            "squareIcon": entry.get("squareIcon", ""),
            "tileIcon": entry.get("tileIcon", ""),
        }

        champions.append(champion)

    # Sort by cost then name
    champions.sort(key=lambda c: (c["cost"], c["name"]))
    return champions


def extract_traits(cdragon_data: dict) -> list[dict]:
    """Extract all Set 16 traits from CDragon data."""
    traits = []

    set_data = None
    for s in cdragon_data["setData"]:
        if s["number"] == TARGET_SET:
            set_data = s
            break

    if not set_data:
        return traits

    for t in set_data.get("traits", []):
        trait = {
            "name": t.get("name", ""),
            "apiName": t.get("apiName", ""),
            "desc": clean_ability_desc(t.get("desc", "")),
            "icon": t.get("icon", ""),
            "breakpoints": [],
        }
        for effect in t.get("effects", []):
            bp = {
                "minUnits": effect.get("minUnits"),
                "maxUnits": effect.get("maxUnits"),
                "style": effect.get("style"),
                "variables": effect.get("variables", {}),
            }
            trait["breakpoints"].append(bp)

        traits.append(trait)

    traits.sort(key=lambda t: t["name"])
    return traits


def main():
    print("Fetching TFT data from Community Dragon...")
    cdragon_data = fetch_cdragon_data()
    print(f"  Downloaded data ({len(json.dumps(cdragon_data)):,} chars)")

    print(f"Extracting Set {TARGET_SET} champions...")
    champions = extract_champions(cdragon_data)
    print(f"  Found {len(champions)} champions")

    print(f"Extracting Set {TARGET_SET} traits...")
    traits = extract_traits(cdragon_data)
    print(f"  Found {len(traits)} traits")

    if not champions:
        print("ERROR: No champions found. The CDragon data may have changed.")
        sys.exit(1)

    output = {
        "metadata": {
            "source": CDRAGON_URL,
            "set": TARGET_SET,
            "set_name": "TFT Set 16 - Magic n' Mayhem",
            "champion_count": len(champions),
            "trait_count": len(traits),
        },
        "champions": champions,
        "traits": traits,
    }

    # Resolve output path relative to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_path = os.path.join(project_root, OUTPUT_FILE)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {output_path}")

    # Summary
    by_cost = {}
    for c in champions:
        t = c["cost"]
        by_cost.setdefault(t, []).append(c["name"])

    print("\nChampions by cost:")
    for cost in sorted(by_cost.keys()):
        names = sorted(by_cost[cost])
        print(f"  {cost}-cost ({len(names)}): {', '.join(names)}")

    print(f"\nTraits ({len(traits)}):")
    print(f"  {', '.join(t['name'] for t in traits)}")


if __name__ == "__main__":
    main()
