"""Run one agent "team" in its own workspace with the Claude Agent SDK, with enforced isolation.

The November 2026 experiments isolated teams by instruction and audited the transcripts afterwards
(``ctb audit``). This runner enforces the same rules in code instead:
* the agent's working directory is its workspace and it loads no user or project settings;
* every file-touching tool call is checked by ``can_use_tool``; a path outside the workspace is denied;
* web tools are disabled; Bash runs in the SDK sandbox with no network, and a command naming an
  absolute path outside the workspace (other than system locations) or ``..`` is denied;
* in the direct-answer arm only Read, Glob, Write and Edit exist at all.
Cost, turns and the full message log are written next to the workspace for ``ctb audit``.
The guard is defence in depth, not a security boundary: for untrusted settings run each team in a
container that never mounts the answer keys (docs/methodology.md). Requires the Claude Code CLI and an ``ANTHROPIC_API_KEY`` in the environment.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PATH_KEYS = ("file_path", "path", "notebook_path")
ABS_PATH = re.compile(r"(?<![\w.])/[\w./-]+")
SYSTEM_PREFIXES = ("/usr/", "/bin/", "/lib", "/opt/", "/dev/null", "/etc/ssl/")


@dataclass
class TeamConfig:
    workspace: Path
    prompt: str
    model: str | None = None
    direct: bool = False  # direct-answer arm: no code execution at all
    max_turns: int = 200
    max_budget_usd: float | None = None


def _inside(p: str, root: Path) -> bool:
    try:
        return Path(os.path.normpath(root / p if not os.path.isabs(p) else p)).is_relative_to(root)
    except (TypeError, ValueError):
        return False


def make_guard(root: Path) -> Any:
    from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

    root = root.resolve()

    async def guard(tool: str, args: dict[str, Any], _ctx: Any) -> Any:
        for k in PATH_KEYS:
            v = args.get(k)
            if isinstance(v, str) and not _inside(v, root):
                return PermissionResultDeny(message=f"{k} outside the workspace is not allowed")
        if tool == "Bash":
            cmd = str(args.get("command", ""))
            for p in ABS_PATH.findall(cmd):
                if not (_inside(p, root) or p.startswith(SYSTEM_PREFIXES)):
                    return PermissionResultDeny(message=f"path outside the workspace: {p}")
            if re.search(r"(^|[\s/])\.\.(/|\s|$)", cmd):
                return PermissionResultDeny(message="leaving the workspace is not allowed")
        return PermissionResultAllow()

    return guard


async def run_team(cfg: TeamConfig) -> dict[str, Any]:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    ws = cfg.workspace.resolve()
    tools = ["Read", "Glob", "Write", "Edit"] if cfg.direct else ["Read", "Glob", "Grep", "Write", "Edit", "Bash"]
    options = ClaudeAgentOptions(
        cwd=str(ws),
        tools=tools,
        allowed_tools=[],  # everything goes through the guard
        disallowed_tools=["WebFetch", "WebSearch"],
        can_use_tool=make_guard(ws),
        setting_sources=[],  # do not load the operator's own CLAUDE.md or settings
        sandbox={"enabled": True, "allowUnsandboxedCommands": False, "network": {"allowedDomains": []}},
        model=cfg.model,
        max_turns=cfg.max_turns,
        max_budget_usd=cfg.max_budget_usd,
    )
    tmp = ws / ".tmp"  # private scratch: in the 2026-11 runs a shared scratch folder let helper files collide
    tmp.mkdir(exist_ok=True)
    options.env = {"TMPDIR": str(tmp)}
    log_path = ws.parent / f"{ws.name}.transcript.jsonl"
    result: dict[str, Any] = {}

    async def prompt_stream() -> Any:  # can_use_tool requires streaming input
        yield {"type": "user", "message": {"role": "user", "content": cfg.prompt}}

    with open(log_path, "w", encoding="utf-8") as log:
        async for msg in query(prompt=prompt_stream(), options=options):
            log.write(json.dumps(_to_jsonable(msg), ensure_ascii=False, default=str) + "\n")
            if isinstance(msg, ResultMessage):
                result = {
                    "workspace": ws.name,
                    "turns": msg.num_turns,
                    "cost_usd": msg.total_cost_usd,
                    "duration_s": msg.duration_ms / 1000,
                    "usage": msg.usage,
                    "is_error": msg.is_error,
                    "permission_denials": len(msg.permission_denials or []),
                }
    (ws.parent / f"{ws.name}.result.json").write_text(json.dumps(result, indent=1, default=str) + "\n")
    return result


def _to_jsonable(msg: Any) -> Any:
    from dataclasses import asdict, is_dataclass

    return {
        "type": type(msg).__name__,
        **(asdict(msg) if is_dataclass(msg) and not isinstance(msg, type) else {"repr": repr(msg)}),
    }


def run(cfg: TeamConfig) -> dict[str, Any]:
    return asyncio.run(run_team(cfg))
