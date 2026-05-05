"""
CCP AI Content Reviewer.

Two review modes:
- review_local()  — fast Haiku review for local drafts before commit.
- review_pr()     — thorough Sonnet review for GitHub PR diffs (used by CI).

Both return:
    {"verdict": "APPROVE" | "REQUEST_CHANGES", "comments": [str, ...]}

Usage:
    from scripts.review import review_local, review_pr

    result = review_local(content, content_type="analysis")
    if result["verdict"] == "REQUEST_CHANGES":
        for c in result["comments"]:
            print(c)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lib imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from ai_client import call_haiku, call_sonnet  # noqa: E402
from config import get_content_types  # noqa: E402

# ---------------------------------------------------------------------------
# Shared review criteria
# ---------------------------------------------------------------------------

_QUALITY_CHECKS = """\
1. VAGUE CLAIMS: Statements like "performance improved" or "significantly
   better" without concrete numbers.  Ask for specific metrics.
2. SUBJECTIVE AS FACT: Opinions presented as facts without evidence.
   Ask for data or qualification.
3. UNCLEAR WRITING: Sentences a reader couldn't act on or would
   misunderstand.  Ask for rephrasing.
4. MISSING CODE/SQL: If the content references a query, script, or
   model but doesn't include it.  Ask to include the relevant code.
5. CONTRADICTIONS: Claims that contradict common data-engineering best
   practices or well-known facts.  Flag for verification.
6. WRONG TEAM FOLDER: If the content clearly belongs to a different team
   than indicated (e.g. an ops playbook filed under "data")."""

# ---------------------------------------------------------------------------
# Review prompts
# ---------------------------------------------------------------------------

_LOCAL_PROMPT = f"""\
You are a strict technical reviewer for an internal knowledge base (CCP).
The knowledge base stores analyses, SQL queries, playbooks, decisions,
insights, and model documentation for a home-services company.

Review the content below and check for ALL of the following issues:

{_QUALITY_CHECKS}

Respond ONLY with valid JSON (no markdown fences, no surrounding text):
{{
  "verdict": "APPROVE" or "REQUEST_CHANGES",
  "comments": ["list of specific issues found, or empty list if approved"]
}}

If the content is acceptable, return verdict APPROVE with an empty comments
list.  Be strict but fair — only flag genuine issues, not style preferences."""

_PR_PROMPT = f"""\
You are a thorough technical reviewer for the CCP knowledge base (a
GitHub-repo-based team knowledge store).  A contributor has opened a PR
to add or update content.

Review the PR diff and check for ALL of the following:

**Content quality (apply to every file):**
{_QUALITY_CHECKS}

**Structural checks (PR-level):**
7. DUPLICATE ENTRY: If INDEX.md content is provided, check whether the
   new entry's title or topic already exists.  Flag duplicates.
8. YAML FRONTMATTER: If a file has YAML frontmatter (between ---
   delimiters), verify required fields exist: title, type, team, author,
   date.  Flag missing or malformed fields.
9. TYPE MISMATCH: If frontmatter declares type "query" but the content
   has no code block, or declares "analysis" but has no data — flag it.
10. CONTENT-TYPE CONSISTENCY: The declared type should match the actual
    content.  An "analysis" should have metrics; a "playbook" should have
    actionable steps; a "decision" should state the decision and rationale.

Respond ONLY with valid JSON (no markdown fences, no surrounding text):
{{
  "verdict": "APPROVE" or "REQUEST_CHANGES",
  "comments": ["list of specific issues found, or empty list if approved"]
}}"""

# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_ai_response(raw: str) -> dict[str, Any]:
    """Extract the JSON verdict from an AI response.

    Tolerates markdown code fences and surrounding prose.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract a JSON object from surrounding text
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                return _fallback_response()
        else:
            return _fallback_response()

    return _normalize(parsed)


def _fallback_response() -> dict[str, Any]:
    return {
        "verdict": "REQUEST_CHANGES",
        "comments": [
            "AI reviewer returned unparseable response. Manual review required."
        ],
    }


