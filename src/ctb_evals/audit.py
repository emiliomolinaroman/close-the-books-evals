"""Audit Claude Code transcripts (JSONL) for isolation breaches, and extract cost and effort metrics.

Isolation in the experiments was by instruction (each agent was told to stay inside its workspace);
this audit is the evidence that it did. For every transcript the workspace is read from the first
prompt, then every tool call is checked for:
* paths under the experiment root that fall outside the agent's own workspace (answer keys,
  other teams' folders, raw benchmark data);
* tools the arm does not allow (the direct-answer arm may only use Read, Write, Edit and Glob).
It also records every path a tool call names inside ``shared_dirs`` (scratch folders several agents
can see, e.g. ``/tmp``). Those are not breaches of the answer keys, but two agents using the same
scratch file can interfere; ``scratch_collisions`` lists every such path. Token usage, tool calls and
turns go into ``results/runs.csv``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterator
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

DIRECT_ALLOWED = {"Read", "Write", "Edit", "Glob"}
NOT_ACTIONS = {"SubagentHandback"}  # the agent's final report, not a tool acting on files


def _lines(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(d, dict):
                yield d


def first_prompt(path: Path) -> str:
    for d in _lines(path):
        m = d.get("message")
        if d.get("type") == "user" and isinstance(m, dict):
            c = m.get("content")
            return c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
    return ""


def audit_transcript(
    path: Path, root: str, shared_dirs: tuple[str, ...] = (), workspace_re: str = r"(r\d+/[\w-]+)"
) -> dict[str, Any] | None:
    root = root.rstrip("/")
    prompt = first_prompt(path)
    m = re.search(re.escape(root) + "/" + workspace_re, prompt)
    if not m:
        return None
    ws = f"{root}/{m.group(1)}"
    direct = "answering directly" in prompt
    path_re = re.compile(re.escape(root) + r"/[^\s\"'`,;)\\*]+")
    shared_re = [re.compile(re.escape(d.rstrip("/")) + r"/[^\s\"'`,;)\\*|>]+") for d in shared_dirs]
    scratch: set[str] = set()
    tools: Counter[str] = Counter()
    breaches: set[str] = set()
    usage: Counter[str] = Counter()
    turns = 0
    seen_msgs: set[str] = set()
    times: list[datetime] = []
    for d in _lines(path):
        ts = d.get("timestamp")
        if isinstance(ts, str):
            with suppress(ValueError):
                times.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        msg = d.get("message")
        if not isinstance(msg, dict):
            continue
        if d.get("type") == "assistant":
            mid = msg.get("id")
            if mid and mid not in seen_msgs:  # one API message can span several JSONL lines
                seen_msgs.add(mid)
                turns += 1
                for k, v in (msg.get("usage") or {}).items():
                    if isinstance(v, int):
                        usage[k] += v
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for c in content:
            if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                continue
            name = str(c.get("name"))
            tools[name] += 1
            if name in NOT_ACTIONS:
                continue
            raw = json.dumps(c.get("input"), ensure_ascii=False)
            for rx in shared_re:
                scratch.update(h.rstrip(".:/") for h in rx.findall(raw))
            scratch.difference_update(d.rstrip("/") for d in shared_dirs)
            for hit in path_re.findall(raw):
                hit = hit.rstrip(".:")
                if not (hit == ws or hit.startswith(ws + "/")):
                    breaches.add(f"{name}: {hit}")
            if direct and name not in DIRECT_ALLOWED:
                breaches.add(f"tool not allowed in direct arm: {name}")
    return {
        "transcript": path.name,
        "workspace": ws[len(root) + 1 :],
        "arm": "direct" if direct else "agent",
        "turns": turns,
        "tool_calls": sum(tools.values()),
        "tools": dict(tools),
        "usage": dict(usage),
        "minutes": round((max(times) - min(times)).total_seconds() / 60, 1) if len(times) > 1 else None,
        "breaches": sorted(breaches),
        "scratch_paths": sorted(scratch),
    }


def audit_dir(
    transcripts: str | Path, root: str, pattern: str = "*.output", shared_dirs: tuple[str, ...] = ()
) -> list[dict[str, Any]]:
    out = []
    for f in sorted(Path(transcripts).glob(pattern)):
        r = audit_transcript(f, root, shared_dirs)
        if r is not None:
            out.append(r)
    return out


def scratch_collisions(report: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Scratch paths named by more than one workspace."""
    users: dict[str, set[str]] = {}
    for r in report:
        for p in r.get("scratch_paths", []):
            users.setdefault(p, set()).add(r["workspace"])
    return {p: sorted(w) for p, w in sorted(users.items()) if len(w) > 1}
