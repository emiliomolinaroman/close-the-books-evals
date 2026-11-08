"""Build the 16 workspaces of the 2026-11-06 follow-up (run from the repository root, after `ctb reproduce`
or `ctb finbalance build` has written the splits to work/).

    python experiments/2026-11/followup_examples/build_workspaces.py <new_output_dir>

directo4_<k>: the direct-answer instructions and five packets; ejemplos3_<k>: the same plus ejemplos/,
three solved examples drawn by the rule in PREREGISTRATION.md. The draw and the groups are written to
design.json, which is committed. Folder and file names are Spanish, as in the study.
"""

import json
import random
import sys
from pathlib import Path

from ctb_evals.finbalance.render import render_packet
from ctb_evals.io import read_json, read_jsonl

out = Path(sys.argv[1])
if out.exists():
    sys.exit(f"{out} exists; give a new folder")
spec = Path("prompts/direct_answer_instructions.md").read_text(encoding="utf-8")
sample = read_json("experiments/2026-11/sample_40.json")
recs = {r["record_id"]: r for r in read_jsonl("work/finbalance/hidden/hidden_a.jsonl")}
ex = list(read_jsonl("work/finbalance/participant/examples.jsonl"))

rng = random.Random(20261106)
clean = sorted(e["record_id"] for e in ex if not e["solution"]["has_inconsistency"])
inc = sorted(e["record_id"] for e in ex if e["solution"]["has_inconsistency"])
chosen = rng.sample(clean, 2) + rng.sample(inc, 1)
rng.shuffle(chosen)
by_id = {e["record_id"]: e for e in ex}

for arm in ("directo4", "ejemplos3"):
    for g in range(8):
        d = out / f"{arm}_{g}"
        (d / "paquetes").mkdir(parents=True)
        (d / "salida").mkdir()
        (d / "INSTRUCCIONES.md").write_text(spec, encoding="utf-8")
        for rid in sample[g * 5 : (g + 1) * 5]:
            (d / "paquetes" / f"{rid}.txt").write_text(render_packet(recs[rid]), encoding="utf-8")
        if arm == "ejemplos3":
            (d / "ejemplos").mkdir()
            for n, rid in enumerate(chosen, 1):
                e = dict(by_id[rid])
                e["record_id"] = f"EX{n}"
                (d / "ejemplos" / f"EX{n}.txt").write_text(render_packet(e), encoding="utf-8")
                (d / "ejemplos" / f"EX{n}_answer.json").write_text(json.dumps(e["solution"], indent=1), encoding="utf-8")

design = {
    "seed": 20261106,
    "rule": "2 consistent + 1 inconsistent drawn from examples.jsonl, order shuffled; record ids replaced by EX1-EX3",
    "examples": {f"EX{n}": rid for n, rid in enumerate(chosen, 1)},
    "groups": [sample[g * 5 : (g + 1) * 5] for g in range(8)],
}
print(json.dumps(design, indent=1))
