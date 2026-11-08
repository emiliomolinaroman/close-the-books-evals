#!/usr/bin/env python3
"""PostToolUse: añade cada acción de Claude al log de auditoría (out/agent_actions.jsonl)."""
import json, os, sys
from datetime import datetime, timezone
ev = json.load(sys.stdin)
os.makedirs("out", exist_ok=True)
entry = {"ts": datetime.now(timezone.utc).isoformat(), "actor": "claude", "tool": ev.get("tool_name"),
         "input": {k: str(v)[:300] for k, v in (ev.get("tool_input") or {}).items()}}
with open("out/agent_actions.jsonl", "a") as f:
    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
