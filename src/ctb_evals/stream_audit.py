"""Audit one `claude -p --output-format stream-json --verbose` transcript.

Checks what the 2026-11-08 follow-up promises about every session: the model of every assistant
message, the tools called, that every path a tool names is inside the session's own folder, which
skills ran, and what the run reports about turns, cost and permission denials.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

PATH_KEYS = ("file_path", "path", "notebook_path")


def _inside(p: str, root: Path) -> bool:
    q = Path(p)
    q = q if q.is_absolute() else root / q
    try:
        q.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def audit_stream(
    lines: list[str], workspace: Path, allowed_tools: set[str], model: str = "claude-opus-5-5"
) -> dict[str, Any]:
    models: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    outside: list[str] = []
    skills: list[str] = []
    init: dict[str, Any] = {}
    result: dict[str, Any] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            init = e
        elif e.get("type") == "assistant":
            msg = e.get("message") or {}
            if msg.get("model"):
                models[msg["model"]] += 1
            for block in msg.get("content") or []:
                if block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                tools[name] += 1
                inp = block.get("input") or {}
                for k in PATH_KEYS:
                    if isinstance(inp.get(k), str) and not _inside(inp[k], workspace):
                        outside.append(inp[k])
                if name == "Skill":
                    skills.append(str(inp.get("skill") or inp.get("command") or inp.get("name")))
        elif e.get("type") == "result":
            result = e
    return {
        "models": dict(models),
        "tools": dict(tools),
        "disallowed_tools": sorted(set(tools) - allowed_tools),
        "paths_outside_workspace": outside,
        "skills_called": skills,
        "available_tools": init.get("tools"),
        "claude_code_version": init.get("claude_code_version"),
        "api_key_source": init.get("apiKeySource"),
        "num_turns": result.get("num_turns"),
        "is_error": result.get("is_error"),
        "subtype": result.get("subtype"),
        "total_cost_usd": result.get("total_cost_usd"),
        "usage": result.get("usage"),
        "permission_denials": len(result.get("permission_denials") or []),
        "session_id": result.get("session_id") or init.get("session_id"),
        "clean": bool(result) and not outside and not (set(tools) - allowed_tools) and set(models) == {model},
    }


def audit_file(path: Path, workspace: Path, allowed_tools: set[str], model: str = "claude-opus-5-5") -> dict[str, Any]:
    return audit_stream(path.read_text(encoding="utf-8").splitlines(), workspace, allowed_tools, model)
