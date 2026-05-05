#!/usr/bin/env python3
"""
CCP MCP Server for Claude Desktop.
Exposes save_to_ccp tool so non-tech users can save knowledge
by just talking to Claude Desktop.

Configured in ~/Library/Application Support/Claude/claude_desktop_config.json
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def handle_request(request: dict) -> dict:
    method = request.get("method", "")

    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "ccp", "version": "1.0.0"},
        }

    if method == "tools/list":
        return {
            "tools": [
                {
                    "name": "save_to_ccp",
                    "description": (
                        "Save knowledge to the team's Central Context Package (CCP) knowledge base. "
                        "Use this when the user wants to save an analysis, insight, query, playbook, "
                        "or any useful finding to the shared knowledge base."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Title of the knowledge entry (be specific and descriptive)",
                            },
                            "content": {
                                "type": "string",
                                "description": "The content to save — analysis, findings, queries, etc.",
                            },
                            "team": {
                                "type": "string",
                                "enum": ["data", "ops", "product", "engineering"],
                                "description": "Which team folder to save under",
                            },
                            "content_type": {
                                "type": "string",
                                "enum": ["analysis", "query", "playbook", "decision", "insight", "model"],
                                "description": "Type of content. Default: analysis",
                                "default": "analysis",
                            },
                        },
                        "required": ["title", "content", "team"],
                    },
                },
                {
                    "name": "search_ccp",
                    "description": (
                        "Search the team knowledge base for prior work. "
                        "Use this when the user asks if something has been done before, "
                        "or wants to find existing analyses, queries, or playbooks."
                    ),
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "What to search for in the knowledge base",
                            },
                        },
                        "required": ["query"],
                    },
                },
            ]
        }

    if method == "tools/call":
        tool_name = request["params"]["name"]
        args = request["params"]["arguments"]

        if tool_name == "save_to_ccp":
            return _save_to_ccp(args)
        elif tool_name == "search_ccp":
            return _search_ccp(args)

        return {"content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}], "isError": True}

    if method == "notifications/initialized":
        return None

    return {"error": {"code": -32601, "message": f"Unknown method: {method}"}}


def _save_to_ccp(args: dict) -> dict:
    title = args["title"]
    content = args["content"]
    team = args["team"]
    content_type = args.get("content_type", "analysis")

    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(content)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "kb.py"),
             title, "--team", team, "--type", content_type, "--file", tmp_path],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "CCP_ROOT": os.environ.get("CCP_ROOT", str(Path.home() / "ccp"))},
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
    except subprocess.TimeoutExpired:
        output = "Save timed out after 60 seconds."
        success = False
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {
        "content": [{"type": "text", "text": output if output.strip() else "Saved successfully."}],
        "isError": not success,
    }


def _search_ccp(args: dict) -> dict:
    query = args["query"]
    ccp_root = Path(os.environ.get("CCP_ROOT", Path.home() / "ccp"))
    index_path = ccp_root / "INDEX.md"

    if not index_path.exists():
        return {"content": [{"type": "text", "text": "Knowledge base is empty. No entries yet."}]}

    index_content = index_path.read_text()

    results = []
    query_words = query.lower().split()
    for line in index_content.split("\n"):
        if line.startswith("|") and not line.startswith("| Date") and not line.startswith("|---"):
            if any(word in line.lower() for word in query_words):
                results.append(line.strip())

    if not results:
        return {"content": [{"type": "text", "text": f"No entries found matching '{query}'."}]}

    text = f"Found {len(results)} matching entries:\n\n"
    for r in results[:10]:
        text += f"{r}\n"
    if len(results) > 10:
        text += f"\n... and {len(results) - 10} more."

    return {"content": [{"type": "text", "text": text}]}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(request)

        if response is None:
            continue

        msg = {"jsonrpc": "2.0", "id": request.get("id")}
        if "error" in response:
            msg["error"] = response["error"]
        else:
            msg["result"] = response

        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
