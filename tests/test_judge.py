from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctb_evals.apex.judge import agreement, build_blind_bundle, load_verdicts, merge, summarize


def _write(p: Path, obj: object) -> Path:
    p.write_text(json.dumps(obj))
    return p


def test_labels_are_mapped_back(tmp_path: Path) -> None:
    v = _write(tmp_path / "v.json", {"T1": {"X": [1, 0], "Y": [1, 1]}})
    assert load_verdicts(v, {"X": "A", "Y": "B"}) == {"T1": {"A": [1, 0], "B": [1, 1]}}
    assert load_verdicts(v, {"X": "B", "Y": "A"}) == {"T1": {"B": [1, 0], "A": [1, 1]}}
    assert load_verdicts(v, {"T1": {"X": "B", "Y": "A"}}) == {"T1": {"B": [1, 0], "A": [1, 1]}}


def test_summary_and_agreement() -> None:
    v1 = {"T1": {"A": [1, 0, 1], "B": [1, 1, 1]}, "T2": {"A": [0, 0], "B": [0, 1]}}
    v2 = {"T1": {"A": [1, 0, 1], "B": [1, 1, 1]}, "T2": {"A": [0, 0], "B": [0, 0]}}
    s = summarize(v1)
    assert (s["A"]["passed"], s["B"]["passed"], s["criteria"], s["tasks"]) == (2, 4, 5, 2)
    assert s["criteria_b_only"] == 2 and s["criteria_a_only"] == 0
    ag = agreement(v1, v2)
    assert (ag["agree"], ag["pairs"]) == (9, 10)
    with pytest.raises(ValueError):
        merge(v1, v1)


def test_blind_bundle_hides_arms(tmp_path: Path) -> None:
    labels = build_blind_bundle("T1", "req", ["c1", "c2"], "gold", {"A": "answer a", "B": "answer b"}, tmp_path, seed=3)
    swapped = build_blind_bundle("T1", "req", ["c1"], "gold", {"A": "a", "B": "b"}, tmp_path / "s", seed=3, swap=True)
    assert labels["X"] == swapped["Y"]
    files = sorted(p.name for p in (tmp_path / "T1").iterdir())
    assert files == ["answer_X.md", "answer_Y.md", "expert_answer.txt", "request.md", "rubric.md"]
    assert "A" not in (tmp_path / "T1" / "rubric.md").read_text().split()
