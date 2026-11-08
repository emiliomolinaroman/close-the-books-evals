from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctb_evals.finbalance.scoring import score_record
from ctb_evals.study import bank_statement_convention, examples_followup

BS = {"assets": {"Cash": 100.0}, "liabilities": {}, "equity": {"Share Capital": 100.0}}
E1 = {"doc_refs": ["D1"], "debit_account": "AR", "credit_account": "Revenue", "amount": 10.0}
E2 = {"doc_refs": ["D2"], "debit_account": "Cash", "credit_account": "AR", "amount": 4.0}


def _key(entries: list[dict]) -> dict:
    return {"has_inconsistency": False, "inconsistency_codes": [], "entries": entries, "balance_sheet": BS}


KEYS = {
    "P1": _key([E1, E2]),
    "P2": _key([E1, E2]),
    "P3": {"has_inconsistency": True, "inconsistency_codes": ["tax_rate_mismatch"], "entries": [], "balance_sheet": {}},
}
TYPES = {r: {"D1": "customer_invoice", "D2": "payment_advice", "D9": "bank_statement"} for r in KEYS}
FLAG = {"has_inconsistency": True, "inconsistency_codes": ["tax_rate_mismatch"], "inconsistency_notes": ["x"],
        "entries": [], "balance_sheet": {"assets": {}, "liabilities": {}, "equity": {}}}  # fmt: skip


def _answer(*entries: dict) -> dict:
    return {"has_inconsistency": False, "inconsistency_codes": [], "inconsistency_notes": [],
            "entries": list(entries), "balance_sheet": BS}  # fmt: skip


def _bank(e: dict) -> dict:  # the key's document plus the bank statement
    return dict(e, doc_refs=[*e["doc_refs"], "D9"])


def _write(d: Path, answers: dict[str, dict]) -> None:
    d.mkdir(parents=True)
    for rid, a in answers.items():
        (d / f"{rid}.json").write_text(json.dumps(a))


def test_examples_followup_on_a_known_case(tmp_path: Path) -> None:
    """Control: 1 of 4 entries exact; examples: 3 of 4; code: 4 of 4.

    In any resample with k copies of P1 out of 2, control F1 is k/4 and examples F1 is (k + 2)/4, so a
    paired bootstrap of the difference is exactly 0.5 every time, and the share of the gap closed is
    0.5 / (1 - k/4): 0.5, 2/3 or 1. An unpaired bootstrap or a share without the control in the
    denominator would give other numbers.
    """
    key_file = tmp_path / "keys.json"
    key_file.write_text(json.dumps(KEYS))
    ddir = tmp_path / "direct"
    ctl = {"P1": _answer(E1, _bank(E2)), "P2": _answer(_bank(E1), _bank(E2)), "P3": FLAG}
    ex = {"P1": _answer(E1, E2), "P2": _answer(E1, _bank(E2)), "P3": FLAG}
    exact = {"P1": _answer(E1, E2), "P2": _answer(E1, E2), "P3": FLAG}
    for name, answers in (("t1", ctl), ("ctl", ctl), ("ex", ex)):
        _write(ddir / name, answers)
    team_preds = {"T1": exact, "T2": exact}
    team_records = {t: {r: score_record(r, KEYS[r], p[r]).as_dict() for r in KEYS} for t, p in team_preds.items()}
    cfg = {"earlier_trials": ["t1"], "control": "ctl", "examples": "ex", "bootstrap": {"reps": 400, "seed": 7}}
    out = tmp_path / "records"
    out.mkdir()
    res = examples_followup(cfg, ddir, key_file, list(KEYS), KEYS, TYPES, team_records, team_preds, out)

    assert res["n"] == 3 and res["n_clean"] == 2
    c, x = res["arms"]["ctl"], res["arms"]["ex"]
    assert c["entry_f1_strict"] == 0.25 and x["entry_f1_strict"] == 0.75
    assert c["entry_f1_tolerant"] == 1.0 and x["entry_f1_tolerant"] == 1.0
    assert c["citations"]["over"] == 3 and c["citations"]["extra_types"] == {"bank_statement": 3}
    assert res["code_teams"]["entry_f1_strict"] == 1.0
    assert res["entry_f1_strict_diff"]["diff"] == 0.5
    assert res["entry_f1_strict_diff"]["ci95"] == [0.5, 0.5]  # paired: the same packets in both arms
    assert res["gap_closed"]["value"] == pytest.approx(2 / 3)
    assert res["gap_closed"]["ci95"] == [0.5, 1.0]
    assert res["entry_f1_tolerant_diff"]["diff"] == 0.0
    assert res["fully_right_paired"]["diff"] == 0.0  # citations do not enter "fully right"
    assert res["vs_earlier_trials"]["gap_closed"] == pytest.approx(2 / 3)
    assert c["entries_missing_a_key_document"] == 0 and res["fewer_entries_missing_a_key_document"]["diff"] == 0
    assert sorted(p.name for p in out.iterdir()) == ["finbalance_direct_ctl.jsonl", "finbalance_direct_ex.jsonl"]


def test_missing_documents_count_partial_citations(tmp_path: Path) -> None:
    """An entry that adds one document and leaves out another still misses one of the key's documents."""
    two = dict(E1, doc_refs=["D1", "D2"])
    keys = {"P1": _key([two])}
    key_file = tmp_path / "keys.json"
    key_file.write_text(json.dumps(keys))
    ddir = tmp_path / "direct"
    _write(ddir / "ctl", {"P1": _answer(dict(E1, doc_refs=["D1", "D9"]))})  # partial
    _write(ddir / "ex", {"P1": _answer(dict(E1, doc_refs=["D1"]))})  # under
    exact = {"P1": _answer(two)}
    team_records = {"T1": {"P1": score_record("P1", keys["P1"], exact["P1"]).as_dict()}}
    cfg = {"earlier_trials": [], "control": "ctl", "examples": "ex", "bootstrap": {"reps": 50, "seed": 7}}
    out = tmp_path / "records"
    out.mkdir()
    res = examples_followup(cfg, ddir, key_file, ["P1"], keys, TYPES, team_records, {"T1": exact}, out)
    assert res["arms"]["ctl"]["citations"]["partial"] == 1 and res["arms"]["ex"]["citations"]["under"] == 1
    assert res["arms"]["ctl"]["entries_missing_a_key_document"] == 1
    assert res["arms"]["ex"]["entries_missing_a_key_document"] == 1
    assert res["code_teams"]["entries_missing_a_key_document"] == {"T1": 0}


def test_bank_statement_convention(tmp_path: Path) -> None:
    rec = {
        "documents": [{"doc_id": "D1", "doc_type": "customer_invoice"}, {"doc_id": "D9", "doc_type": "bank_statement"}],
        "expected_entries": [{"doc_refs": ["D1"]}, {"doc_refs": ["D1", "D9"]}],
    }
    (tmp_path / "main").mkdir()
    (tmp_path / "main" / "records.jsonl").write_text(json.dumps(rec) + "\n" + json.dumps(rec) + "\n")
    c = bank_statement_convention(tmp_path)
    assert c["files"] == ["main/records.jsonl"]
    assert (c["records"], c["records_with_bank_statement"], c["key_entries"]) == (2, 2, 4)
    assert c["key_entries_citing_bank_statement"] == 2
