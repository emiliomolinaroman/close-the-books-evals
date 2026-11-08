from __future__ import annotations

import copy
import json
from pathlib import Path

from ctb_evals.finbalance.scoring import LEGACY_NAMES, aggregate, balance_sheet_equal, matched_entries, score_records

ROOT = Path(__file__).resolve().parents[1]

CLEAN = {
    "has_inconsistency": False,
    "inconsistency_codes": [],
    "entries": [
        {"doc_refs": ["D1"], "debit_account": "AR", "credit_account": "Revenue", "amount": 100.0},
        {"doc_refs": ["D2", "D1"], "debit_account": "Cash", "credit_account": "AR", "amount": 40.0},
    ],
    "balance_sheet": {"assets": {"Cash": 40.0, "AR": 60.0, "Prepaid": 0.0}, "liabilities": {}, "equity": {"RE": 100.0}},
}
NEG = {
    "has_inconsistency": True,
    "inconsistency_codes": ["bank_closing_mismatch"],
    "entries": [],
    "balance_sheet": {"assets": {}, "liabilities": {}, "equity": {}},
}


def test_balance_sheet_rules() -> None:
    bs = CLEAN["balance_sheet"]
    assert balance_sheet_equal(
        bs, {"assets": {"Cash": 40.004, "AR": 60.0}, "equity": {"RE": 100.0}}
    )  # zero line, tolerance
    assert not balance_sheet_equal(bs, {"assets": {"Cash": 40.0, "AR": 60.0, "Extra": 1.0}, "equity": {"RE": 100.0}})
    assert not balance_sheet_equal(bs, {"assets": {"Cash": 40.02, "AR": 60.0}, "equity": {"RE": 100.0}})
    assert not balance_sheet_equal(bs, None)
    assert not balance_sheet_equal(bs, {"assets": {"Cash": "forty"}})


def test_entry_matching_is_a_multiset() -> None:
    exp = CLEAN["entries"]
    dup = [exp[0], exp[0]]
    assert matched_entries(exp, dup, False) == 1
    swapped_refs = [dict(exp[1], doc_refs=["D1", "D2"])]
    assert matched_entries(exp, swapped_refs, True) == 1  # order of doc_refs does not matter
    assert matched_entries(exp, [dict(exp[1], doc_refs=["D2"])], True) == 0
    assert matched_entries(exp, [{"amount": "x"}], False) == 0


def test_record_outcomes() -> None:
    keys = {"c": CLEAN, "n": NEG}
    perfect = score_records({"c": CLEAN, "n": NEG}, keys)
    assert all(o.correct for o in perfect)
    wrong_code = score_records({"c": CLEAN, "n": dict(NEG, inconsistency_codes=["x"])}, keys)
    assert [o.correct for o in wrong_code] == [True, False]
    false_alarm = score_records({"c": dict(CLEAN, has_inconsistency=True), "n": NEG}, keys)
    s = aggregate(false_alarm)
    assert s["false_alarms"] == 1 and s["accuracy"] == 0.5
    missing = aggregate(score_records({}, keys))
    assert missing["missing"] == 2 and missing["accuracy"] == 0.0


def _legacy_score():
    path = ROOT / "experiments/2026-11/original_scripts/finbalance/score.py"
    src = path.read_text().split("SITE=")[0]
    ns: dict = {"__file__": str(path)}
    exec(src, ns)
    return ns["score"]


def test_matches_the_scorer_used_in_the_experiments() -> None:
    legacy = _legacy_score()
    keys = {f"c{i}": copy.deepcopy(CLEAN) for i in range(6)} | {f"n{i}": copy.deepcopy(NEG) for i in range(4)}
    preds = json.loads(json.dumps(keys))
    preds["c1"]["balance_sheet"]["assets"]["Cash"] = 41.0
    preds["c2"]["entries"] = preds["c2"]["entries"][:1]
    preds["c3"]["entries"][0]["doc_refs"] = ["D9"]
    preds["c4"]["has_inconsistency"] = True
    del preds["c5"]
    preds["n1"]["inconsistency_codes"] = ["other"]
    preds["n2"]["has_inconsistency"] = False
    old = legacy(preds, keys)
    new = aggregate(score_records(preds, keys))
    for old_name, new_name in LEGACY_NAMES.items():
        assert old[old_name] == new[new_name], old_name
