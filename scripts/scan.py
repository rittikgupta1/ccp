"""
CCP Secrets & PII Scanner.

Scans text content for secrets (hard block) and PII (warn + auto-redact).
Patterns are loaded from ccp.yaml; hardcoded fallbacks are used when the
config file is unavailable.

Usage:
    from scripts.scan import scan_content, redact_warnings

    result = scan_content(text)
    # result = {"blocked": [...], "warnings": [...]}

    if result["blocked"]:
        sys.exit("Commit blocked — secrets detected.")

    clean_text = redact_warnings(text, result["warnings"])
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Lib imports (path-safe for both package and script invocation)
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from config import load_config, get_scanner_patterns  # noqa: E402

# ---------------------------------------------------------------------------
# Hardcoded fallback patterns (used when ccp.yaml is unavailable)
# ---------------------------------------------------------------------------

_FALLBACK_BLOCK: list[str] = [
    r"sk-[a-zA-Z0-9]{20,}",                         # OpenAI / Anthropic API keys
    r"gho_[a-zA-Z0-9]{36}",                          # GitHub OAuth token
    r"ghp_[A-Za-z0-9]{36}",                          # GitHub PAT
    r"dapi[a-zA-Z0-9]{32,}",                         # Databricks PAT
    r"dbc-[a-f0-9-]{36}",                            # Databricks workspace ID
    r"AKIA[0-9A-Z]{16}",                             # AWS access key
    r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",        # PEM private keys
    r"jdbc:(?:mysql|postgresql|sqlserver)://[^\s]+",  # DB connection strings
]

_FALLBACK_WARN: list[str] = [
    r"\b[6-9][0-9]{9}\b",                            # Indian phone numbers
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}",  # Email addresses
    r"\b\d{4}\s?\d{4}\s?\d{4}\b",                    # Aadhaar-like 12-digit numbers
]

# ---------------------------------------------------------------------------
# Human-readable pattern names
# ---------------------------------------------------------------------------

_BLOCK_NAMES: dict[str, str] = {
    r"sk-[a-zA-Z0-9]{20,}":                        "api_key_generic",
    r"gho_[a-zA-Z0-9]{36}":                        "github_oauth_token",
    r"ghp_[A-Za-z0-9]{36}":                        "github_pat",
    r"dapi[a-zA-Z0-9]{32,}":                       "databricks_pat",
    r"dbc-[a-f0-9-]{36}":                          "databricks_workspace_id",
    r"AKIA[0-9A-Z]{16}":                           "aws_access_key",
    r"-----BEGIN (RSA |EC )?PRIVATE KEY-----":      "private_key",
    r"jdbc:(?:mysql|postgresql|sqlserver)://[^\s]+": "db_connection_string",
}

_WARN_NAMES: dict[str, str] = {
    r"\b[6-9][0-9]{9}\b":                              "indian_phone_number",
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}":  "email_address",
    r"\b\d{4}\s?\d{4}\s?\d{4}\b":                      "aadhaar_like_number",
}


def _pattern_name(pattern: str, names_map: dict[str, str], index: int) -> str:
    """Return a human-readable name for a pattern, or a generic fallback."""
    return names_map.get(pattern, f"pattern_{index}")


# ---------------------------------------------------------------------------
# Core scanning logic
# ---------------------------------------------------------------------------

def _load_patterns(config: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    """Resolve block/warn regex lists from config or fallbacks.

    Parameters
    ----------
    config : dict or None
        Full parsed ccp.yaml dict, or a dict with a "scanner" key.
        If None, attempts load_config() then falls back to hardcoded patterns.

    Returns
    -------
    (block_patterns, warn_patterns)
    """
    if config is not None:
        scanner = config.get("scanner", config)
        block = scanner.get("block", [])
        warn = scanner.get("warn", [])
        if block or warn:
            return block, warn

    # Try loading from ccp.yaml via config.py
    try:
        patterns = get_scanner_patterns()
        if patterns.get("block") or patterns.get("warn"):
            return patterns.get("block", []), patterns.get("warn", [])
    except (FileNotFoundError, Exception):
        pass

    # Hardcoded fallbacks
    return _FALLBACK_BLOCK, _FALLBACK_WARN


def _truncate(text: str, max_len: int = 40) -> str:
    """Truncate a string to max_len characters, appending '...' if cut."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _scan_patterns(
    lines: list[str],
    patterns: list[str],
    names_map: dict[str, str],
) -> list[dict[str, Any]]:
    """Run a list of regex patterns against lines, returning findings."""
    findings: list[dict[str, Any]] = []
    compiled: list[tuple[re.Pattern, str]] = []
    for i, pat in enumerate(patterns):
        try:
            compiled.append((re.compile(pat), _pattern_name(pat, names_map, i)))
        except re.error:
            continue

    for line_num, line in enumerate(lines, start=1):
        for regex, name in compiled:
            for m in regex.finditer(line):
                findings.append({
                    "pattern_name": name,
                    "match": _truncate(m.group(0)),
                    "line": line_num,
                })
    return findings


