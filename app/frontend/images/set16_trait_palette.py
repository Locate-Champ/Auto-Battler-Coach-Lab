import csv
import json
from pathlib import Path
import requests

URL = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/tfttraits.json"

# Tier-to-background mapping.
# Note: Riot’s file gives you tier labels (kBronze, etc). Exact hex values can vary by UI skin/theme.
# These are solid "UI tile" defaults that match the typical bronze/silver/gold/prismatic/unique look.
TIER_BG = {
    "kBronze":    "#B8773B",
    "kSilver":    "#C7D0DA",
    "kGold":      "#F2C24D",
    "kChromatic": "#B388FF",  # prismatic-ish anchor color (often rendered as a gradient in UI)
    "kUnique":    "#FF4D8D",
    None:         "#2C3442",  # inactive/unknown
}

OUT_CSV = Path("set16_trait_breakpoints.csv")
OUT_MD  = Path("set16_trait_breakpoints.md")

def fetch_traits():
    r = requests.get(URL, timeout=30)
    r.raise_for_status()
    return r.json()

def trait_rows_set16(traits):
    rows = []
    for t in traits:
        if t.get("set") != "TFTSet16":
            continue

        display_name = t.get("display_name", "")
        trait_id     = t.get("trait_id", "")
        icon_path    = t.get("icon_path", "")

        # Most breakpoints are in conditional_trait_sets
        # Some "unique" traits still appear there with style_name kUnique.
        csets = t.get("conditional_trait_sets", []) or []

        # If a trait has no conditional sets, still keep a placeholder row (rare in Set 16, but safe).
        if not csets:
            rows.append({
                "display_name": display_name,
                "trait_id": trait_id,
                "breakpoint_min_units": "",
                "breakpoint_max_units": "",
                "style_name": "",
                "bg_hex": TIER_BG.get(None),
                "icon_path": icon_path,
            })
            continue

        for cs in csets:
            style_name = cs.get("style_name")
            rows.append({
                "display_name": display_name,
                "trait_id": trait_id,
                "breakpoint_min_units": cs.get("min_units", ""),
                "breakpoint_max_units": cs.get("max_units", ""),
                "style_name": style_name,
                "bg_hex": TIER_BG.get(style_name, TIER_BG[None]),
                "icon_path": icon_path,
            })

    # Sort: trait name, then breakpoint
    def sort_key(r):
        # min_units may be "", keep those last
        try:
            mu = int(r["breakpoint_min_units"])
        except Exception:
            mu = 10**9
        return (r["display_name"].lower(), mu)

    rows.sort(key=sort_key)
    return rows

def write_csv(rows, path):
    fieldnames = [
        "display_name",
        "trait_id",
        "breakpoint_min_units",
        "breakpoint_max_units",
        "style_name",
        "bg_hex",
        "icon_path",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def write_markdown(rows, path):
    # A readable markdown table
    headers = ["Trait (in-game)", "trait_id (Riot)", "Min", "Max", "Tier (style_name)", "BG Hex", "Icon Path"]
    sep = ["---"] * len(headers)

    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(sep) + " |")

    for r in rows:
        lines.append("| " + " | ".join([
            str(r["display_name"]),
            str(r["trait_id"]),
            str(r["breakpoint_min_units"]),
            str(r["breakpoint_max_units"]),
            str(r["style_name"]),
            str(r["bg_hex"]),
            str(r["icon_path"]),
        ]) + " |")

    path.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    traits = fetch_traits()
    rows = trait_rows_set16(traits)

    write_csv(rows, OUT_CSV)
    write_markdown(rows, OUT_MD)

    print(f"Wrote {len(rows)} breakpoint rows")
    print(f"- {OUT_CSV.resolve()}")
    print(f"- {OUT_MD.resolve()}")
    print("\nPreview (first 25 rows):")
    for r in rows[:25]:
        print(f"{r['display_name']:<22} {r['trait_id']:<30} "
              f"({r['breakpoint_min_units']}–{r['breakpoint_max_units']}) "
              f"{r['style_name']:<10} {r['bg_hex']}")
