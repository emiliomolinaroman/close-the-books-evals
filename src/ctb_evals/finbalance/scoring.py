"""FinBalance scoring: exact balance sheet, journal-entry F1, contradiction codes.

This is a line-for-line port of the scorer used in the November 2026 experiments
(``harness/finbalance/score.py``), extended to return one outcome per record so that
standard errors and paired comparisons can be computed. ``aggregate`` reproduces the
original summary numbers exactly; ``tests/test_scoring.py`` checks it.

Rules (from the FinBalance task statement):
* a clean packet is correct when it is not flagged and every balance-sheet line matches the
  key within 0.01 with no extra or missing accounts (zero-balance lines are ignored);
* an inconsistent packet is correct when it is flagged and the set of codes is exactly the key's;
* entries are matched as multisets on (debit, credit, amount in cents) ("lax") and additionally
  on the sorted ``doc_refs`` ("strict"); F1 is pooled over clean packets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

SECTIONS = ("assets", "liabilities", "equity")
TOL = 0.01


def _sections(bs: Any) -> dict[str, dict[str, float]]:
    bs = bs if isinstance(bs, dict) else {}
    out: dict[str, dict[str, float]] = {}
    for s in SECTIONS:
        sec = bs.get(s) or {}
        out[s] = {k: round(float(v), 2) for k, v in sec.items() if abs(float(v)) > TOL}
    return out


def balance_sheet_equal(expected: Any, predicted: Any) -> bool:
    """Exact match per section and account, within one cent."""
    try:
        a, b = _sections(expected), _sections(predicted)
    except (TypeError, ValueError, AttributeError):
        return False
    for s in a:
        if set(a[s]) != set(b[s]):
            return False
        if any(abs(a[s][k] - b[s][k]) > TOL for k in a[s]):
            return False
    return True


def _entry_key(e: dict[str, Any], with_refs: bool) -> tuple[Any, ...]:
    k: tuple[Any, ...] = (e.get("debit_account"), e.get("credit_account"), round(float(e.get("amount", 0)) * 100))
    if with_refs:
        k = (*k, tuple(sorted(e.get("doc_refs") or [])))
    return k


def matched_entries(expected: list[dict[str, Any]], predicted: list[dict[str, Any]], with_refs: bool) -> int:
    """Multiset intersection size between expected and predicted entries."""
    remaining = [_entry_key(e, with_refs) for e in expected]
    tp = 0
    for p in predicted:
        try:
            k = _entry_key(p, with_refs)
        except (TypeError, ValueError, AttributeError):
            continue
        if k in remaining:
            remaining.remove(k)
            tp += 1
    return tp


@dataclass(frozen=True)
class RecordOutcome:
    record_id: str
    inconsistent: bool  # according to the key
    answered: bool
    flagged: bool
    correct: bool  # the headline metric ("fully right")
    bs_exact: bool  # clean packets only
    codes_exact: bool  # inconsistent packets only
    entries_exact_lax: bool
    entries_exact_strict: bool
    tp_lax: int
    tp_strict: int
    n_expected: int
    n_predicted: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_record(record_id: str, key: dict[str, Any], pred: Any) -> RecordOutcome:
    answered = isinstance(pred, dict)
    p: dict[str, Any] = pred if answered else {}
    flagged = bool(p.get("has_inconsistency"))
    if key["has_inconsistency"]:
        codes_ok = flagged and set(p.get("inconsistency_codes") or []) == set(key["inconsistency_codes"])
        return RecordOutcome(record_id, True, answered, flagged, codes_ok, False, codes_ok, False, False, 0, 0, 0, 0)
    entries = p.get("entries") or []
    if not isinstance(entries, list):
        entries = []
    entries = [e for e in entries if isinstance(e, dict)]
    tl = matched_entries(key["entries"], entries, False)
    ts = matched_entries(key["entries"], entries, True)
    n_exp, n_pred = len(key["entries"]), len(entries)
    bs_ok = balance_sheet_equal(key["balance_sheet"], p.get("balance_sheet")) and not flagged
    return RecordOutcome(
        record_id,
        False,
        answered,
        flagged,
        bs_ok,
        bs_ok,
        False,
        tl == n_exp == n_pred,
        ts == n_exp == n_pred,
        tl,
        ts,
        n_exp,
        n_pred,
    )


def score_records(predictions: dict[str, Any], keys: dict[str, dict[str, Any]]) -> list[RecordOutcome]:
    """Score every record in ``keys`` (missing predictions count as wrong)."""
    return [score_record(rid, k, predictions.get(rid)) for rid, k in keys.items()]


def aggregate(outcomes: list[RecordOutcome]) -> dict[str, Any]:
    """Summary metrics; same definitions and rounding as the original scorer."""
    n = len(outcomes)
    clean = [o for o in outcomes if not o.inconsistent]
    neg = [o for o in outcomes if o.inconsistent]
    n_exp = sum(o.n_expected for o in clean)
    n_pred = sum(o.n_predicted for o in clean)

    def f1(tp: int) -> float:
        return round(2 * tp / (n_exp + n_pred), 3) if n_exp + n_pred else 0.0

    return {
        "n": n,
        "n_clean": len(clean),
        "n_inconsistent": len(neg),
        "accuracy": round(sum(o.correct for o in outcomes) / max(1, n), 3),
        "bs_exact": round(sum(o.bs_exact for o in clean) / max(1, len(clean)), 3),
        "entry_f1_lax": f1(sum(o.tp_lax for o in clean)),
        "entry_f1_strict": f1(sum(o.tp_strict for o in clean)),
        "entries_exact_lax": round(sum(o.entries_exact_lax for o in clean) / max(1, len(clean)), 3),
        "inconsistency_recall": round(sum(o.flagged for o in neg) / max(1, len(neg)), 3),
        "inconsistency_code_accuracy": round(sum(o.codes_exact for o in neg) / max(1, len(neg)), 3),
        "false_alarms": sum(o.flagged for o in clean),
        "missing": sum(not o.answered for o in outcomes),
    }


# Names used by the original Spanish scorer, kept so old result files can be compared.
LEGACY_NAMES = {
    "acierto_global": "accuracy",
    "bs_exact": "bs_exact",
    "asientos_f1_laxo": "entry_f1_lax",
    "asientos_f1_estricto": "entry_f1_strict",
    "registros_asientos_laxos_ok": "entries_exact_lax",
    "incons_deteccion": "inconsistency_recall",
    "incons_codigo": "inconsistency_code_accuracy",
    "falsas_alarmas": "false_alarms",
    "sin_respuesta": "missing",
}