def scan_content(
    text: str,
    config: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Scan text for secrets (block) and PII (warn).

    Parameters
    ----------
    text : str
        The content to scan (e.g. file contents, PR diff body).
    config : dict, optional
        Parsed ccp.yaml or a dict with "scanner.block" / "scanner.warn".
        If omitted, loads from ccp.yaml or uses hardcoded defaults.

    Returns
    -------
    dict
        {
            "blocked": [{"pattern_name": str, "match": str, "line": int}, ...],
            "warnings": [{"pattern_name": str, "match": str, "line": int}, ...],
        }
    """
    block_patterns, warn_patterns = _load_patterns(config)
    lines = text.splitlines()

    blocked = _scan_patterns(lines, block_patterns, _BLOCK_NAMES)
    warnings = _scan_patterns(lines, warn_patterns, _WARN_NAMES)

    return {"blocked": blocked, "warnings": warnings}


# ---------------------------------------------------------------------------
# Auto-redaction
# ---------------------------------------------------------------------------

def redact_warnings(text: str, warnings: list[dict[str, Any]]) -> str:
    """Replace warned patterns in text with [REDACTED].

    Only redacts on lines that produced warnings.  Block-tier findings
    should prevent commit entirely, not be redacted.

    Parameters
    ----------
    text : str
        Original text content.
    warnings : list of dict
        Warning findings from scan_content().  Each must have "line" key.

    Returns
    -------
    str
        Text with all warned matches replaced by ``[REDACTED]``.
    """
    if not warnings:
        return text

    # Re-derive warn patterns to get the un-truncated regexes
    _, warn_patterns = _load_patterns(None)
    compiled: list[re.Pattern] = []
    for pat in warn_patterns:
        try:
            compiled.append(re.compile(pat))
        except re.error:
            continue

    warn_lines: set[int] = {w["line"] for w in warnings}

    lines = text.splitlines(keepends=True)
    for idx in range(len(lines)):
        line_num = idx + 1
        if line_num not in warn_lines:
            continue
        for regex in compiled:
            lines[idx] = regex.sub("[REDACTED]", lines[idx])

    return "".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Scan files passed as CLI arguments."""
    import argparse

    parser = argparse.ArgumentParser(description="CCP Secrets & PII Scanner")
    parser.add_argument("files", nargs="+", help="Files to scan")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero on warnings as well as blocks",
    )
    args = parser.parse_args()

    any_blocked = False
    any_warned = False

    for filepath in args.files:
        try:
            content = Path(filepath).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"[SKIP] {filepath}: {exc}")
            continue

        result = scan_content(content)

        for finding in result["blocked"]:
            any_blocked = True
            print(
                f"[BLOCK] {filepath}:{finding['line']}  "
                f"{finding['pattern_name']}  ->  {finding['match']}"
            )

        for finding in result["warnings"]:
            any_warned = True
            print(
                f"[WARN]  {filepath}:{finding['line']}  "
                f"{finding['pattern_name']}  ->  {finding['match']}"
            )

    if any_blocked:
        sys.exit(1)
    if any_warned and args.strict:
        sys.exit(2)


if __name__ == "__main__":
    main()
