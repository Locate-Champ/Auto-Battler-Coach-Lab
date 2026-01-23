#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

INCOMING_DIR = Path("knowledge-base/sources/web-scrape/incoming")
CANONICAL_DIR = Path("knowledge-base/sources/web-scrape/canonical")
METADATA_DIR = Path("knowledge-base/sources/web-scrape/metadata")
MANIFESTS_DIR = Path("knowledge-base/manifests")
OUTPUTS_DIR = Path("outputs/kb")

MANIFEST_JSONL = MANIFESTS_DIR / "manifest.jsonl"
MANIFEST_JSON = MANIFESTS_DIR / "manifest.json"
SUMMARY_CSV = OUTPUTS_DIR / "manifest-summary.csv"
FILE_MAP_JSON = METADATA_DIR / "file-map.json"
REPORT_MD = OUTPUTS_DIR / "ingestion-report.md"

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._ -]+")
H1_RE = re.compile(r"^#\s+(.*)\s*$")
H2_RE = re.compile(r"^##\s+(.*)\s*$")
H3_RE = re.compile(r"^###\s+(.*)\s*$")
URL_LABEL_RE = re.compile(r"^(Source|URL)\s*:\s*(https?://\S+)\s*$", re.IGNORECASE)
FRONTMATTER_KEY_RE = re.compile(r"^(url|canonical_url)\s*:\s*(https?://\S+)\s*$", re.IGNORECASE)
IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


@dataclass
class FileStats:
    path: Path
    relpath: str
    canonical_relpath: str
    canonical_filename: str
    size: int
    sha256: str
    line_count: int
    word_count: int
    title: str
    url: Optional[str]
    headings: list[str]
    has_h1: bool
    unclosed_code_fence: bool
    long_line_count: int
    local_image_links: list[str]
    local_image_missing: list[str]
    raw_html_lines: int
    decode_error: bool


def iter_markdown_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    if any(p.is_dir() for p in root.iterdir()):
        return sorted(p for p in root.rglob("*.md") if p.is_file())
    return sorted(p for p in root.glob("*.md") if p.is_file())


def sanitize_filename(name: str) -> str:
    sanitized = SAFE_FILENAME_RE.sub("-", name)
    sanitized = sanitized.strip()
    return sanitized or "untitled.md"


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_title(lines: list[str], fallback: str) -> tuple[str, bool]:
    for line in lines:
        match = H1_RE.match(line)
        if match:
            title = match.group(1).strip()
            if title:
                return title, True
    return fallback, False


def extract_url(lines: list[str]) -> Optional[str]:
    max_lines = 40
    in_frontmatter = False
    frontmatter_scanned = 0
    for idx, line in enumerate(lines[:max_lines]):
        if idx == 0 and line.strip() == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
                continue
            frontmatter_scanned += 1
            match = FRONTMATTER_KEY_RE.match(line.strip())
            if match:
                return match.group(2)
            if frontmatter_scanned > 20:
                in_frontmatter = False
            continue
        match = URL_LABEL_RE.match(line.strip())
        if match:
            return match.group(2)
    return None


def extract_headings(lines: list[str], limit: int = 30) -> list[str]:
    headings: list[str] = []
    for line in lines:
        for regex in (H2_RE, H3_RE):
            match = regex.match(line)
            if match:
                text = match.group(1).strip()
                if text:
                    headings.append(text)
                break
        if len(headings) >= limit:
            break
    return headings


def normalize_content(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))


def analyze_file(path: Path, canonical_path: Path) -> FileStats:
    data = path.read_bytes()
    sha256 = compute_sha256(data)
    size = len(data)
    decode_error = False
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        decode_error = True
        text = data.decode("utf-8", errors="ignore")

    normalized_text = normalize_content(text)
    if not decode_error:
        canonical_path.write_text(normalized_text, encoding="utf-8")
    else:
        canonical_path.write_bytes(data)

    lines = normalized_text.split("\n")
    line_count = len(lines)
    word_count = len(normalized_text.split()) if normalized_text.strip() else 0

    fallback_title = path.stem
    title, has_h1 = extract_title(lines, fallback_title)
    url = extract_url(lines)
    headings = extract_headings(lines)
    code_fence_count = sum(1 for line in lines if line.strip().startswith("```"))
    unclosed_code_fence = code_fence_count % 2 != 0
    long_line_count = sum(1 for line in lines if len(line) > 5000)

    local_image_links: list[str] = []
    local_image_missing: list[str] = []
    for line in lines:
        for match in IMAGE_LINK_RE.findall(line):
            link = match.strip()
            if link.startswith("http://") or link.startswith("https://"):
                continue
            if link.startswith("<") and link.endswith(">"):
                link = link[1:-1]
            local_image_links.append(link)
            candidate = (path.parent / link).resolve()
            if not candidate.exists():
                local_image_missing.append(link)

    raw_html_lines = sum(
        1
        for line in lines
        if "<table" in line.lower()
        or "<div" in line.lower()
        or "<span" in line.lower()
    )

    return FileStats(
        path=path,
        relpath=str(path.relative_to(INCOMING_DIR)).replace("\\", "/"),
        canonical_relpath=canonical_path.as_posix(),
        canonical_filename=canonical_path.name,
        size=size,
        sha256=sha256,
        line_count=line_count,
        word_count=word_count,
        title=title,
        url=url,
        headings=headings,
        has_h1=has_h1,
        unclosed_code_fence=unclosed_code_fence,
        long_line_count=long_line_count,
        local_image_links=local_image_links,
        local_image_missing=local_image_missing,
        raw_html_lines=raw_html_lines,
        decode_error=decode_error,
    )


