#!/usr/bin/env python3
"""Extract TFT augment names/descriptions from MetaTFT lookup data."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import requests

LOOKUP_URL = "https://data.metatft.com/lookups/TFTSet16_latest_en_us.json"
OUTPUT_DIR = Path("outputs")
JSON_OUTPUT = OUTPUT_DIR / "metatft_augments_set16.json"
CSV_OUTPUT = OUTPUT_DIR / "metatft_augments_set16.csv"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    resp = requests.get(
        LOOKUP_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (compatible; CodexBot/1.0)"},
    )
    resp.raise_for_status()
    payload = resp.json()

    augments = payload.get("augments", [])
    rows = []
    for augment in augments:
        rows.append(
            {
                "api_name": augment.get("apiName", ""),
                "name": augment.get("name", ""),
                "description": augment.get("desc", ""),
                "tags": "|".join(augment.get("tags", [])),
                "icon": augment.get("icon", ""),
            }
        )

    rows.sort(key=lambda row: row["name"].lower())

    with JSON_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "source": LOOKUP_URL,
                "count": len(rows),
                "augments": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["api_name", "name", "description", "tags", "icon"],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} augments to {JSON_OUTPUT} and {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
