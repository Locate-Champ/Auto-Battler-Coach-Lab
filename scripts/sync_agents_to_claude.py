#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS = REPO_ROOT / "AGENTS.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"


def normalize_newlines(s: str) -> str:
    # Normalize Windows CRLF and old Mac CR to LF
    return s.replace("\r\n", "\n").replace("\r", "\n")


def build_claude_from_agents(agents_text: str) -> str:
    text = normalize_newlines(agents_text)
    lines = text.split("\n")

    if not lines or not lines[0].startswith("#"):
        raise ValueError("AGENTS.md must start with a markdown title line like '# AGENTS'.")

    # Rewrite the CLAUDE header at the source so it stays deterministic.
    lines[0] = "# CLAUDE"
    generated_notice = "This file is generated from AGENTS.md. Do not edit directly."
    if len(lines) > 1:
        lines[1] = generated_notice
    else:
        lines.append(generated_notice)

    out = "\n".join(lines)
    # Ensure trailing newline
    if not out.endswith("\n"):
        out += "\n"
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if CLAUDE.md is not in sync.")
    args = parser.parse_args()

    agents_text = AGENTS.read_text(encoding="utf-8")
    expected = build_claude_from_agents(agents_text)

    current = ""
    if CLAUDE.exists():
        current = normalize_newlines(CLAUDE.read_text(encoding="utf-8"))
        if not current.endswith("\n"):
            current += "\n"

    if args.check:
        if current != expected:
            sys.stderr.write("CLAUDE.md is out of sync with AGENTS.md.\n")
            sys.stderr.write("Run: python scripts/sync_agents_to_claude.py\n")
            return 1
        return 0

    CLAUDE.write_text(expected, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
