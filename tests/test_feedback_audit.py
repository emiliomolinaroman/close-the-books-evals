from __future__ import annotations

import json
from pathlib import Path

from ctb_evals.finbalance.feedback import feedback
from ctb_evals.stream_audit import audit_stream

BS = {"assets": {"Cash": 100.0}, "liabilities": {}, "equity": {"Share Capital": 100.0}}
E1 = {"doc_refs": ["D1"], "debit_account": "AR", "credit_account": "Revenue", "amount": 10.0}
E2 = {"doc_refs": ["D2"], "debit_account": "Cash", "credit_account": "AR", "amount": 4.0}
SOL = {"has_inconsistency": False, "inconsistency_codes": [], "entries": [E1, E2], "balance_sheet": BS}
TYPES = {"D1": "customer_invoice", "D2": "payment_advice", "D9": "bank_statement"}


def _ans(entries: list[dict], bs: dict = BS, flag: bool = False) -> dict:
    return {
        "has_inconsistency": flag,
        "inconsistency_codes": [],
        "inconsistency_notes": [],
        "entries": entries,
        "balance_sheet": bs,
    }


def test_feedback_right_answer_says_so() -> None:
    txt = feedback("TR1", SOL, _ans([E2, E1]), TYPES)
    assert "fully right" in txt and "NOT" not in txt
    assert "2 match exactly" in txt and "Balance sheet: correct." in txt


def test_feedback_names_the_extra_document_and_the_wrong_line() -> None:
    over = dict(E2, doc_refs=["D2", "D9"])
    txt = feedback("TR1", SOL, _ans([E1, over], {**BS, "assets": {"Cash": 96.0}}), TYPES)
    assert "NOT fully right" in txt
    assert "1 match exactly" in txt
    # the expected entry is shown with its document types, and the given one is tied to it
    assert "Dr Cash / Cr AR 4.00; documents: D2 (payment_advice)" in txt
    assert "D9 (bank_statement)" in txt and "the cited documents differ" in txt
    assert "assets / Cash: expected 100.0, you gave 96.0" in txt


def test_feedback_inconsistent_packet_and_unparseable() -> None:
    sol = {"has_inconsistency": True, "inconsistency_codes": ["tax_rate_mismatch"], "entries": [], "balance_sheet": {}}
    txt = feedback("TR2", sol, _ans([E1]), TYPES)
    assert "expected ['tax_rate_mismatch']; you gave none" in txt
    assert "No parseable" in feedback("TR3", SOL, None, TYPES)


def _ev(kind: str, **kw: object) -> str:
    return json.dumps({"type": kind, **kw})


def test_audit_flags_outside_paths_tools_and_models(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    ok = [
        _ev("system", subtype="init", tools=["Read", "Write"], claude_code_version="2.1.319", apiKeySource="none"),
        _ev(
            "assistant",
            message={
                "model": "claude-opus-5-5",
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": str(ws / "paquetes" / "H1.txt")}},
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "salida/H1.json"}},
                ],
            },
        ),
        _ev("result", num_turns=3, total_cost_usd=0.5, session_id="s1", permission_denials=[]),
    ]
    a = audit_stream(ok, ws, {"Read", "Write"})
    assert a["clean"] and a["tools"] == {"Read": 1, "Write": 1} and a["paths_outside_workspace"] == []
    assert a["total_cost_usd"] == 0.5 and a["api_key_source"] == "none"

    bad = [
        *ok[:2],
        _ev(
            "assistant",
            message={
                "model": "claude-sonnet-5-5",
                "content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": str(ws / ".." / "keys.json")}},
                ],
            },
        ),
        ok[2],
    ]
    b = audit_stream(bad, ws, {"Read", "Write"})
    assert not b["clean"]
    assert b["disallowed_tools"] == ["Bash"]
    assert b["paths_outside_workspace"] == [str(ws / ".." / "keys.json")]
    assert b["models"] == {"claude-opus-5-5": 1, "claude-sonnet-5-5": 1}
    assert not audit_stream(ok[:2], ws, {"Read", "Write"})["clean"]  # no result event: the run did not finish


def test_teaching_reading_rule_as_preregistered() -> None:
    from ctb_evals.report import teaching_reading

    def g(v: float, lo: float, hi: float) -> dict:
        return {"value": v, "ci95": [lo, hi]}

    assert teaching_reading("S", g(0.50, 0.01, 0.9)) == "closes most of the gap"
    assert teaching_reading("S", g(0.50, -0.01, 0.9)) == "partly"  # interval touches zero
    assert teaching_reading("Ma", g(0.249, 0.1, 0.4)) == "does not close the gap"
    assert teaching_reading("Mb", g(0.30, 0.1, 0.5)) == "partly"
    assert teaching_reading("P", g(0.25, 0.01, 0.5)) == "part of the gap is being told that citations count"
    assert teaching_reading("P", g(0.30, -0.05, 0.6)) == "being told the scoring does not explain the gap"
    assert teaching_reading("P", g(0.09, 0.01, 0.2)) == "being told the scoring does not explain the gap"
    assert teaching_reading("P", g(0.15, 0.05, 0.3)) == "in between the two pre-registered readings"
    assert teaching_reading("E", g(0.9, 0.5, 1.0)) == "replication of 1b"
