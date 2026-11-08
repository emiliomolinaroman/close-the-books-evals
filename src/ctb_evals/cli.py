"""``ctb``: command-line entry point. Run ``ctb --help`` or ``ctb <command> --help``."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import __version__


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def cmd_fetch(a: argparse.Namespace) -> int:
    from .data import fetch, verify

    names = ["finbalance", "apex"] if a.dataset == "all" else [a.dataset]
    for n in names:
        print(f"fetching {n} ...", file=sys.stderr)
        fetch(n, a.data)
        bad = verify(n, a.data)
        print(f"{n}: {'OK' if not bad else 'CHECKSUM MISMATCH: ' + ', '.join(bad)}", file=sys.stderr)
        if bad:
            return 1
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    from .data import verify

    rc = 0
    for n in ("finbalance", "apex"):
        bad = verify(n, a.data)
        print(f"{n}: {'OK' if not bad else 'missing or changed: ' + ', '.join(bad[:5])}")
        rc |= bool(bad)
    return rc


def cmd_fb_build(a: argparse.Namespace) -> int:
    from .finbalance.splits import build

    _print(build(Path(a.data) / "finbalance" / "data", a.out)["splits"])
    return 0


def cmd_fb_score(a: argparse.Namespace) -> int:
    from .finbalance import evaluate

    work = Path(a.work)
    key = work / "keys" / f"{a.split}.json"
    if a.program:
        split_file = work / ("participant" if a.split == "public" else "hidden") / f"{a.split}.jsonl"
        res = evaluate.evaluate_program(a.program, split_file, key, timeout=a.timeout)
    elif a.predictions:
        idmap = work / "keys" / f"{a.split}_source_ids.json" if a.legacy_ids else None
        res = evaluate.evaluate_predictions(a.predictions, key, idmap)
    else:
        sample = json.loads(Path(a.sample).read_text()) if a.sample else None
        res = evaluate.evaluate_answer_dirs(a.answer_dir, key, sample)
    if a.records:
        from .io import write_jsonl

        write_jsonl(a.records, res["records"])
    _print({k: v for k, v in res.items() if k != "records"})
    return 0


def cmd_apex_build(a: argparse.Namespace) -> int:
    from .apex.workspaces import build
    from .data import extract_apex_world, manifest

    root = Path(a.data) / manifest()["apex"]["dest"]
    world = extract_apex_world(a.data, Path(a.out) / "_world")
    for w in build(root, world, a.task, a.out, scaffold=a.scaffold):
        print(w)
    return 0


def cmd_apex_summarize(a: argparse.Namespace) -> int:
    from .apex.judge import agreement, load_verdicts, merge, summarize
    from .io import read_json

    def load(pairs: list[str]) -> dict[str, dict[str, list[int]]]:
        return merge(*[load_verdicts(v, read_json(lab)) for v, lab in (p.split(":", 1) for p in pairs)])

    v1 = load(a.judge)
    out = {"judge": summarize(v1)}
    if a.second:
        v2 = load(a.second)
        out["second_judge"] = summarize(v2)
        out["agreement"] = agreement(v1, v2)
    _print(out)
    return 0


def cmd_audit(a: argparse.Namespace) -> int:
    from .audit import audit_dir, scratch_collisions
    from .io import write_json

    rep = audit_dir(a.transcripts, a.root, a.pattern, tuple(a.shared or ()))
    for r in rep:
        print("OK " if not r["breaches"] else "!! ", r["workspace"], r["tool_calls"], r["breaches"][:3])
    collisions = scratch_collisions(rep)
    if a.out:
        write_json(a.out, {"transcripts": rep, "scratch_collisions": collisions})
    if a.csv:
        from .study import runs_table

        rows = runs_table(rep)
        with open(a.csv, "w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
            wr.writeheader()
            wr.writerows(rows)
    breaches = sum(1 for r in rep if r["breaches"])
    print(f"{len(rep)} transcripts, {breaches} with breaches, {len(collisions)} shared scratch paths", file=sys.stderr)
    return 1 if breaches else 0


def cmd_reproduce(a: argparse.Namespace) -> int:
    from .io import read_json
    from .report import render
    from .study import reproduce

    reproduce(a.repo, a.data, a.work)
    md = render(read_json(Path(a.repo, "results", "summary.json")))  # render what was committed, keys sorted
    Path(a.repo, "results", "RESULTS.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    from .io import read_json
    from .report import render, update_readme

    summary = read_json(a.summary)
    if a.readme:
        p = Path(a.readme)
        p.write_text(update_readme(p.read_text(encoding="utf-8"), summary), encoding="utf-8")
        return 0
    sys.stdout.write(render(summary))
    return 0


def cmd_run_team(a: argparse.Namespace) -> int:
    from .agents.runner import TeamConfig, run

    cfg = TeamConfig(
        Path(a.workspace),
        Path(a.prompt).read_text(encoding="utf-8"),
        model=a.model,
        direct=a.direct,
        max_turns=a.max_turns,
        max_budget_usd=a.max_budget_usd,
    )
    _print(run(cfg))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ctb", description=__doc__)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="clone FinBalance and/or APEX at their pinned revisions")
    s.add_argument("dataset", choices=["finbalance", "apex", "all"], nargs="?", default="all")
    s.add_argument("--data", default="data")
    s.set_defaults(fn=cmd_fetch)

    s = sub.add_parser("verify", help="check dataset checksums against the manifest")
    s.add_argument("--data", default="data")
    s.set_defaults(fn=cmd_verify)

    fb = sub.add_parser("finbalance", help="FinBalance track").add_subparsers(dest="sub", required=True)
    s = fb.add_parser("build", help="build examples/public/hidden splits and answer keys")
    s.add_argument("--data", default="data")
    s.add_argument("--out", default="work/finbalance")
    s.set_defaults(fn=cmd_fb_build)
    s = fb.add_parser("score", help="score a run.py, a predictions file, or per-packet answers")
    s.add_argument("--work", default="work/finbalance")
    s.add_argument("--split", choices=["public", "hidden_a", "hidden_b"], required=True)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--program", help="run.py to execute on the split (no network)")
    g.add_argument("--predictions", help="JSON {record_id: answer}")
    g.add_argument("--answer-dir", nargs="+", help="directories with one <record_id>.json each")
    s.add_argument("--sample", help="JSON list of record ids to restrict scoring to")
    s.add_argument("--legacy-ids", action="store_true", help="predictions use original FinBalance ids")
    s.add_argument("--timeout", type=float, default=600)
    s.add_argument("--records", help="write per-record outcomes (JSONL) here")
    s.set_defaults(fn=cmd_fb_score)

    ap = sub.add_parser("apex", help="APEX-Accounting track").add_subparsers(dest="sub", required=True)
    s = ap.add_parser("build", help="build team workspaces")
    s.add_argument("--data", default="data")
    s.add_argument("--out", default="work/apex")
    s.add_argument("--task", default="prompts/apex_task_en.md")
    s.add_argument("--scaffold", help="scaffold folder for arm B (e.g. scaffold/en)")
    s.set_defaults(fn=cmd_apex_build)
    s = ap.add_parser("summarize", help="aggregate blind verdicts: verdicts.json:labels.json ...")
    s.add_argument("--judge", nargs="+", required=True)
    s.add_argument("--second", nargs="+")
    s.set_defaults(fn=cmd_apex_summarize)

    s = sub.add_parser("audit", help="audit agent transcripts for isolation breaches; extract usage")
    s.add_argument("transcripts")
    s.add_argument("root", help="experiment root; each transcript's workspace must be under it")
    s.add_argument("--pattern", default="*.output")
    s.add_argument("--shared", nargs="*", help="scratch dirs visible to several agents (reported, not breaches)")
    s.add_argument("--out")
    s.add_argument("--csv")
    s.set_defaults(fn=cmd_audit)

    s = sub.add_parser("reproduce", help="recompute every result of the Nov 2026 study")
    s.add_argument("--repo", default=".")
    s.add_argument("--data", default="data")
    s.add_argument("--work", default="work")
    s.set_defaults(fn=cmd_reproduce)

    s = sub.add_parser("report", help="render results/summary.json as Markdown")
    s.add_argument("summary", nargs="?", default="results/summary.json")
    s.add_argument("--readme", help="rewrite the generated results block of this README instead of printing")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("run-team", help="run one agent team with the Claude Agent SDK (extra: agents)")
    s.add_argument("workspace")
    s.add_argument("--prompt", required=True, help="file with the team's brief")
    s.add_argument("--model")
    s.add_argument("--direct", action="store_true", help="direct-answer arm: no code execution")
    s.add_argument("--max-turns", type=int, default=200)
    s.add_argument("--max-budget-usd", type=float)
    s.set_defaults(fn=cmd_run_team)
    return p


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
