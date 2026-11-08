"""Build the FinBalance splits used in the experiments, deterministically.

Splits (all derived from the public FinBalance release, CC BY 4.0):
  examples   30 solved packets from ``data/main`` (24 clean, 6 inconsistent), answers included
  public     60 unsolved packets from ``data/main`` (45 clean, 15 inconsistent)
  hidden_a  143 packets: the whole ``fresh_seed_20260712/coverage`` split (another generator seed)
  hidden_b  150 packets from ``fresh_seed_20260712/main`` (120 clean, 30 inconsistent)

Leakage controls: only whitelisted fields reach participants (no document ``role``, no generator metadata,
no expected entries); hidden and public ids are replaced by neutral ids because the original ids encode
the contradiction code (e.g. ``MAIN_NEG_02_BANK_CLOSING_MISMATCH``).
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from ..io import read_jsonl, sha256_file, write_json, write_jsonl

KEEP_META = (
    "period_label",
    "entity_name",
    "currency_code",
    "currency_symbol",
    "functional_currency_code",
    "date_format",
    "tax_regime",
    "tax_label",
)
KEEP_DOC = ("doc_id", "doc_type", "title", "date", "ocr_text")
SEED_MAIN = 7
SEED_HIDDEN_B = 2026


def strip_record(r: dict[str, Any]) -> dict[str, Any]:
    """Return the participant-visible view of a FinBalance record."""
    return {
        "record_id": r["record_id"],
        "industry": r["industry"],
        "difficulty_level": r["difficulty_level"],
        "period_start": r["period_start"],
        "period_end": r["period_end"],
        "opening_balance": r["opening_balance"],
        "allowed_accounts": r["allowed_accounts"],
        "context": {k: r["metadata"].get(k) for k in KEEP_META},
        "documents": [{k: d.get(k) for k in KEEP_DOC} for d in r["documents"]],
    }


def answer_of(r: dict[str, Any]) -> dict[str, Any]:
    """Return the gold answer in the submission format."""
    return {
        "has_inconsistency": r["expected_inconsistency"],
        "inconsistency_codes": r["expected_inconsistency_codes"],
        "inconsistency_notes": r.get("inconsistency_reasons", []),
        "entries": [
            {k: e[k] for k in ("doc_refs", "debit_account", "credit_account", "amount")} for e in r["expected_entries"]
        ],
        "balance_sheet": {k: r["expected_balance_sheet"].get(k, {}) for k in ("assets", "liabilities", "equity")},
    }


def _pick(records: list[dict[str, Any]], n: int, used: set[str]) -> list[dict[str, Any]]:
    """Round-robin over difficulty levels (1-5) so every level is represented."""
    by_level: dict[int, list[dict[str, Any]]] = {}
    for r in records:
        if r["record_id"] not in used:
            by_level.setdefault(r["difficulty_level"], []).append(r)
    out: list[dict[str, Any]] = []
    while len(out) < n:
        progressed = False
        for level in sorted(by_level):
            if by_level[level] and len(out) < n:
                out.append(by_level[level].pop())
                progressed = True
        if not progressed:
            raise ValueError(f"not enough records to pick {n}")
    used.update(x["record_id"] for x in out)
    return out


def select(data_dir: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Select the raw records of every split (same selection as the November 2026 experiments)."""
    data_dir = Path(data_dir)
    main = list(read_jsonl(data_dir / "main" / "records.jsonl"))
    rng = random.Random(SEED_MAIN)
    rng.shuffle(main)
    clean = [r for r in main if not r["expected_inconsistency"]]
    neg = [r for r in main if r["expected_inconsistency"]]
    used: set[str] = set()
    examples = _pick(clean, 24, used) + _pick(neg, 6, used)
    public = _pick(clean, 45, used) + _pick(neg, 15, used)
    rng.shuffle(examples)
    rng.shuffle(public)
    hidden_a = list(read_jsonl(data_dir / "fresh_seed_20260712" / "coverage" / "records.jsonl"))
    fresh = list(read_jsonl(data_dir / "fresh_seed_20260712" / "main" / "records.jsonl"))
    rng_b = random.Random(SEED_HIDDEN_B)
    rng_b.shuffle(fresh)
    hidden_b = [r for r in fresh if not r["expected_inconsistency"]][:120] + [
        r for r in fresh if r["expected_inconsistency"]
    ][:30]
    rng_b.shuffle(hidden_b)
    return {"examples": examples, "public": public, "hidden_a": hidden_a, "hidden_b": hidden_b}


PREFIX = {"public": "P", "hidden_a": "H", "hidden_b": "Q"}


def build(data_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Write participant files, answer keys and a manifest with checksums. Returns the manifest."""
    out = Path(out_dir)
    sel = select(data_dir)
    manifest: dict[str, Any] = {
        "source": str(data_dir),
        "seeds": {"main": SEED_MAIN, "hidden_b": SEED_HIDDEN_B},
        "splits": {},
    }
    # examples keep their ids and carry the answer: they are the "history" participants learn from
    ex_rows = []
    for r in sel["examples"]:
        row = strip_record(r)
        row["solution"] = answer_of(r)
        ex_rows.append(row)
    write_jsonl(out / "participant" / "examples.jsonl", ex_rows)
    for split in ("public", "hidden_a", "hidden_b"):
        rows, key, id_map = [], {}, {}
        for i, r in enumerate(sel[split]):
            new_id = f"{PREFIX[split]}{i:03d}"
            row = strip_record(r)
            row["record_id"] = new_id
            rows.append(row)
            key[new_id] = answer_of(r)
            id_map[r["record_id"]] = new_id
        where = "participant" if split == "public" else "hidden"
        path = out / where / f"{split}.jsonl"
        write_jsonl(path, rows)
        write_json(out / "keys" / f"{split}.json", key)
        write_json(out / "keys" / f"{split}_source_ids.json", id_map)
        manifest["splits"][split] = {
            "records": len(rows),
            "inconsistent": sum(1 for v in key.values() if v["has_inconsistency"]),
            "sha256": sha256_file(path),
        }
    manifest["splits"]["examples"] = {
        "records": len(ex_rows),
        "inconsistent": sum(1 for r in ex_rows if r["solution"]["has_inconsistency"]),
        "sha256": sha256_file(out / "participant" / "examples.jsonl"),
    }
    write_json(out / "manifest.json", manifest)
    return manifest