def ensure_dirs() -> None:
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def build_report(stats: list[FileStats], duplicates: dict[str, list[FileStats]]) -> None:
    total = len(stats)
    empty_files = [s for s in stats if s.size < 200]
    h1_count = sum(1 for s in stats if s.has_h1)
    url_count = sum(1 for s in stats if s.url)
    unclosed = [s for s in stats if s.unclosed_code_fence]
    long_lines = [s for s in stats if s.long_line_count > 0]
    raw_html = [s for s in stats if s.raw_html_lines > 0]
    decode_issues = [s for s in stats if s.decode_error]

    local_image_links = sum(len(s.local_image_links) for s in stats)
    local_image_missing = sum(len(s.local_image_missing) for s in stats)

    lines = [
        "# Ingestion Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## File Counts",
        f"- Total markdown files: {total}",
        f"- Duplicate files by sha256: {len(duplicates)}",
        f"- Empty or near-empty files (< 200 bytes): {len(empty_files)}",
        "",
        "## Title Extraction",
        f"- Files with H1 titles: {h1_count}",
        f"- Files using filename fallback: {total - h1_count}",
        "",
        "## URL Extraction",
        f"- Files with explicit URL: {url_count}",
        "",
        "## Content Health",
        f"- Files with unclosed code fences: {len(unclosed)}",
        f"- Files with very long lines (> 5000 chars): {len(long_lines)}",
        f"- Files with raw HTML markers: {len(raw_html)}",
        f"- Files with UTF-8 decode issues: {len(decode_issues)}",
        "",
        "## Link + Asset Scan",
        f"- Local image links found: {local_image_links}",
        f"- Local image links missing targets: {local_image_missing}",
        "",
        "## Notes",
        "- No modifications were made to incoming files.",
    ]

    if duplicates:
        lines.append("")
        lines.append("### Duplicate groups")
        for sha, items in duplicates.items():
            lines.append(f"- {sha}: {', '.join(s.relpath for s in items)}")

    if empty_files:
        lines.append("")
        lines.append("### Near-empty files")
        for item in empty_files:
            lines.append(f"- {item.relpath} ({item.size} bytes)")

    if unclosed:
        lines.append("")
        lines.append("### Unclosed code fences")
        for item in unclosed:
            lines.append(f"- {item.relpath}")

    if long_lines:
        lines.append("")
        lines.append("### Files with long lines")
        for item in long_lines:
            lines.append(f"- {item.relpath} ({item.long_line_count} lines)")

    if raw_html:
        lines.append("")
        lines.append("### Raw HTML markers")
        for item in raw_html:
            lines.append(f"- {item.relpath} ({item.raw_html_lines} lines)")

    if decode_issues:
        lines.append("")
        lines.append("### UTF-8 decode issues")
        for item in decode_issues:
            lines.append(f"- {item.relpath}")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_manifest() -> None:
    ensure_dirs()
    files = list(iter_markdown_files(INCOMING_DIR))
    timestamp = datetime.now(timezone.utc).isoformat()

    stats: list[FileStats] = []
    entries: list[dict[str, object]] = []
    sha_groups: dict[str, list[FileStats]] = {}
    filename_map: dict[str, str] = {}
    by_id: dict[str, dict[str, str]] = {}

    for path in files:
        relpath = path.relative_to(INCOMING_DIR)
        sanitized_parts = [sanitize_filename(part) for part in relpath.parts]
        canonical_relpath = Path(*sanitized_parts)
        canonical_path = CANONICAL_DIR / canonical_relpath
        canonical_path.parent.mkdir(parents=True, exist_ok=True)

        stat = analyze_file(path, canonical_path)
        stats.append(stat)

        sha_groups.setdefault(stat.sha256, []).append(stat)

        if path.name != stat.canonical_filename:
            filename_map[path.name] = stat.canonical_filename

        entry_id = stat.sha256[:12]
        entry = {
            "id": entry_id,
            "source": "web-scrape",
            "original_filename": path.name,
            "original_relpath": stat.relpath,
            "canonical_relpath": stat.canonical_relpath,
            "bytes": stat.size,
            "sha256": stat.sha256,
            "line_count": stat.line_count,
            "word_count": stat.word_count,
            "title": stat.title,
            "url": stat.url,
            "headings": stat.headings,
            "created_at": timestamp,
        }
        entries.append(entry)
        by_id[entry_id] = {
            "original_relpath": stat.relpath,
            "canonical_relpath": stat.canonical_relpath,
        }

    duplicates = {sha: items for sha, items in sha_groups.items() if len(items) > 1}

    MANIFEST_JSONL.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    MANIFEST_JSON.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "title", "original_relpath", "canonical_relpath", "bytes", "sha256"],
        )
        writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "id": entry["id"],
                    "title": entry["title"],
                    "original_relpath": entry["original_relpath"],
                    "canonical_relpath": entry["canonical_relpath"],
                    "bytes": entry["bytes"],
                    "sha256": entry["sha256"],
                }
            )

    file_map = {
        "generated_at": timestamp,
        "by_id": by_id,
        "filename_map": filename_map,
    }
    FILE_MAP_JSON.write_text(json.dumps(file_map, indent=2) + "\n", encoding="utf-8")

    build_report(stats, duplicates)


if __name__ == "__main__":
    build_manifest()
