#!/usr/bin/env python3
"""Rebuild INDEX.md from YAML frontmatter in teams/ and company/ markdown files."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import yaml
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIRS = ["teams", "company"]
INDEX_PATH = REPO_ROOT / "INDEX.md"


def parse_frontmatter(filepath: Path) -> dict | None:
    """Extract YAML frontmatter (between --- markers) from a markdown file."""
    text = filepath.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None

    if not isinstance(meta, dict):
        return None

    return meta


def collect_entries() -> list[dict]:
    """Walk content dirs and collect entries with frontmatter."""
    entries = []

    for dir_name in CONTENT_DIRS:
        content_dir = REPO_ROOT / dir_name
        if not content_dir.exists():
            continue

        for md_file in content_dir.rglob("*.md"):
            meta = parse_frontmatter(md_file)
            if meta is None:
                continue

            rel_path = md_file.relative_to(REPO_ROOT)

            # Infer team from directory structure: teams/<team>/... or "company"
            parts = rel_path.parts
            if parts[0] == "teams" and len(parts) >= 2:
                team = parts[1]
            elif parts[0] == "company":
                team = "company"
            else:
                team = "unknown"

            entries.append(
                {
                    "date": str(meta.get("date", "unknown")),
                    "title": meta.get("title", md_file.stem),
                    "team": team,
                    "type": meta.get("type", "unknown"),
                    "author": meta.get("author", "unknown"),
                    "link": str(rel_path),
                }
            )

    return entries


def sort_entries(entries: list[dict]) -> list[dict]:
    """Sort entries by date descending (newest first). Unknown dates go last."""

    def sort_key(entry: dict) -> str:
        date = entry["date"]
        if date == "unknown":
            return "0000-00-00"
        return date

    return sorted(entries, key=sort_key, reverse=True)


def build_index_md(entries: list[dict]) -> str:
    """Build the full INDEX.md content."""
    contributors = {e["author"] for e in entries if e["author"] != "unknown"}
    total = len(entries)
    contributor_count = len(contributors)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        "# CCP Knowledge Base Index",
        "",
        f"> Last updated: {now} | Total entries: {total} | Contributors: {contributor_count}",
        "",
        "| Date | Title | Team | Type | Author | Link |",
        "|------|-------|------|------|--------|------|",
    ]

    for entry in entries:
        link = f"[{entry['title']}]({entry['link']})"
        lines.append(
            f"| {entry['date']} | {entry['title']} | {entry['team']} "
            f"| {entry['type']} | {entry['author']} | {link} |"
        )

    lines.append("")  # trailing newline
    return "\n".join(lines)


def main() -> None:
    entries = collect_entries()
    sorted_entries = sort_entries(entries)
    content = build_index_md(sorted_entries)

    INDEX_PATH.write_text(content, encoding="utf-8")
    print(f"INDEX.md updated: {len(sorted_entries)} entries, written to {INDEX_PATH}")


if __name__ == "__main__":
    main()
