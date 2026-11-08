from __future__ import annotations

from ctb_evals.finbalance.citations import aggregate_citations, classify_citations
from ctb_evals.finbalance.scoring import matched_entries

EXP = [
    {"doc_refs": ["D1"], "debit_account": "AR", "credit_account": "Revenue", "amount": 100.0},
    {"doc_refs": ["D2", "D3"], "debit_account": "Cash", "credit_account": "AR", "amount": 40.0},
    {"doc_refs": ["D4"], "debit_account": "Rent", "credit_account": "Cash", "amount": 10.0},
    {"doc_refs": ["D5", "D6"], "debit_account": "Supplies", "credit_account": "AP", "amount": 5.0},
]
TYPES = {
    "D1": "customer_invoice",
    "D2": "payment_advice",
    "D3": "remittance_note",
    "D4": "lease_schedule",
    "D5": "vendor_invoice",
    "D6": "delivery_note",
    "D9": "bank_statement",
}


def test_each_class_and_document_types() -> None:
    pred = [
        dict(EXP[0], doc_refs=["D1", "D9"]),  # cites the key's document plus the bank statement
        dict(EXP[1], doc_refs=["D2"]),  # cites one of the two documents the key cites
        dict(EXP[2], doc_refs=["D9"]),  # no document in common
        dict(EXP[3], doc_refs=["D5", "D9"]),  # overlaps, neither contains the other
    ]
    c = classify_citations(EXP, pred, TYPES)
    assert {k: c[k] for k in ("exact", "over", "under", "partial", "disjoint", "missing")} == {
        "exact": 0,
        "over": 1,
        "under": 1,
        "partial": 1,
        "disjoint": 1,
        "missing": 0,
    }
    assert c["extra_types"] == {"bank_statement": 1}
    assert c["lacking_types"] == {"remittance_note": 1}
    assert c["tp_tolerant"] == 1  # exact + over
    assert (c["n_expected"], c["n_predicted"]) == (4, 4)


def test_exact_pairs_first_and_counts_agree_with_the_scorer() -> None:
    exp = [
        {"doc_refs": ["D1"], "debit_account": "AR", "credit_account": "Revenue", "amount": 100.0},
        {"doc_refs": ["D2"], "debit_account": "AR", "credit_account": "Revenue", "amount": 100.0},
    ]
    # the second prediction matches the first key entry exactly; the first is the second entry plus a document
    pred = [dict(exp[1], doc_refs=["D2", "D9"]), dict(exp[0])]
    c = classify_citations(exp, pred, TYPES)
    assert (c["exact"], c["over"]) == (1, 1)
    mixed = [*pred, {"amount": "x"}, "not an entry", dict(EXP[1], doc_refs=["D3", "D2"]), dict(EXP[2], amount=11.0)]
    c = classify_citations([*exp, EXP[1], EXP[2]], mixed, TYPES)
    lax_pairs = sum(c[k] for k in ("exact", "over", "under", "partial", "disjoint", "missing"))
    assert c["exact"] == matched_entries([*exp, EXP[1], EXP[2]], mixed, True)
    assert lax_pairs == matched_entries([*exp, EXP[1], EXP[2]], mixed, False)
    assert c["n_predicted"] == 5  # dicts only, as in the scorer


def test_missing_refs_and_unknown_types() -> None:
    c = classify_citations(EXP[:1], [dict(EXP[0], doc_refs=None)], {})
    assert c["missing"] == 1 and c["tp_tolerant"] == 0
    c = classify_citations(EXP[:1], [dict(EXP[0], doc_refs=["D1", "D7"])], {})
    assert c["extra_types"] == {"unknown": 1}
    c = classify_citations(EXP[:1], [dict(EXP[0], doc_refs="D1")], {})  # a bare string is not a list of ids
    assert c["missing"] == 1


def test_aggregate_pools_counts_and_f1() -> None:
    a = classify_citations(EXP, [dict(EXP[0], doc_refs=["D1", "D9"]), dict(EXP[1])], TYPES)
    b = classify_citations(EXP[:2], [dict(EXP[1], doc_refs=["D2"])], TYPES)
    s = aggregate_citations([a, b])
    assert (s["exact"], s["over"], s["under"]) == (1, 1, 1)
    assert s["entry_f1_tolerant"] == round(2 * 2 / (6 + 3), 4)
    assert s["entry_f1_strict"] == round(2 * 1 / (6 + 3), 4)
    assert s["extra_types"] == {"bank_statement": 1}
