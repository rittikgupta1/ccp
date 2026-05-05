import os
import yaml
from pathlib import Path
from typing import Optional


_config_cache = None


def _find_config_path() -> Path:
    ccp_root = os.environ.get("CCP_ROOT")
    if ccp_root:
        p = Path(ccp_root) / "ccp.yaml"
        if p.exists():
            return p
        raise FileNotFoundError(f"ccp.yaml not found at CCP_ROOT={ccp_root}")

    current = Path(__file__).resolve().parent
    for _ in range(10):
        candidate = current / "ccp.yaml"
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent

    fallback = Path.home() / "ccp" / "ccp.yaml"
    if fallback.exists():
        return fallback

    raise FileNotFoundError(
        "ccp.yaml not found. Set CCP_ROOT or place ccp.yaml in a parent directory."
    )


def load_config(force_reload: bool = False) -> dict:
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache
    path = _find_config_path()
    with open(path) as f:
        _config_cache = yaml.safe_load(f)
    return _config_cache


def get_teams() -> list[str]:
    return load_config().get("teams", [])


def get_role(github_username: str) -> str:
    roles = load_config().get("roles", {})
    for role_name in ("admin", "reviewer"):
        users = roles.get(role_name, {}).get("users", [])
        if github_username in users:
            return role_name
    return "contributor"


def is_admin(github_username: str) -> bool:
    return get_role(github_username) == "admin"


def get_content_types() -> dict:
    return load_config().get("content_types", {})


_CONTENT_TYPE_DEFAULTS = {
    "description": "",
    "approval": "reviewer_or_admin",
    "expiry_days": 90,
}


def get_content_type(name: str) -> dict:
    ct = get_content_types().get(name)
    if ct is None:
        raise KeyError(f"Unknown content type: {name}")
    return {**_CONTENT_TYPE_DEFAULTS, **ct}


def get_scanner_patterns() -> dict:
    scanner = load_config().get("scanner", {})
    return {
        "block": scanner.get("block", []),
        "warn": scanner.get("warn", []),
    }


def get_ai_config() -> dict:
    return load_config().get("ai", {})
