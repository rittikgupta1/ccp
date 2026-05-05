#!/usr/bin/env python3
"""
CCP — Central Context Package
Core save engine. Usage:

    kb "Title of entry" --team data --type analysis [--file output.md]
    echo "content" | kb "Title" --team data
    kb "Title" --team ops --skip-review
    kb "Title" --team data --dry-run
"""
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

from config import load_config, get_role, is_admin, get_content_type, get_teams
from git_ops import sync, commit_and_push, create_branch, create_pr, get_current_user, get_ccp_root


def parse_args():
    parser = argparse.ArgumentParser(
        prog="kb",
        description="Save knowledge to the CCP knowledge base.",
    )
    parser.add_argument("title", help="Title of the knowledge entry")
    parser.add_argument("--team", required=True, choices=get_teams(),
                        help="Team folder to save under")
    parser.add_argument("--type", dest="content_type", default="analysis",
                        help="Content type (analysis, query, playbook, decision, insight, model)")
    parser.add_argument("--file", "-f", help="Read content from this file")
    parser.add_argument("--skip-review", action="store_true",
                        help="Skip AI quality review (admin only)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be saved without committing")
    return parser.parse_args()


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:60].strip("-")


def gather_content(args) -> str:
    if args.file:
        path = Path(args.file).expanduser()
        if not path.exists():
            print(f"Error: file not found: {args.file}")
            sys.exit(1)
        return path.read_text()

    if not sys.stdin.isatty():
        return sys.stdin.read()

    # Try clipboard on macOS
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
        if result.returncode == 0 and result.stdout.strip():
            print(f"Read {len(result.stdout)} chars from clipboard.")
            confirm = input("Use clipboard content? [Y/n]: ").strip().lower()
            if confirm != "n":
                return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    print("Enter content (Ctrl+D when done):")
    lines = []
    try:
        while True:
            lines.append(input())
    except EOFError:
        pass
    return "\n".join(lines)


def format_entry(title: str, content: str, team: str, content_type: str, author: str) -> str:
    ct = get_content_type(content_type)
    expiry_days = ct.get("expiry_days", 90)
    expires = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
    date = datetime.now().strftime("%Y-%m-%d")

    frontmatter = f"""---
title: "{title}"
date: {date}
author: {author}
team: {team}
type: {content_type}
trust: draft
expires: {expires}
---"""
    return f"{frontmatter}\n\n# {title}\n\n{content}\n"


def run_scan(content: str) -> bool:
    try:
        from scan import scan_content, redact_warnings
    except ImportError:
        sys.path.insert(0, str(SCRIPT_DIR))
        from scan import scan_content, redact_warnings

    results = scan_content(content)

    if results["blocked"]:
        print("\n\033[91mBLOCKED — Secrets/credentials detected:\033[0m")
        for f in results["blocked"]:
            print(f"  - {f['pattern_name']}: {f['match']}")
        print("\nRemove these before saving. Cannot commit.")
        return False

    if results["warnings"]:
        print("\n\033[93mWARNING — Potentially sensitive content detected:\033[0m")
        for f in results["warnings"]:
            print(f"  - {f['pattern_name']}: {f['match']}")
        print("These will be auto-redacted.")

    return True


def run_review(content: str, content_type: str, skip: bool, is_admin_user: bool) -> bool:
    if skip:
        if is_admin_user:
            print("AI review skipped (admin override).")
            return True
        else:
            print("Error: only admins can skip AI review.")
            return False

    try:
        from review import review_local
    except ImportError:
        sys.path.insert(0, str(SCRIPT_DIR))
        from review import review_local

    print("Running AI quality review...")
    try:
        result = review_local(content, content_type)
    except Exception as e:
        print(f"\033[93mAI review unavailable ({e}). Proceeding without review.\033[0m")
        return True

    if result["verdict"] == "APPROVE":
        print("\033[92mAI Review: APPROVED\033[0m")
        return True

    print("\n\033[91mAI Review — Changes Needed:\033[0m")
    for comment in result["comments"]:
        print(f"  - {comment}")
    print("\nFix the content and re-run, or use --skip-review (admin only).")
    return False


def save_admin(filepath: Path, formatted: str, title: str) -> str:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(formatted)
    commit_and_push(str(filepath), f"kb: {title}")
    return str(filepath.relative_to(get_ccp_root()))


def save_contributor(filepath: Path, formatted: str, title: str, author: str) -> str:
    date = datetime.now().strftime("%Y%m%d")
    slug = slugify(title)
    branch_name = f"ccp/{author}/{date}-{slug}"

    create_branch(branch_name)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(formatted)

    rel_path = str(filepath.relative_to(get_ccp_root()))
    commit_and_push(str(filepath), f"kb: {title}")

    body = f"## New Knowledge Base Entry\n\n"
    body += f"- **Title:** {title}\n"
    body += f"- **Author:** {author}\n"
    body += f"- **File:** {rel_path}\n\n"
    body += f"*Auto-generated by CCP. AI review will run on this PR.*"

    pr_url = create_pr(f"CCP: {title}", body)
    return pr_url


def main():
    args = parse_args()

    ccp_root = Path(get_ccp_root())
    if not ccp_root.exists():
        print(f"Error: CCP repo not found at {ccp_root}")
        print("Run setup.sh first: curl -sL https://raw.githubusercontent.com/snabbit-tech/ccp/main/setup.sh | bash")
        sys.exit(1)

    author = os.environ.get("CCP_USER") or os.environ.get("KB_USER")
    if not author:
        try:
            author = get_current_user()
        except Exception:
            author = os.environ.get("USER", "unknown")

    content = gather_content(args)
    if not content.strip():
        print("Error: no content provided.")
        sys.exit(1)

    formatted = format_entry(args.title, content, args.team, args.content_type, author)
    date = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(args.title)
    filename = f"{date}_{slug}.md"
    filepath = ccp_root / "teams" / args.team / filename

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"Would save to: {filepath.relative_to(ccp_root)}")
        print(f"Author: {author}")
        print(f"Role: {get_role(author)}")
        print(f"Content type: {args.content_type}")
        print(f"Content length: {len(content)} chars")
        print(f"\nFormatted entry preview:\n")
        print(formatted[:500])
        if len(formatted) > 500:
            print(f"\n... ({len(formatted) - 500} more chars)")
        return

    if not run_scan(content):
        sys.exit(1)

    admin_user = is_admin(author)
    if not run_review(content, args.content_type, args.skip_review, admin_user):
        sys.exit(1)

    sync()

    if admin_user:
        rel_path = save_admin(filepath, formatted, args.title)
        print(f"\n\033[92mSaved to {rel_path}\033[0m")
        print("INDEX.md will be updated by GitHub Action.")
    else:
        pr_url = save_contributor(filepath, formatted, args.title, author)
        print(f"\n\033[92mPR created (AI-approved): {pr_url}\033[0m")
        print("Awaiting merge. Hard AI review will run on the PR.")


if __name__ == "__main__":
    main()
