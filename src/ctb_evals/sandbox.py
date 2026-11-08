"""Run a participant's ``run.py`` on unseen packets, the way the hidden leaderboard would.

Guarantees, in order of strength:
* fresh temporary directory per run, input copied in, output read back, directory removed;
* wall-clock timeout (default 600 s, as in the experiments) and the process group is killed on expiry;
* the network is disabled inside the child via ``sitecustomize`` (socket creation, DNS and
  ``create_connection`` raise). This blocks ordinary Python networking, not a determined
  adversary (a subprocess or ctypes could bypass it). For untrusted code, run inside a container
  with ``--network none``; see docs/methodology.md.
* writes into the program directory are detected and reported (a run that caches answers next to
  its code between runs would otherwise be invisible).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SITECUSTOMIZE = """\
import socket as _s
def _blocked(*a, **k):
    raise OSError("network disabled by ctb-evals sandbox")
_s.socket = _blocked
_s.create_connection = _blocked
_s.getaddrinfo = _blocked
"""


@dataclass
class RunResult:
    predictions: dict[str, Any]
    returncode: int | None
    seconds: float
    timed_out: bool
    stderr_tail: str
    wrote_to_program_dir: list[str] = field(default_factory=list)

    @property
    def error(self) -> str:
        if self.timed_out:
            return "timeout"
        if self.returncode:
            return self.stderr_tail
        return ""


def _snapshot(d: Path) -> dict[str, float]:
    out = {}
    for p in d.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            out[str(p.relative_to(d))] = p.stat().st_mtime
    return out


def run_program(
    program: str | Path,
    records: str | Path,
    timeout: float = 600.0,
    python: str = sys.executable,
) -> RunResult:
    """Execute ``python program records.jsonl out.json`` with no network; return parsed predictions."""
    program = Path(program).resolve()
    prog_dir = program.parent
    before = _snapshot(prog_dir)
    base = Path(tempfile.mkdtemp(prefix="ctb_run_"))
    try:
        shutil.copy(records, base / "records.jsonl")
        site = base / "_site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(SITECUSTOMIZE)
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        env["PYTHONPATH"] = str(site)
        env["NO_PROXY"] = "*"
        start = time.monotonic()
        timed_out = False
        proc = subprocess.Popen(
            [python, str(program), str(base / "records.jsonl"), str(base / "pred.json")],
            cwd=prog_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            _, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGKILL)
            _, err = proc.communicate()
        seconds = time.monotonic() - start
        try:
            with open(base / "pred.json", encoding="utf-8") as fh:
                preds = json.load(fh)
            if not isinstance(preds, dict):
                preds = {}
        except (OSError, ValueError):
            preds = {}
        after = _snapshot(prog_dir)
        changed = sorted(k for k, v in after.items() if before.get(k) != v)
        return RunResult(
            preds,
            proc.returncode,
            round(seconds, 2),
            timed_out,
            (err or b"").decode("utf-8", "replace")[-800:],
            changed,
        )
    finally:
        shutil.rmtree(base, ignore_errors=True)
