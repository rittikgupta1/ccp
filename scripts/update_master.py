#!/usr/bin/env python3
"""Regenerate MASTER-CONTEXT.md by sending all knowledge base content to Claude (Haiku via Vertex AI)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

import os
import yaml
import anthropic
from datetime import datetime, timezone

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIRS = ["teams", "company"]
MASTER_PATH = REPO_ROOT / "MASTER-CONTEXT.md"
CONFIG_PATH = REPO_ROOT / "ccp.yaml"

SUMMARIZE_PROMPT = (
    "Summarize all knowledge in this repository. "
    "Group by team, then by topic. "
    "For each topic: key findings, who contributed, open questions. "
    "Include cross-references between related entries."
)


def load_config() -> dict:
    """Load ccp.yaml for AI model settings."""
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {}


def collect_content() -> tuple[str, int, set[str]]:
    """Read all .md files in content dirs. Returns (combined_text, entry_count, contributors)."""
    sections = []
    entry_count = 0
    contributors: set[str] = set()

    for dir_name in CONTENT_DIRS:
        content_dir = REPO_ROOT / dir_name
        if not content_dir.exists():
            continue

        for md_file in sorted(content_dir.rglob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            rel_path = md_file.relative_to(REPO_ROOT)
            sections.append(f"--- FILE: {rel_path} ---\n{text}\n")
            entry_count += 1

            # Try to extract author from frontmatter
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        meta = yaml.safe_load(parts[1])
                        if isinstance(meta, dict) and meta.get("author"):
                            contributors.add(meta["author"])
                    except yaml.YAMLError:
                        pass

    combined = "\n".join(sections)
    return combined, entry_count, contributors


def generate_summary(content: str, config: dict) -> str:
    """Call Claude Haiku via Vertex AI to summarize the knowledge base."""
    ai_config = config.get("ai", {})
    project_id = os.environ.get(
        "ANTHROPIC_VERTEX_PROJECT_ID", ai_config.get("project", "")
    )
    region = os.environ.get("CLOUD_ML_REGION", ai_config.get("region", "global"))
    model = ai_config.get("model", "claude-haiku-4-5-20251001")

    client = anthropic.AnthropicVertex(project_id=project_id, region=region)

    if not content.strip():
        return "*No entries found in the knowledge base. Add .md files to teams/ or company/ to get started.*"

    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{SUMMARIZE_PROMPT}\n\n"
                    f"<knowledge_base>\n{content}\n</knowledge_base>"
                ),
            }
        ],
    )

    return message.content[0].text


def build_master_md(summary: str, entry_count: int, contributors: set[str]) -> str:
    """Build the full MASTER-CONTEXT.md content."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    contributor_count = len(contributors)

    lines = [
        "# CCP Knowledge Base -- Master Context",
        "",
        f"> Auto-generated on {now} | {entry_count} entries | {contributor_count} contributors",
        "",
        "*This file is auto-generated every two weeks. It summarizes everything in the knowledge base.*",
        "",
        summary,
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    config = load_config()
    content, entry_count, contributors = collect_content()

    print(f"Collected {entry_count} entries from {len(contributors)} contributors.")

    summary = generate_summary(content, config)
    master_md = build_master_md(summary, entry_count, contributors)

    MASTER_PATH.write_text(master_md, encoding="utf-8")
    print(f"MASTER-CONTEXT.md regenerated: {MASTER_PATH}")


if __name__ == "__main__":
    main()
