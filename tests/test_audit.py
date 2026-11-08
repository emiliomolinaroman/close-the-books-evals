from __future__ import annotations

import json
from pathlib import Path

from ctb_evals.audit import audit_dir, scratch_collisions


def _transcript(path: Path, prompt: str, calls: list[tuple[str, dict]]) -> None:
    lines = [{"type": "user", "message": {"role": "user", "content": prompt}}]
    for i, (name, inp) in enumerate(calls):
        lines.append(
            {
                "type": "assistant",
                "timestamp": f"2026-11-02T07:0{i}:00Z",
                "message": {
                    "id": f"m{i}",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "content": [{"type": "tool_use", "name": name, "input": inp}],
                },
            }
        )
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def test_breaches_and_collisions(tmp_path: Path) -> None:
    root = "/exp"
    _transcript(
        tmp_path / "a.output",
        f"Your folder is {root}/r7/fb_A1 .",
        [
            ("Read", {"file_path": f"{root}/r7/fb_A1/data/x.jsonl"}),
            ("Bash", {"command": "cat > /scratch/ev.py <<EOF\nEOF"}),
            ("Bash", {"command": f"cat {root}/r7/_keys/hidden.json"}),
        ],
    )
    _transcript(
        tmp_path / "b.output",
        f"answering directly. Folder: {root}/r9/direct_0 .",
        [
            ("Read", {"file_path": f"{root}/r9/direct_0/packets/H1.txt"}),
            ("Bash", {"command": "python3 /scratch/ev.py"}),
        ],
    )
    rep = audit_dir(tmp_path, root, shared_dirs=("/scratch",))
    by = {r["workspace"]: r for r in rep}
    assert by["r7/fb_A1"]["breaches"] == [f"Bash: {root}/r7/_keys/hidden.json"]
    assert "tool not allowed in direct arm: Bash" in by["r9/direct_0"]["breaches"]
    assert by["r7/fb_A1"]["usage"] == {"input_tokens": 30, "output_tokens": 15}
    assert by["r7/fb_A1"]["turns"] == 3 and by["r7/fb_A1"]["minutes"] == 2.0
    assert scratch_collisions(rep) == {"/scratch/ev.py": ["r7/fb_A1", "r9/direct_0"]}
