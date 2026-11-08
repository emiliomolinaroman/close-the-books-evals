#!/usr/bin/env python3
"""PreToolUse: bloquea escrituras en data/raw/ y la entrega si el validador no ha pasado."""
import json, os, re, sys
ev = json.load(sys.stdin)
tool, inp = ev.get("tool_name", ""), ev.get("tool_input", {})
path = inp.get("file_path", "") or ""
cmd = inp.get("command", "") or ""
RAW = ("data/raw/", "/datos/")
if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit") and any(r in path for r in RAW):
    print("data/raw/ es de solo lectura: escribe en data/work/", file=sys.stderr); sys.exit(2)
if tool == "Bash" and re.search(r"(>|rm |mv |sed -i|tee ).*(data/raw/|datos/)", cmd):
    print("data/raw/ es de solo lectura", file=sys.stderr); sys.exit(2)
if tool == "Bash" and "make submit" in cmd and not os.path.exists("out/.check_passed"):
    print("Ejecuta antes `make check` (y /close-check); no hay out/.check_passed", file=sys.stderr); sys.exit(2)
sys.exit(0)
