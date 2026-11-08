"""Short, specific feedback on one FinBalance answer: what was expected, what was given, and where.

Used by the 2026-11-08 follow-up, where an agent answers a training packet, reads this feedback and
updates its own notes. Only training packets (from the public examples split) ever get feedback.
"""

from __future__ import annotations

from typing import Any

from ctb_evals.finbalance.scoring import _entry_key, _sections, score_record

TOL = 0.01


def _fmt_entry(e: dict[str, Any], doc_types: dict[str, str]) -> str:
    refs = ", ".join(f"{r} ({doc_types.get(str(r), '?')})" for r in sorted(str(x) for x in e.get("doc_refs") or []))
    try:
        amount = f"{float(e.get('amount', 0)):.2f}"
    except (TypeError, ValueError):
        amount = str(e.get("amount"))
    return f"Dr {e.get('debit_account')} / Cr {e.get('credit_account')} {amount}; documents: {refs or 'none'}"


def _key_or_none(e: Any, with_refs: bool) -> tuple[Any, ...] | None:
    try:
        return _entry_key(e, with_refs)
    except (TypeError, ValueError, AttributeError):
        return None


def feedback(record_id: str, solution: dict[str, Any], pred: Any, doc_types: dict[str, str]) -> str:
    """Feedback text for one packet. ``doc_types`` maps document id to its type in that packet."""
    out = score_record(record_id, solution, pred)
    lines = [f"Packet {record_id}: your answer was {'fully right' if out.correct else 'NOT fully right'}."]
    if not isinstance(pred, dict):
        lines.append("No parseable JSON answer was found for this packet.")
        return "\n".join(lines) + "\n"
    exp_codes = sorted(solution.get("inconsistency_codes") or [])
    got_codes = sorted(pred.get("inconsistency_codes") or []) if pred.get("has_inconsistency") else []
    if solution["has_inconsistency"] or pred.get("has_inconsistency"):
        lines.append(f"Inconsistency: expected {exp_codes or 'none'}; you gave {got_codes or 'none'}.")
    if solution["has_inconsistency"]:
        return "\n".join(lines) + "\n"

    expected = list(solution["entries"])
    given = [e for e in (pred.get("entries") or []) if isinstance(e, dict)]
    left = [(_entry_key(e, True), e) for e in expected]
    extra: list[dict[str, Any]] = []
    for g in given:
        k = _key_or_none(g, True)
        hit = next((i for i, (ke, _) in enumerate(left) if ke == k), None)
        if hit is None:
            extra.append(g)
        else:
            left.pop(hit)
    lines.append(
        f"Entries: {len(expected)} expected, you gave {len(given)}; "
        f"{len(expected) - len(left)} match exactly (accounts, amount and cited documents)."
    )
    if left:
        lines.append("Expected entries you did not give exactly:")
        lines += [f"- {_fmt_entry(e, doc_types)}" for _, e in left]
    if extra:
        lax_left = [_entry_key(e, False) for _, e in left]
        lines.append("Your entries that match no expected entry:")
        for g in extra:
            k = _key_or_none(g, False)
            note = ""
            if k is not None and k in lax_left:
                lax_left.remove(k)
                note = "  <- same accounts and amount as an expected entry; the cited documents differ"
            lines.append(f"- {_fmt_entry(g, doc_types)}{note}")
    try:
        a, b = _sections(solution["balance_sheet"]), _sections(pred.get("balance_sheet"))
    except (TypeError, ValueError, AttributeError):
        lines.append("Balance sheet: could not be read.")
        return "\n".join(lines) + "\n"
    diffs = []
    for s in a:
        for acct in sorted(set(a[s]) | set(b.get(s, {}))):
            x, y = a[s].get(acct), b.get(s, {}).get(acct)
            if x is None or y is None or abs(x - y) > TOL:
                diffs.append(
                    f"- {s} / {acct}: expected {x if x is not None else 'absent'}, you gave {y if y is not None else 'absent'}"
                )
    if diffs:
        lines.append("Balance sheet lines that differ:")
        lines += diffs
    else:
        lines.append("Balance sheet: correct.")
    return "\n".join(lines) + "\n"
