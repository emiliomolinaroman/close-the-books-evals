"""Run the 2026-11-08 follow-up with headless Claude Code (`claude -p`), from the repository root.

    python experiments/2026-11/followup_teaching/harness.py test   <campaign> <arm> [--jobs 8]
    python experiments/2026-11/followup_teaching/harness.py train  <campaign> <chain>
    python experiments/2026-11/followup_teaching/harness.py seed   <campaign> <chain>
    python experiments/2026-11/followup_teaching/harness.py audit  <campaign>
    python experiments/2026-11/followup_teaching/harness.py collect <campaign> <arm> <team_outputs_dir>

The harness, not the model, decides what runs next. Every session gets a fresh context, its own
folder as working directory, a fixed model, a fixed tool list and a turn limit, all set on the
command line (the brief repeats the rules, but the CLI enforces them):

* `--setting-sources project`, `--strict-mcp-config` with no servers and auto memory off: no user
  CLAUDE.md, hooks, plugins, MCP servers or memory reach the agent (checked in the pilot);
* `--tools` lists the only tools that exist in the session; `--permission-mode acceptEdits` lets it
  write inside its folder and nowhere else; a read outside the folder needs a permission no one can
  grant in print mode;
* the subscription login is used (no API key in the environment; `apiKeySource` is audited).

Transcripts go to `<campaign>/_logs/`, outside every agent folder. Training packets, their answers
and the feedback archive live in `<campaign>/_staging/` and `<campaign>/_archive/`, also outside.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ctb_evals.finbalance.evaluate import load_answer_dir
from ctb_evals.finbalance.feedback import feedback
from ctb_evals.finbalance.scoring import score_record
from ctb_evals.stream_audit import audit_file

MODEL = "claude-opus-5-5"
MAX_TURNS = 40
TIMEOUT_S = 1500
BRIEFS = Path("prompts/agent_briefs")
TOOLS = {"skill": ["Read", "Write", "Skill"]}
DEFAULT_TOOLS = ["Read", "Write"]
DROP_ENV = ("ANTHROPIC_API_KEY", "CLAUDECODE", "CLAUDE_PID", "CLAUDE_EFFORT")


def _env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in DROP_ENV and not k.startswith("CLAUDE_CODE_")}


def _claude(campaign: Path, ws: Path, prompt: str, tools: list[str], log: Path, resume: str | None = None) -> dict:
    mcp = campaign / "_mcp_empty.json"
    if not mcp.exists():
        mcp.write_text('{"mcpServers": {}}\n')
    cmd = ["claude", "-p", prompt, "--model", MODEL, "--setting-sources", "project", "--strict-mcp-config",
           "--mcp-config", str(mcp), "--tools", ",".join(tools), "--permission-mode", "acceptEdits",
           "--settings", '{"autoMemoryEnabled": false}', "--max-turns", str(MAX_TURNS),
           "--output-format", "stream-json", "--verbose"]  # fmt: skip
    if resume:
        cmd += ["--resume", resume]
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log.open("w") as fh:
        p = subprocess.Popen(cmd, cwd=ws, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             env=_env(), start_new_session=True)  # fmt: skip
        try:
            p.wait(timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, 9)
            p.wait()
    a = audit_file(log, ws, set(tools), MODEL)
    a.update(workspace=ws.name, exit=p.returncode, wall_s=round(time.time() - t0, 1), log=log.name)
    return a


def _brief(name: str, **kw: str) -> str:
    text = (BRIEFS / f"teaching_{name}.md").read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{" + k + "}", v)
    if "{" in re.sub(r"\{\"|<record_id>", "", text):
        sys.exit(f"unfilled placeholder in {name}")
    return text.strip()


def _workspaces(campaign: Path, arm: str) -> list[Path]:
    return sorted((p for p in campaign.iterdir() if re.fullmatch(rf"{arm}_\d+", p.name)), key=lambda p: int(p.name.rsplit("_", 1)[1]))


def run_test(campaign: Path, arm: str, jobs: int) -> None:
    brief = {"control": "control", "puntuacion": "puntuacion", "ejemplos3": "ejemplos3", "skill": "skill"}.get(
        arm, "memoria" if arm.startswith("memoria_") else None
    )
    if brief is None:
        sys.exit(f"unknown arm {arm}")
    tools = TOOLS.get(arm, DEFAULT_TOOLS)

    def one(ws: Path) -> dict:
        files = ", ".join(sorted(p.name for p in (ws / "paquetes").iterdir()))
        if brief == "memoria" and not (ws / "memoria" / "NOTES.md").exists():
            sys.exit(f"{ws.name}: memoria/NOTES.md missing; run `seed` first")
        return _claude(campaign, ws, _brief(brief, folder=str(ws), files=files), tools, campaign / "_logs" / f"{ws.name}.jsonl")

    wss = _workspaces(campaign, arm)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for a in pool.map(one, wss):
            print(json.dumps({k: a[k] for k in ("workspace", "clean", "models", "tools", "num_turns", "total_cost_usd", "wall_s")}))


def _answer(ws: Path, tr: str) -> object:
    preds, _ = load_answer_dir(ws / "salida")
    return preds.get(tr)


def run_train(campaign: Path, chain: str) -> None:
    ws = campaign / f"tren_{chain}"
    stage = campaign / "_staging" / chain
    arch = campaign / "_archive" / chain
    steps = sorted(stage.glob("TR*.txt"), key=lambda p: int(p.stem[2:]))
    rows = []
    for pk in steps:
        tr = pk.stem
        for sub in ("paquete_actual", "salida", "revision"):  # nothing but memoria/ carries over
            for f in (ws / sub).iterdir():
                (arch / f"before_{tr}").mkdir(parents=True, exist_ok=True)
                shutil.move(str(f), arch / f"before_{tr}" / f"{sub}__{f.name}")
        shutil.copy(pk, ws / "paquete_actual" / pk.name)
        a1 = _claude(campaign, ws, _brief("train_answer", folder=str(ws), tr=tr), DEFAULT_TOOLS,
                     campaign / "_logs" / f"tren_{chain}_{tr}_answer.jsonl")  # fmt: skip
        sol = json.loads((stage / f"{tr}_solution.json").read_text())
        types = json.loads((stage / f"{tr}_doc_types.json").read_text())
        pred = _answer(ws, tr)
        (ws / "revision" / f"{tr}.md").write_text(feedback(tr, sol, pred, types), encoding="utf-8")
        a2 = {}
        if a1.get("session_id"):
            a2 = _claude(campaign, ws, _brief("train_update", tr=tr), DEFAULT_TOOLS,
                         campaign / "_logs" / f"tren_{chain}_{tr}_update.jsonl", resume=a1["session_id"])  # fmt: skip
        notes = ws / "memoria" / "NOTES.md"
        arch.mkdir(parents=True, exist_ok=True)
        if notes.exists():
            shutil.copy(notes, arch / f"NOTES_after_{tr}.md")
        o = score_record(tr, sol, pred).as_dict()
        row = {"step": tr, "correct": o["correct"], "tp_strict": o["tp_strict"], "n_expected": o["n_expected"],
               "n_predicted": o["n_predicted"], "answer_clean": a1.get("clean"), "update_clean": a2.get("clean"),
               "notes_words": len(notes.read_text().split()) if notes.exists() else 0}  # fmt: skip
        rows.append(row)
        print(json.dumps(row))
    (campaign / "_logs" / f"tren_{chain}_steps.json").write_text(json.dumps(rows, indent=1))


def seed(campaign: Path, chain: str) -> None:
    notes = campaign / f"tren_{chain}" / "memoria" / "NOTES.md"
    if not notes.exists():
        sys.exit(f"{notes} missing: the chain wrote no notes")
    for ws in _workspaces(campaign, f"memoria_{chain}"):
        (ws / "memoria").mkdir(exist_ok=True)
        shutil.copy(notes, ws / "memoria" / "NOTES.md")
    print(f"seeded {chain}: {len(notes.read_text().split())} words")


def audit(campaign: Path) -> None:
    out, rows = [], []
    for log in sorted((campaign / "_logs").glob("*.jsonl")):
        name = log.stem
        m = re.match(r"tren_([ab])_TR\d+_(answer|update)$", name)
        ws = campaign / (f"tren_{m.group(1)}" if m else name)
        arm = "train" if m else name.rsplit("_", 1)[0]
        tools = TOOLS.get(arm, DEFAULT_TOOLS)
        a = audit_file(log, ws, set(tools), MODEL)
        a["log"] = name
        out.append(a)
        u = a.get("usage") or {}
        rows.append({"session": name, "arm": arm, "turns": a["num_turns"], "tool_calls": sum(a["tools"].values()),
                     "input_tokens": u.get("input_tokens", 0), "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
                     "cache_read_input_tokens": u.get("cache_read_input_tokens", 0), "output_tokens": u.get("output_tokens", 0),
                     "cost_usd_list_price": a["total_cost_usd"], "clean": a["clean"], "skills": ";".join(a["skills_called"])})  # fmt: skip
    root = str(campaign.resolve())
    text = json.dumps(out, indent=1).replace(root, "<root>")
    (campaign / "_logs" / "audit.json").write_text(text)
    with (campaign / "_logs" / "runs.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    bad = [a["log"] for a in out if not a["clean"]]
    print(f"{len(out)} transcripts, {len(bad)} not clean: {bad}")


def collect(campaign: Path, arm: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=False)
    n = 0
    for ws in _workspaces(campaign, arm):
        for f in sorted((ws / "salida").glob("*.json")):
            shutil.copy(f, dest / f.name)
            n += 1
    print(f"{arm}: {n} answers -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["test", "train", "seed", "audit", "collect"])
    ap.add_argument("campaign", type=Path)
    ap.add_argument("arg", nargs="?")
    ap.add_argument("dest", nargs="?", type=Path)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    c = a.campaign.resolve()
    if a.cmd == "test":
        run_test(c, a.arg, a.jobs)
    elif a.cmd == "train":
        run_train(c, a.arg)
    elif a.cmd == "seed":
        seed(c, a.arg)
    elif a.cmd == "audit":
        audit(c)
    else:
        collect(c, a.arg, a.dest)


if __name__ == "__main__":
    main()
