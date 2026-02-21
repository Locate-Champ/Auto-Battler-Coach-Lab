#!/usr/bin/env python3
"""Sync Ixtal quest reward ladders into the local simulator artifact.

Default source is the published LittleBuddyBot Ixtal quest sheet (CSV).
Writes normalized quest reward ladders to:
`simulator/game/ixtal_quest_rewards.json`
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

if __package__ in (None, ""):
    from simulator.game.unlocks import _normalize_ixtal_quest_name
else:
    from .unlocks import _normalize_ixtal_quest_name


DEFAULT_IXTAL_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vRgVnJkF2R4kdvRRg-cD0zPVN3y559udFAIVwtMqh1sQh9t9vbm8a9XBtJZtoecDlUGhAj9bCHRiIqL/pub"
    "?gid=0&single=true&output=csv"
)
DEFAULT_OUTPUT = Path(__file__).with_name("ixtal_quest_rewards.json")


def _read_csv_text(*, csv_path: Path | None, csv_url: str) -> str:
    if csv_path is not None:
        return csv_path.read_text(encoding="utf-8")

    request = urllib.request.Request(
        csv_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/132.0.0.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _parse_reward_ladders(csv_text: str) -> Dict[str, Tuple[int, ...]]:
    raw_lines = csv_text.splitlines()
    header_idx = -1
    for idx, line in enumerate(raw_lines):
        normalized = line.strip().lower()
        if normalized.startswith("icon,name,") or normalized.startswith("name,"):
            header_idx = idx
            break

    if header_idx < 0:
        raise ValueError("Could not find CSV header row with Name/Prize columns.")

    ladders: Dict[str, Tuple[int, ...]] = {}
    reader = csv.DictReader(io.StringIO("\n".join(raw_lines[header_idx:])))
    for row in reader:
        raw_name = (row.get("Name") or row.get("name") or "").strip()
        quest_name = _normalize_ixtal_quest_name(raw_name)
        if not quest_name:
            continue

        rewards: List[int] = []
        for column in ("Prize 2", "Prize 3", "Prize 4", "Prize 5", "Prize 6"):
            raw_reward = (row.get(column) or "").strip()
            if not raw_reward:
                continue
            digits = re.findall(r"\d+", raw_reward)
            if digits:
                rewards.append(int(digits[0]))

        if rewards:
            ladders[quest_name] = tuple(rewards)

    return dict(sorted(ladders.items(), key=lambda item: item[0]))


def _write_output(path: Path, ladders: Dict[str, Tuple[int, ...]]) -> None:
    serializable = {name: list(rewards) for name, rewards in ladders.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serializable, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Ixtal quest reward ladders for unlock tracking."
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=None,
        help="Optional local CSV path (defaults to downloading from --csv-url).",
    )
    parser.add_argument(
        "--csv-url",
        default=DEFAULT_IXTAL_CSV_URL,
        help="Source CSV URL for Ixtal quest rewards.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output artifact path (default: {DEFAULT_OUTPUT.as_posix()}).",
    )
    args = parser.parse_args()

    csv_text = _read_csv_text(csv_path=args.csv_path, csv_url=args.csv_url)
    ladders = _parse_reward_ladders(csv_text)
    if not ladders:
        raise RuntimeError("Parsed zero quest ladders; output not written.")

    _write_output(args.output, ladders)
    print(f"Wrote {len(ladders)} Ixtal quest reward ladders to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
