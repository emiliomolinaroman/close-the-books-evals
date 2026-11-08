from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from ctb_evals.finbalance.evaluate import evaluate_program
from ctb_evals.sandbox import run_program


def _prog(tmp_path: Path, body: str) -> Path:
    d = tmp_path / "p"
    d.mkdir(exist_ok=True)
    p = d / "run.py"
    p.write_text("import json, sys\n" + body)
    return p


@pytest.fixture
def records(tmp_path: Path) -> Path:
    f = tmp_path / "records.jsonl"
    f.write_text(json.dumps({"record_id": "H000"}) + "\n")
    return f


def test_happy_path(tmp_path: Path, records: Path) -> None:
    p = _prog(tmp_path, "json.dump({'H000': {'ok': 1}}, open(sys.argv[2], 'w'))\n")
    r = run_program(p, records)
    assert r.predictions == {"H000": {"ok": 1}} and r.error == "" and not r.timed_out


def test_network_is_blocked(tmp_path: Path, records: Path) -> None:
    p = _prog(
        tmp_path,
        "import socket\ntry:\n    socket.create_connection(('example.invalid', 80))\n"
        "    r = 'open'\nexcept OSError as e:\n    r = str(e)\njson.dump({'H000': r}, open(sys.argv[2], 'w'))\n",
    )
    assert "network disabled" in run_program(p, records).predictions["H000"]


def test_api_keys_are_not_inherited(tmp_path: Path, records: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = _prog(tmp_path, "import os\njson.dump({'H000': os.environ.get('ANTHROPIC_API_KEY')}, open(sys.argv[2], 'w'))\n")
    assert run_program(p, records).predictions == {"H000": None}


def test_timeout_and_crash(tmp_path: Path, records: Path) -> None:
    slow = _prog(tmp_path, "import time\ntime.sleep(30)\n")
    r = run_program(slow, records, timeout=1)
    assert r.timed_out and r.predictions == {} and r.error == "timeout"
    crash = _prog(tmp_path, "raise SystemExit('boom')\n")
    r = run_program(crash, records)
    assert r.returncode == 1 and "boom" in r.error


def test_writes_next_to_the_program_are_reported(tmp_path: Path, records: Path) -> None:
    p = _prog(
        tmp_path,
        "import pathlib\npathlib.Path(__file__).with_name('cache.json').write_text('{}')\n"
        "json.dump({}, open(sys.argv[2], 'w'))\n",
    )
    assert run_program(p, records).wrote_to_program_dir == ["cache.json"]


def test_end_to_end_oracle_scores_perfectly(oracle_program: Path, built: Path) -> None:
    res = evaluate_program(oracle_program, built / "hidden" / "hidden_a.jsonl", built / "keys" / "hidden_a.json")
    assert res["summary"]["accuracy"] == 1.0 and res["summary"]["missing"] == 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_child_processes_die_on_timeout(tmp_path: Path, records: Path) -> None:
    marker = tmp_path / "survived"
    p = _prog(
        tmp_path,
        f"import subprocess, time\nsubprocess.Popen([sys.executable, '-c', "
        f"\"import time; time.sleep(3); open({str(marker)!r}, 'w')\"])\ntime.sleep(30)\n",
    )
    run_program(p, records, timeout=1)
    import time

    time.sleep(3.5)
    assert not marker.exists()
