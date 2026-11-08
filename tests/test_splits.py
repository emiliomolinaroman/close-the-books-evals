from __future__ import annotations

import json
from pathlib import Path

from ctb_evals.finbalance.splits import build
from ctb_evals.io import read_jsonl


def test_counts_and_strata(built: Path) -> None:
    m = json.loads((built / "manifest.json").read_text())["splits"]
    assert (m["examples"]["records"], m["examples"]["inconsistent"]) == (30, 6)
    assert (m["public"]["records"], m["public"]["inconsistent"]) == (60, 15)
    assert m["hidden_a"]["records"] == 25
    assert (m["hidden_b"]["records"], m["hidden_b"]["inconsistent"]) == (150, 30)
    levels = {r["difficulty_level"] for r in read_jsonl(built / "participant" / "public.jsonl")}
    assert levels == {1, 2, 3, 4, 5}


def test_no_overlap_and_neutral_ids(built: Path) -> None:
    ex = {r["record_id"] for r in read_jsonl(built / "participant" / "examples.jsonl")}
    src = json.loads((built / "keys" / "public_source_ids.json").read_text())
    assert not ex & set(src)
    for split, prefix in (("public", "P"), ("hidden_a", "H"), ("hidden_b", "Q")):
        where = "participant" if split == "public" else "hidden"
        ids = [r["record_id"] for r in read_jsonl(built / where / f"{split}.jsonl")]
        assert all(i.startswith(prefix) and "NEG" not in i for i in ids)
        assert len(set(ids)) == len(ids)


def test_nothing_secret_reaches_participants(built: Path) -> None:
    for f in ("examples.jsonl", "public.jsonl"):
        for r in read_jsonl(built / "participant" / f):
            text = json.dumps({k: v for k, v in r.items() if k != "solution"})
            assert "expected_" not in text
            assert "generator_secret" not in text
            assert all("role" not in d for d in r["documents"])
    assert not list((built / "participant").glob("*hidden*"))


def test_build_is_deterministic(fb_data: Path, tmp_path: Path) -> None:
    a = build(fb_data, tmp_path / "a")["splits"]
    b = build(fb_data, tmp_path / "b")["splits"]
    assert {k: v["sha256"] for k, v in a.items()} == {k: v["sha256"] for k, v in b.items()}
