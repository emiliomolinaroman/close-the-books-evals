"""Build the folders of the 2026-11-08 follow-up (run from the repository root, after `ctb reproduce`
or `ctb finbalance build` has written the splits to work/).

    python experiments/2026-11/followup_teaching/build_workspaces.py <new_campaign_dir>

Test folders, 8 groups of 5 packets of sample_40 each (the groups of the 2026-11-06 follow-up):
  control_<g>    the direct-answer instructions and five packets
  puntuacion_<g> the same plus PUNTUACION.md, the scoring section the code teams' brief had
  ejemplos3_<g>  the same plus ejemplos/, the three solved examples of the 2026-11-06 follow-up
  skill_<g>      the same as control plus .claude/skills/journal-entry-prep/ (Anthropic's skill)
  memoria_a_<g>, memoria_b_<g>  the same as control; memoria/ is copied in after training
Training (memory chains), outside any test folder:
  tren_a/, tren_b/   INSTRUCCIONES.md and an empty memoria/; the harness feeds one packet at a time
  _staging/          training packets, their answers and document types (never inside a workspace)
The draw and the groups are written to design.json next to this script.
With PILOT=1 it builds a small pilot instead: one group of two packets from the examples split (not
used anywhere else in the follow-up) and chains of two training packets; design.json is not written.
"""

import json
import os
import random
import shutil
import sys
from pathlib import Path

from ctb_evals.finbalance.render import render_packet
from ctb_evals.io import read_json, read_jsonl

HERE = Path(__file__).parent
out = Path(sys.argv[1])
if out.exists():
    sys.exit(f"{out} exists; give a new folder")
spec = Path("prompts/direct_answer_instructions.md").read_text(encoding="utf-8")
prev = read_json("experiments/2026-11/followup_examples/design.json")
groups = prev["groups"]
recs = {r["record_id"]: r for r in read_jsonl("work/finbalance/hidden/hidden_a.jsonl")}
ex = {e["record_id"]: e for e in read_jsonl("work/finbalance/participant/examples.jsonl")}
skill_src = Path("prompts/skills/journal-entry-prep/SKILL.md")
task = Path("prompts/finbalance_task_en.md").read_text(encoding="utf-8")
scoring = task[task.index("## Scoring") : task.index("- The HIDDEN set")].rstrip() + "\n"
PILOT = os.environ.get("PILOT") == "1"

# memory chains: two disjoint draws of 6 consistent + 2 inconsistent packets from the examples split,
# leaving out the three solved examples of the ejemplos3 arm; order shuffled within each chain
used = set(prev["examples"].values())
clean = sorted(r for r, e in ex.items() if r not in used and not e["solution"]["has_inconsistency"])
inc = sorted(r for r, e in ex.items() if r not in used and e["solution"]["has_inconsistency"])
chains: dict[str, list[str]] = {}
for name, seed in (("a", 20261108), ("b", 20261109)):
    rng = random.Random(seed)
    pick = rng.sample(clean, 6) + rng.sample(inc, 2)
    rng.shuffle(pick)
    chains[name] = pick
    clean = [r for r in clean if r not in pick]
    inc = [r for r in inc if r not in pick]
if PILOT:  # two unused consistent packets as the test group, and two training packets per chain
    recs = {r: ex[r] for r in clean[:2]}
    groups = [clean[:2]]
    chains = {c: ids[:2] for c, ids in chains.items()}


def base(d: Path, g: int) -> None:
    (d / "paquetes").mkdir(parents=True)
    (d / "salida").mkdir()
    (d / "INSTRUCCIONES.md").write_text(spec, encoding="utf-8")
    for rid in groups[g]:
        (d / "paquetes" / f"{rid}.txt").write_text(render_packet(recs[rid]), encoding="utf-8")


for g in range(len(groups)):
    base(out / f"control_{g}", g)
    d = out / f"puntuacion_{g}"
    base(d, g)
    (d / "PUNTUACION.md").write_text(scoring, encoding="utf-8")
    d = out / f"ejemplos3_{g}"
    base(d, g)
    (d / "ejemplos").mkdir()
    for n, rid in sorted(prev["examples"].items()):
        e = dict(ex[rid], record_id=n)
        (d / "ejemplos" / f"{n}.txt").write_text(render_packet(e), encoding="utf-8")
        (d / "ejemplos" / f"{n}_answer.json").write_text(json.dumps(e["solution"], indent=1), encoding="utf-8")
    d = out / f"skill_{g}"
    base(d, g)
    (d / ".claude" / "skills" / "journal-entry-prep").mkdir(parents=True)
    shutil.copy(skill_src, d / ".claude" / "skills" / "journal-entry-prep" / "SKILL.md")
    for c in chains:
        base(out / f"memoria_{c}_{g}", g)

stage = out / "_staging"
for c, ids in chains.items():
    t = out / f"tren_{c}"
    for sub in ("memoria", "paquete_actual", "salida", "revision"):
        (t / sub).mkdir(parents=True)
    (t / "INSTRUCCIONES.md").write_text(spec, encoding="utf-8")
    for k, rid in enumerate(ids, 1):
        tr = f"TR{k}"
        e = dict(ex[rid], record_id=tr)
        s = stage / c
        s.mkdir(parents=True, exist_ok=True)
        (s / f"{tr}.txt").write_text(render_packet(e), encoding="utf-8")
        (s / f"{tr}_solution.json").write_text(json.dumps(e["solution"], indent=1), encoding="utf-8")
        types = {str(doc["doc_id"]): doc["doc_type"] for doc in e["documents"]}
        (s / f"{tr}_doc_types.json").write_text(json.dumps(types, indent=1), encoding="utf-8")

design = {
    "groups": groups,
    "examples": prev["examples"],
    "memory_chains": {
        c: {"seed": s, "packets": {f"TR{k}": rid for k, rid in enumerate(chains[c], 1)}}
        for c, s in (("a", 20261108), ("b", 20261109))
    },
    "rule": "per chain 6 consistent + 2 inconsistent from examples.jsonl minus the three ejemplos3 packets, "
    "chain b drawn from what chain a left, order shuffled; record ids replaced by TR1-TR8",
}
if not PILOT:
    (HERE / "design.json").write_text(json.dumps(design, indent=1) + "\n", encoding="utf-8")
print(json.dumps(design, indent=1))
