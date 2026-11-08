#!/usr/bin/env python3
"""PreToolUse: blocks writes to data/raw/, and blocks submission if the validator has not passed."""
import json, os, re, sys
ev = json.load(sys.stdin)
tool, inp = ev.get("tool_name", ""), ev.get("tool_input", {})
path = inp.get("file_path", "") or ""
cmd = inp.get("command", "") or ""
RAW = ("data/raw/", "/datos/")
if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit") and any(r in path for r in RAW):
    print("data/raw/ is read-only: write to data/work/", file=sys.stderr); sys.exit(2)
if tool == "Bash" and re.search(r"(>|rm |mv |sed -i|tee ).*(data/raw/|datos/)", cmd):
    print("data/raw/ is read-only", file=sys.stderr); sys.exit(2)
if tool == "Bash" and "make submit" in cmd and not os.path.exists("out/.check_passed"):
    print("Run `make check` (and /close-check) first; out/.check_passed does not exist", file=sys.stderr); sys.exit(2)
sys.exit(0)
