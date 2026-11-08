from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctb_evals.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--version"])
    assert "ctb" in capsys.readouterr().out


def test_build_and_score(fb_data: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = fb_data.parent.parent  # <tmp>/finbalance/data -> <tmp>
    work = tmp_path / "w"
    assert main(["finbalance", "build", "--data", str(data), "--out", str(work)]) == 0
    capsys.readouterr()
    key = json.loads((work / "keys" / "public.json").read_text())
    pred = tmp_path / "pred.json"
    pred.write_text(json.dumps(key))
    assert main(["finbalance", "score", "--work", str(work), "--split", "public", "--predictions", str(pred)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["accuracy"] == 1.0
