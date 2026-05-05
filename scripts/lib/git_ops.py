import json
import os
import subprocess
from pathlib import Path


def get_ccp_root() -> str:
    return os.environ.get("CCP_ROOT", str(Path.home() / "ccp"))


def _run(cmd: list[str], cwd: str = None) -> subprocess.CompletedProcess:
    result = subprocess.run(
        cmd,
        cwd=cwd or get_ccp_root(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\nstderr: {result.stderr.strip()}"
        )
    return result


def sync():
    _run(["git", "pull", "--rebase"])


def commit_and_push(filepath: str, message: str):
    root = get_ccp_root()
    _run(["git", "add", filepath], cwd=root)
    _run(["git", "commit", "-m", message], cwd=root)
    _run(["git", "push"], cwd=root)


def create_branch(name: str):
    _run(["git", "checkout", "-b", name])


def create_pr(title: str, body: str) -> str:
    result = _run(["gh", "pr", "create", "--title", title, "--body", body])
    return result.stdout.strip()


def get_current_user() -> str:
    result = _run(["gh", "api", "user"], cwd=".")
    data = json.loads(result.stdout)
    return data["login"]
