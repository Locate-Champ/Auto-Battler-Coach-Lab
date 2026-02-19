#!/usr/bin/env python3
"""
Extract network request-like lines from MetaTFT log files.

Example:
  python scripts/extract_network_commands.py \
    --input "C:/Users/<you>/AppData/Local/Overwolf/Log/Apps/MetaTFT" \
    --output outputs/metatft_network_commands.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Iterator

TIMESTAMP_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})")
METHOD_URL_PATTERN = re.compile(
    r"\b(GET|POST|PUT|DELETE|PATCH|OPTIONS|HEAD)\b\s+(https?://[^\s\"]+)",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://[^\s\"]+", re.IGNORECASE)


def iter_log_files(input_path: Path) -> Iterator[Path]:
    if input_path.is_file():
        yield input_path
        return

    if input_path.is_dir():
        for path in sorted(input_path.glob("*.log")):
            yield path
        return

    raise FileNotFoundError(f"Input path not found: {input_path}")


def extract_lines(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8-sig", errors="ignore") as stream:
        for line in stream:
            if "http" not in line.lower():
                continue

            timestamp_match = TIMESTAMP_PATTERN.match(line)
            timestamp = timestamp_match.group(1) if timestamp_match else None

            method_match = METHOD_URL_PATTERN.search(line)
            if method_match:
                method = method_match.group(1).upper()
                url = method_match.group(2)
                yield {
                    "timestamp": timestamp,
                    "method": method,
                    "url": url,
                    "source_file": str(path),
                    "raw_line": line.strip(),
                }
                continue

            url_match = URL_PATTERN.search(line)
            if url_match:
                yield {
                    "timestamp": timestamp,
                    "method": None,
                    "url": url_match.group(0),
                    "source_file": str(path),
                    "raw_line": line.strip(),
                }


def write_jsonl(records: Iterable[dict], output_path: Path) -> int:
    count = 0
    with output_path.open("w", encoding="utf-8") as output_stream:
        for record in records:
            output_stream.write(json.dumps(record) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract network-like request lines from MetaTFT logs into JSONL."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a MetaTFT log file or directory containing .log files",
    )
    parser.add_argument(
        "--output",
        default="outputs/metatft_network_commands.jsonl",
        help="Output JSONL path (default: outputs/metatft_network_commands.jsonl)",
    )

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def record_iter() -> Iterator[dict]:
        for log_path in iter_log_files(input_path):
            yield from extract_lines(log_path)

    count = write_jsonl(record_iter(), output_path)
    print(f"Extracted {count} network lines -> {output_path}")


if __name__ == "__main__":
    main()
