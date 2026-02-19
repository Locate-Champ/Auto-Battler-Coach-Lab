#!/usr/bin/env python3
"""Extract the active TFT augment list shown on MetaTFT's /augments page."""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

import requests

LOOKUP_URL = "https://data.metatft.com/lookups/TFTSet16_latest_en_us.json"
TIERS_URL = "https://api-hc.metatft.com/tft-stat-api/augments_tiers"
OUTPUT_DIR = Path("outputs")
JSON_OUTPUT = OUTPUT_DIR / "metatft_augments_set16.json"
CSV_OUTPUT = OUTPUT_DIR / "metatft_augments_set16.csv"
ROUND_TAGS = {"2-1", "3-2", "4-2"}
RARITY_SUFFIXES = {
    "Silver": ["1", "-I", "-I-A", "-I-B", "_I", "Heart"],
    "Gold": ["2", "-II", "-II-A", "-II-B", "_II", "Crest"],
    "Prismatic": ["3", "-III", "III", "_III", "-III-A", "-III-B", "Crown"],
}
KEYWORD_REPLACEMENTS = {
    "TFT14_AnimaSquad_Bonus_Default": "An Anima Squad Item",
    "Empty Mod - TFT14_Netgod_Champ_Default": "",
    "An Inkshadow Tattoo": "An Exotech Item",
}
TOKEN_REPLACEMENTS = {
    "i:scaleAD": "AD",
    "i:TFTBaseAD": "AD",
    "i:scaleAP": "AP",
    "i:scaleMR": "Magic Resist",
    "i:scaleArmor": "Armor",
    "i:scaleAS": "Attack Speed",
    "i:scaleMana": "Mana",
    "i:scaleHealth": "Health",
    "i:scaleRange": "Range",
    "i:scaleCritMult": "Crit Damage",
    "i:scaleCrit": "Crit Chance",
    "i:scaleDA": "Damage Amp",
    "i:scaleDR": "Durability",
    "i:scaleSV": "Omnivamp",
    "i:goldCoins": "Gold",
    "i:star": "★",
}
DEFAULT_PARAMS = {
    "queue": "1100",
    "patch": "current",
    "days": "3",
    "rank": "CHALLENGER,DIAMOND,EMERALD,GRANDMASTER,MASTER",
    "permit_filter_adjustment": "true",
    "region_hint": "na1",
}


def format_value(value) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return "0"
    if isinstance(value, (int, float)):
        numeric = float(value)
        if abs(numeric - round(numeric)) < 1e-9:
            return str(int(round(numeric)))
        return f"{numeric:.2f}".rstrip("0").rstrip(".")
    return str(value)


def infer_rarity(api_name: str, augment: dict) -> int:
    if api_name == "TFT9_Augment_FreljordTrait":
        return 2

    icon = augment.get("icon", "")
    metatft_name = icon.split("/")[-1].split(".")[0] if icon else ""
    for rarity_name, endings in RARITY_SUFFIXES.items():
        if any(metatft_name.endswith(suffix) for suffix in endings):
            return {"Silver": 1, "Gold": 2, "Prismatic": 3}[rarity_name]

    if api_name.endswith("PlusPlus") or "_III" in api_name or api_name.endswith("3"):
        return 3
    if api_name.endswith("Plus") or "_II" in api_name or api_name.endswith("2"):
        return 2
    return 1


