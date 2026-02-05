#!/usr/bin/env python3
"""
Fetch TFT Set 16 champion data from the League of Legends Wiki.

Parses the Lua module at:
  https://wiki.leagueoflegends.com/en-us/Module:TFTUnitData/data

Extracts champion stats (hp, ad, armor, mr, mana, spell info, etc.)
and writes them to tft_set16_champions.json in the project root.
"""

import json
import re
import sys
import urllib.request

WIKI_API_URL = (
    "https://wiki.leagueoflegends.com/en-us/api.php"
    "?action=parse&page=Module:TFTUnitData/data&prop=wikitext&format=json"
)

TARGET_SET = 16
OUTPUT_FILE = "tft_set16_champions.json"


def fetch_lua_source() -> str:
    """Download the raw Lua module source from the wiki API."""
    req = urllib.request.Request(WIKI_API_URL, headers={"User-Agent": "TFTCoach/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data["parse"]["wikitext"]["*"]


def find_matching_brace(text: str, start: int) -> int:
    """Find the index of the closing brace matching the opening brace at `start`."""
    depth = 0
    i = start
    in_string = False
    escape_next = False
    while i < len(text):
        ch = text[i]
        if escape_next:
            escape_next = False
            i += 1
            continue
        if ch == "\\":
            escape_next = True
            i += 1
            continue
        if ch == '"' and not in_string:
            in_string = True
        elif ch == '"' and in_string:
            in_string = False
        elif not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def parse_lua_value(raw: str) -> object:
    """Parse a single Lua value (string, number, bool, or array of strings)."""
    raw = raw.strip().rstrip(",")
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_lua_table_values(block: str) -> list[str]:
    """Parse a Lua array table like {"Demon", "Blademaster"} into a Python list."""
    items = []
    for m in re.finditer(r'"([^"]*)"', block):
        items.append(m.group(1))
    return items


def parse_set_block(block: str) -> dict:
    """Parse the key-value pairs inside a single set entry block."""
    entry = {}
    # Match simple key = value pairs
    for m in re.finditer(
        r'\["(\w+)"\]\s*=\s*(\{[^}]*\}|"(?:[^"\\]|\\.)*"|[^,\n}]+)', block
    ):
        key = m.group(1)
        raw_val = m.group(2).strip().rstrip(",")
        if raw_val.startswith("{"):
            entry[key] = parse_lua_table_values(raw_val)
        else:
            entry[key] = parse_lua_value(raw_val)
    return entry


def clean_wiki_markup(text: str) -> str:
    """Strip wiki template markup from ability descriptions.

    Handles patterns like:
      {{ap|100|200|300}}  ->  100/200/300
      {{as|magic damage}} ->  magic damage
      {{tiptft|AD|AD}}    ->  AD
      {{tip|Execute|executed}} -> executed
      {{sbc|text}}        ->  text
    """
    if not isinstance(text, str):
        return text

    def replace_template(match):
        inner = match.group(1)
        parts = inner.split("|")
        template_name = parts[0].strip().lower()
        if template_name == "ap":
            # Scaling values: {{ap|100|200|300}} -> 100/200/300
            return "/".join(parts[1:])
        elif template_name in ("as", "sbc"):
            # Styled text: {{as|magic damage}} -> magic damage
            return parts[-1] if len(parts) > 1 else ""
        elif template_name in ("tip", "tiptft"):
            # Tooltip: {{tiptft|AD|AD}} -> last part
            return parts[-1] if len(parts) > 1 else ""
        else:
            return parts[-1] if len(parts) > 1 else ""

    # Repeatedly resolve nested templates from inside out
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{([^{}]+)\}\}", replace_template, text)

    # Clean up any remaining artifacts
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"'''(.+?)'''", r"\1", text)  # bold
    text = re.sub(r"''(.+?)''", r"\1", text)  # italic
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_set_champions(lua_src: str, target_set: int) -> dict:
    """Extract all champion entries for the given set number."""
    champions = {}

    # Find all champion name keys: ["ChampionName"] = {
    champ_pattern = re.compile(r'\n\s*\["([A-Z][^"]+)"\]\s*=\s*\{')

    for champ_match in champ_pattern.finditer(lua_src):
        champ_name = champ_match.group(1)
        champ_block_start = champ_match.end() - 1  # the opening {
        champ_block_end = find_matching_brace(lua_src, champ_block_start)
        if champ_block_end == -1:
            continue

        champ_block = lua_src[champ_block_start : champ_block_end + 1]

        # Look for [16] = { ... } within this champion block
        set_pattern = re.compile(rf"\[{target_set}\]\s*=\s*\{{")
        set_match = set_pattern.search(champ_block)
        if not set_match:
            continue

        set_block_start = set_match.end() - 1
        set_block_end = find_matching_brace(champ_block, set_block_start)
        if set_block_end == -1:
            continue

        set_block = champ_block[set_block_start : set_block_end + 1]
        entry = parse_set_block(set_block)

        if not entry:
            continue

        # Clean ability descriptions
        for field in ("active", "passive"):
            if field in entry:
                entry[field] = clean_wiki_markup(entry[field])

        entry["name"] = champ_name
        champions[champ_name] = entry

    return champions


def format_output(champions: dict) -> dict:
    """Structure the final output with metadata."""
    # Sort by cost then name
    sorted_champs = sorted(
        champions.values(), key=lambda c: (c.get("tier", 0), c.get("name", ""))
    )

    return {
        "metadata": {
            "source": "https://wiki.leagueoflegends.com/en-us/Module:TFTUnitData/data",
            "set": TARGET_SET,
            "set_name": "TFT Set 16 - Magic n' Mayhem",
            "champion_count": len(sorted_champs),
        },
        "champions": sorted_champs,
    }


def main():
    print(f"Fetching TFT Unit data from wiki...")
    lua_src = fetch_lua_source()
    print(f"  Downloaded {len(lua_src):,} characters of Lua source")

    print(f"Extracting Set {TARGET_SET} champions...")
    champions = extract_set_champions(lua_src, TARGET_SET)
    print(f"  Found {len(champions)} champions")

    if not champions:
        print("ERROR: No champions found. The wiki data structure may have changed.")
        sys.exit(1)

    output = format_output(champions)

    # Resolve output path relative to project root
    import os

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_path = os.path.join(project_root, OUTPUT_FILE)

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {output_path}")

    # Summary
    by_tier = {}
    for c in champions.values():
        t = c.get("tier", "?")
        by_tier.setdefault(t, []).append(c["name"])

    print(f"\nChampions by cost:")
    for tier in sorted(by_tier.keys()):
        names = sorted(by_tier[tier])
        print(f"  {tier}-cost ({len(names)}): {', '.join(names)}")


if __name__ == "__main__":
    main()
