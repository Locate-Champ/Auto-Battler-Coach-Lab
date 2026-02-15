from __future__ import annotations

from pathlib import Path

from coach.offline.build_archetypes import build_archetypes


def main() -> None:
    input_path = Path("data/meta/comps.json")
    output_path = Path("outputs/coach/archetypes.json")
    out = build_archetypes(input_path, output_path)
    print(f"[OK] Knowledge base built: {out['count']} archetypes -> {output_path}")


if __name__ == "__main__":
    main()