def render_description(augment: dict) -> str:
    desc = augment.get("desc") or augment.get("description") or ""

    for token in set(
        re.findall(r"\(?@TFTUnitProperty\.*\w*:\w*(?:\*100)?@%?\)?", desc)
    ):
        replacement = "Varies"
        if "TRA" in token:
            replacement = ""

        unit_props = augment.get("unitProperties") or {}
        prop_key = re.sub(r"@", "", token)
        prop_key = re.sub(r"TFTUnitProperty\.*\w*:", "", prop_key)
        if prop_key.endswith(")"):
            prop_key = prop_key.split(")")[0]

        add_percent = False
        if prop_key.endswith("%"):
            add_percent = True
            prop_key = prop_key[:-1]

        if prop_key in unit_props:
            replacement = unit_props[prop_key]
            if isinstance(replacement, (int, float)) and replacement < 1:
                replacement = int(round(replacement * 100))
            replacement = str(replacement)
            if add_percent and replacement and not replacement.endswith("%"):
                replacement = f"{replacement}%"

        if token.endswith(")") and not token.startswith("("):
            replacement = f"{replacement})"
        if token.startswith("(") and not token.endswith(")"):
            replacement = f"({replacement}"

        desc = desc.replace(token, replacement)

    for variable in augment.get("variable_matches") or []:
        full_match = variable.get("full_match")
        if not full_match:
            continue

        value = variable.get("value")
        if value is None or value == "null":
            value = 0

        if variable.get("type") == "multiplier":
            multiplier = variable.get("multiplier", 1)
            try:
                multiplier = float(multiplier)
                value = float(value) * multiplier
            except (TypeError, ValueError):
                pass

        desc = desc.replace(full_match, format_value(value))

    for token, replacement in TOKEN_REPLACEMENTS.items():
        desc = re.sub(f"%{re.escape(token)}%", replacement, desc)
        desc = re.sub(re.escape(token), replacement, desc)

    for token, replacement in KEYWORD_REPLACEMENTS.items():
        if token in desc:
            desc = desc.replace(token, replacement)

    desc = re.sub(r"@[^@]+@", "", desc)
    desc = html.unescape(desc)
    desc = re.sub(r"<br\s*/?>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</?rules>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</?expandRowActive>|</?expandRow>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(r"</?row[^>]*>", " ", desc, flags=re.IGNORECASE)
    desc = re.sub(
        r"</?tooltipCalculationContainer>|</?tooltipCalculation>",
        " ",
        desc,
        flags=re.IGNORECASE,
    )
    desc = re.sub(r"<[^>]+>", " ", desc)
    desc = desc.replace("???", "Varies")
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    resp = requests.get(
        LOOKUP_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CodexBot/1.0)"},
    )
    resp.raise_for_status()
    payload = resp.json()
    lookup_augments = {a["apiName"]: a for a in payload.get("augments", [])}

    tier_resp = requests.get(
        TIERS_URL,
        params=DEFAULT_PARAMS,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CodexBot/1.0)"},
    )
    tier_resp.raise_for_status()
    tiers_payload = tier_resp.json()
    tier_list = tiers_payload.get("content", {}).get("content", {}).get("tierList", [])

    tier_labels = ["S", "A", "B", "C", "D"]
    tier_by_id: dict[str, str] = {}
    ordered_ids: list[str] = []
    for index, tier in enumerate(tier_list):
        label = tier_labels[index] if index < len(tier_labels) else f"T{index}"
        for entry in tier.get("content", []):
            api_name = entry.get("id")
            if not api_name:
                continue
            tier_by_id[api_name] = label
            ordered_ids.append(api_name)

    rows = []
    missing_from_lookup = []
    for api_name in sorted(set(ordered_ids)):
        augment = lookup_augments.get(api_name)
        if not augment:
            missing_from_lookup.append(api_name)
            continue

        tags = [tag for tag in augment.get("tags", []) if tag in ROUND_TAGS]
        icon = augment.get("icon", "")
        metatft_name = icon.split("/")[-1].split(".")[0] if icon else ""
        rows.append(
            {
                "api_name": api_name,
                "name": augment.get("name", ""),
                "description": render_description(augment),
                "tier": tier_by_id.get(api_name, "U"),
                "rarity": infer_rarity(api_name, augment),
                "tags": "|".join(tags),
                "icon": icon,
                "metatft_name": metatft_name,
            }
        )

    tier_sort = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "U": 5}
    rows.sort(key=lambda row: (tier_sort.get(row["tier"], 99), row["name"].lower()))

    with JSON_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source_lookup": LOOKUP_URL,
                "source_tiers": TIERS_URL,
                "count": len(rows),
                "lookup_count": len(lookup_augments),
                "tier_count": len(set(ordered_ids)),
                "missing_from_lookup": missing_from_lookup,
                "augments": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "api_name",
                "name",
                "description",
                "tier",
                "rarity",
                "tags",
                "icon",
                "metatft_name",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(
        "Wrote "
        f"{len(rows)} active augments to {JSON_OUTPUT} and {CSV_OUTPUT} "
        f"(lookup had {len(lookup_augments)} entries)"
    )


if __name__ == "__main__":
    main()
