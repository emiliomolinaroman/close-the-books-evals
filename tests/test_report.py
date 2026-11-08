from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ctb_evals.report import README_END, README_START, headline, render

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "results" / "summary.json"


@pytest.fixture
def summary() -> dict:
    return json.loads(SUMMARY.read_text())


def test_results_md_is_current(summary: dict) -> None:
    assert (ROOT / "results" / "RESULTS.md").read_text() == render(summary)


def test_readme_block_is_current(summary: dict) -> None:
    readme = (ROOT / "README.md").read_text()
    block = readme[readme.index(README_START) + len(README_START) : readme.index(README_END)]
    assert block.strip() == headline(summary).strip(), "run: ctb report --readme README.md"


@pytest.mark.skipif(not os.environ.get("CTB_DATA"), reason="set CTB_DATA to a folder with `ctb fetch finbalance`")
def test_reproduce_matches_committed(tmp_path: Path, summary: dict) -> None:
    import shutil

    from ctb_evals.study import reproduce

    repo = tmp_path / "repo"
    for d in ("experiments", "team_outputs", "results"):
        shutil.copytree(ROOT / d, repo / d)
    fresh = reproduce(repo, os.environ["CTB_DATA"], tmp_path / "work")
    assert json.loads(json.dumps(fresh)) == summary
