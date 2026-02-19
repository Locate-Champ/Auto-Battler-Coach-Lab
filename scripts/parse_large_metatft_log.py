#!/usr/bin/env python3
"""
Parse large MetaTFT log files in a streaming fashion.

Example:
  python scripts/parse_large_metatft_log.py \
    --input "C:/Users/<you>/AppData/Local/Overwolf/Log/Apps/MetaTFT/background.html.log" \
    --output outputs/metatft_events.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TextIO

from app.watcher.parser import LogParser


def parse_stream(
    input_stream: TextIO, output_stream: TextIO, max_events: int | None = None
) -> int:
    parser = LogParser()
    count = 0

    for line in input_stream:
        event = parser.parse_line(line)
        if not event:
            continue
        output_stream.write(json.dumps(event.to_dict()) + "\n")
        count += 1
        if max_events is not None and count >= max_events:
            break

    return count


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description="Stream-parse large MetaTFT log files into JSONL events."
    )
    arg_parser.add_argument(
        "--input", required=True, help="Path to the MetaTFT log file"
    )
    arg_parser.add_argument(
        "--output",
        default="outputs/metatft_events.jsonl",
        help="Output JSONL path (default: outputs/metatft_events.jsonl)",
    )
    arg_parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Stop after emitting N events (useful for sampling).",
    )

    args = arg_parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", errors="ignore") as input_stream:
        with output_path.open("w", encoding="utf-8") as output_stream:
            count = parse_stream(input_stream, output_stream, args.max_events)

    print(f"Parsed {count} events -> {output_path}")


if __name__ == "__main__":
    main()