def _normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    verdict = str(parsed.get("verdict", "REQUEST_CHANGES")).upper()
    if verdict not in ("APPROVE", "REQUEST_CHANGES"):
        verdict = "REQUEST_CHANGES"

    comments = parsed.get("comments", [])
    if isinstance(comments, str):
        comments = [comments] if comments else []
    elif not isinstance(comments, list):
        comments = []

    return {"verdict": verdict, "comments": comments}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def review_local(
    content: str,
    content_type: str = "analysis",
) -> dict[str, Any]:
    """Fast local review using Haiku before commit.

    Parameters
    ----------
    content : str
        The markdown / text content to review.
    content_type : str
        One of the CCP content types (analysis, query, playbook, decision,
        insight, model).  Used to give the reviewer context.

    Returns
    -------
    dict
        {"verdict": "APPROVE" | "REQUEST_CHANGES", "comments": [...]}
    """
    type_hint = ""
    try:
        types = get_content_types()
        if content_type in types:
            desc = types[content_type].get("description", "")
            type_hint = f"\nDeclared content type: {content_type} — {desc}\n"
    except Exception:
        type_hint = f"\nDeclared content type: {content_type}\n"

    user_msg = (
        f"Content type: {content_type}"
        f"{type_hint}\n"
        f"--- CONTENT START ---\n"
        f"{content}\n"
        f"--- CONTENT END ---"
    )

    prompt = f"{_LOCAL_PROMPT}\n\n{user_msg}"
    raw = call_haiku(prompt, max_tokens=1024)
    return _parse_ai_response(raw)


def review_pr(
    pr_diff: str,
    index_md_content: str = "",
) -> dict[str, Any]:
    """Thorough PR review using Sonnet (for GitHub Actions CI).

    Parameters
    ----------
    pr_diff : str
        The full PR diff (unified diff format).
    index_md_content : str
        Current contents of INDEX.md, used for duplicate detection.
        Pass empty string if unavailable.

    Returns
    -------
    dict
        {"verdict": "APPROVE" | "REQUEST_CHANGES", "comments": [...]}
    """
    sections: list[str] = []

    if index_md_content.strip():
        sections.append(
            "--- CURRENT INDEX.md (check for duplicate entries) ---\n"
            f"{index_md_content}\n"
            "--- END INDEX.md ---"
        )

    sections.append(
        "--- PR DIFF START ---\n"
        f"{pr_diff}\n"
        "--- PR DIFF END ---"
    )

    user_msg = "\n\n".join(sections)
    prompt = f"{_PR_PROMPT}\n\n{user_msg}"
    raw = call_sonnet(prompt, max_tokens=4096)
    return _parse_ai_response(raw)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Review files or diffs passed via CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="CCP AI Content Reviewer")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # Local review mode
    local_p = subparsers.add_parser("local", help="Fast local review (Haiku)")
    local_p.add_argument("file", help="File to review")
    local_p.add_argument(
        "--type",
        dest="content_type",
        default="analysis",
        help="Content type (analysis, query, playbook, decision, insight, model)",
    )

    # PR review mode
    pr_p = subparsers.add_parser("pr", help="Thorough PR review (Sonnet)")
    pr_p.add_argument("diff_file", help="File containing PR diff")
    pr_p.add_argument(
        "--index",
        default="",
        help="Path to INDEX.md for duplicate checking",
    )

    args = parser.parse_args()

    if args.mode == "local":
        content = Path(args.file).read_text(encoding="utf-8")
        result = review_local(content, content_type=args.content_type)
    else:
        diff = Path(args.diff_file).read_text(encoding="utf-8")
        index_content = ""
        if args.index:
            index_content = Path(args.index).read_text(encoding="utf-8")
        result = review_pr(diff, index_md_content=index_content)

    print(json.dumps(result, indent=2))

    if result["verdict"] == "REQUEST_CHANGES":
        sys.exit(1)


if __name__ == "__main__":
    main()
