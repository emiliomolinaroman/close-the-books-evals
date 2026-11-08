"""Synthetic fixtures: small FinBalance-shaped data so tests never need the real datasets."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest


def fake_record(rid: str, level: int, inconsistent: bool, rng: random.Random) -> dict[str, Any]:
    amt = round(rng.uniform(100, 5000), 2)
    return {
        "record_id": rid,
        "industry": rng.choice(["retail", "saas", "manufacturing"]),
        "difficulty_level": level,
        "period_start": "2024-01-01",
        "period_end": "2024-01-31",
        "opening_balance": {"assets": {"Cash": 10000.0}, "liabilities": {}, "equity": {"Owner's Equity": 10000.0}},
        "allowed_accounts": ["Cash", "Accounts Receivable", "Service Revenue", "Owner's Equity"],
        "metadata": {
            "period_label": "January 2024",
            "entity_name": "Example Co",
            "currency_code": "USD",
            "currency_symbol": "$",
            "functional_currency_code": "USD",
            "date_format": "YYYY-MM-DD",
            "tax_regime": "none",
            "tax_label": "",
            "generator_secret": "must not leak",
        },
        "documents": [
            {
                "doc_id": "D001",
                "doc_type": "invoice",
                "title": "Invoice 1",
                "date": "2024-01-05",
                "ocr_text": f"INVOICE total {amt}",
                "role": "primary",
            }
        ],
        "expected_inconsistency": inconsistent,
        "expected_inconsistency_codes": ["invoice_total_mismatch"] if inconsistent else [],
        "inconsistency_reasons": ["total differs"] if inconsistent else [],
        "expected_entries": []
        if inconsistent
        else [
            {
                "doc_refs": ["D001"],
                "debit_account": "Accounts Receivable",
                "credit_account": "Service Revenue",
                "amount": amt,
                "memo": "x",
            }
        ],
        "expected_balance_sheet": {
            "date": "2024-01-31",
            "assets": {} if inconsistent else {"Cash": 10000.0, "Accounts Receivable": amt},
            "liabilities": {},
            "equity": {} if inconsistent else {"Owner's Equity": 10000.0, "Retained Earnings": amt},
        },
    }


def write_split(path: Path, prefix: str, n: int, seed: int, neg_every: int = 5) -> None:
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        for i in range(n):
            neg = i % neg_every == 0
            rid = f"{prefix}_NEG_{i:03d}_INVOICE_TOTAL_MISMATCH" if neg else f"{prefix}_{i:03d}"
            fh.write(json.dumps(fake_record(rid, 1 + i % 5, neg, rng)) + "\n")


@pytest.fixture
def fb_data(tmp_path: Path) -> Path:
    """A FinBalance-shaped data dir: data/main, data/fresh_seed_20260712/{coverage,main}."""
    d = tmp_path / "finbalance" / "data"
    write_split(d / "main" / "records.jsonl", "MAIN", 200, 1)
    write_split(d / "fresh_seed_20260712" / "coverage" / "records.jsonl", "COV", 25, 2)
    write_split(d / "fresh_seed_20260712" / "main" / "records.jsonl", "FRESH", 250, 3, neg_every=4)
    return d


@pytest.fixture
def built(fb_data: Path, tmp_path: Path) -> Path:
    from ctb_evals.finbalance.splits import build

    out = tmp_path / "work"
    build(fb_data, out)
    return out


ORACLE = """
import json, sys
recs = [json.loads(l) for l in open(sys.argv[1])]
key = json.load(open(KEY))
json.dump({r["record_id"]: key[r["record_id"]] for r in recs}, open(sys.argv[2], "w"))
"""


@pytest.fixture
def oracle_program(tmp_path: Path, built: Path) -> Path:
    """A run.py that cheats by reading the key: lets tests check perfect scores end to end."""
    p = tmp_path / "prog" / "run.py"
    p.parent.mkdir()
    p.write_text(f"KEY = {str(built / 'keys' / 'hidden_a.json')!r}\n" + ORACLE)
    return p
