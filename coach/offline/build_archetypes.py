from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _token_from_api_name(api_name: str) -> str:
    # TFT16_Kaisa -> Kaisa
    return api_name.split("_", 1)[-1] if "_" in api_name else api_name


def _to_item_id(token: str) -> str:
    s = token.strip()
    if not s:
        return s
    if s.startswith("TFT_"):
        return s
    if s.startswith("TFT16_"):
        return s
    return f"TFT_Item_{s}"


def _num(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            if "." in s:
                return float(s)
            return int(s)
        except Exception:
            return None
    return None


def build_archetypes(input_path: Path, output_path: Path) -> dict:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    comps = data.get("comps", []) or []

    archetypes = []
    for comp in comps:
        units = list(comp.get("units", []) or [])
        token_to_api = {
            _token_from_api_name(u): u
            for u in units
            if isinstance(u, str) and u
        }

        builds: list[dict[str, Any]] = []
        for b in (comp.get("builds", []) or []):
            if not isinstance(b, dict):
                continue
            unit_token = b.get("unit")
            unit_api = None
            if isinstance(unit_token, str) and unit_token:
                unit_api = token_to_api.get(unit_token)
                if unit_api is None:
                    unit_api = unit_token if unit_token.startswith("TFT") else f"TFT16_{unit_token}"

            items_out: list[str] = []
            for it in (b.get("items", []) or []):
                if isinstance(it, str) and it.strip():
                    items_out.append(_to_item_id(it))

            if unit_api and items_out:
                builds.append(
                    {
                        "unit": unit_api,
                        "unit_token": unit_token,
                        "items": items_out,
                        "games": _num(b.get("games")),
                        "avg_placement": _num(b.get("avg_placement")),
                        "place_change": _num(b.get("place_change")),
                    }
                )

        archetypes.append(
            {
                "archetype_id": str(comp.get("cluster_id", comp.get("name", "unknown"))),
                "name": str(comp.get("name", "unknown")),
                "tier": str(comp.get("tier", "C")),
                "units": units,
                "traits": [t.get("name") for t in (comp.get("traits", []) or []) if isinstance(t, dict) and t.get("name")],
                "builds": builds,
                "stats": {
                    "avg_placement": comp.get("avg_placement"),
                    "top4_rate": comp.get("top4_rate"),
                    "games_played": comp.get("games_played"),
                    "win_rate": comp.get("win_rate"),
                },
            }
        )

    out = {
        "schema_version": 1,
        "type": "coach_archetypes",
        "source": str(input_path),
        "count": len(archetypes),
        "archetypes": archetypes,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build coach archetype artifact from meta comps JSON")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/meta/comps.json"),
        help="Path to meta comps JSON (default: data/meta/comps.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/coach/archetypes.json"),
        help="Output artifact path (default: outputs/coach/archetypes.json)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    out = build_archetypes(args.input, args.output)
    print(f"[OK] Wrote {out['count']} archetypes -> {args.output}")


if __name__ == "__main__":
    main()
