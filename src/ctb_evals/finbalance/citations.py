"""Where the citation errors come from. Not part of the original FinBalance scorer.

The strict entry F1 counts an entry as right only when its ``doc_refs`` equal the key's exactly.
This module looks at the entries that get accounts and amount right (the lax match) and asks how
their citations differ from the key:

* ``exact``: the same documents (what the strict F1 counts);
* ``over``: every document the key cites, plus others;
* ``under``: some of the key's documents and nothing else;
* ``partial``: some in common, but neither contains the other;
* ``disjoint``: no document in common;
* ``missing``: no ``doc_refs`` list at all.

Pairing follows the scorer: entries are first paired on (debit, credit, amount in cents, sorted
``doc_refs``), so ``exact`` equals the strict true positives; the rest are then paired on
(debit, credit, amount in cents) alone, so the six classes add up to the lax true positives.
When several key entries share accounts and amount, which one a leftover prediction is paired with
can change its class, and so ``tp_tolerant``, but not the strict or lax totals. In the hidden
splits of this study no two key entries of a packet share accounts and amount.

``tp_tolerant`` (``exact`` + ``over``) gives a "cites at least the right documents" F1. The task
statement allows it: "support-only docs may also be included when needed".
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .scoring import _entry_key

CLASSES = ("exact", "over", "under", "partial", "disjoint", "missing")


def _key(e: dict[str, Any], with_refs: bool) -> tuple[Any, ...] | None:
    try:
        return _entry_key(e, with_refs)
    except (TypeError, ValueError, AttributeError):
        return None


def _ref_set(e: dict[str, Any]) -> frozenset[str]:
    refs = e.get("doc_refs")
    if not isinstance(refs, list):
        return frozenset()
    return frozenset(str(r) for r in refs)


def classify_citations(
    expected: list[dict[str, Any]], predicted: Any, doc_types: dict[str, str] | None = None
) -> dict[str, Any]:
    """Classify the citations of one packet's predicted entries against the key."""
    types = doc_types or {}
    entries = [p for p in predicted if isinstance(p, dict)] if isinstance(predicted, list) else []
    counts: Counter[str] = Counter({c: 0 for c in CLASSES})
    extra: Counter[str] = Counter()
    lacking: Counter[str] = Counter()

    free = list(expected)
    free_strict = [_key(e, True) for e in free]
    pending = []
    for p in entries:
        k = _key(p, True)
        if k is not None and k in free_strict:
            i = free_strict.index(k)
            del free[i], free_strict[i]
            counts["exact"] += 1
        else:
            pending.append(p)

    free_lax = [_key(e, False) for e in free]
    for p in pending:
        k = _key(p, False)
        if k is None or k not in free_lax:
            continue
        i = free_lax.index(k)
        gold = free[i]
        del free[i], free_lax[i]
        got, want = _ref_set(p), _ref_set(gold)
        if not got:
            cls = "missing"
        elif want <= got:
            cls = "over"
            extra.update(types.get(d, "unknown") for d in got - want)
        elif got < want:
            cls = "under"
            lacking.update(types.get(d, "unknown") for d in want - got)
        elif got & want:
            cls = "partial"
        else:
            cls = "disjoint"
        counts[cls] += 1

    return {
        **{c: counts[c] for c in CLASSES},
        "tp_tolerant": counts["exact"] + counts["over"],
        "n_expected": len(expected),
        "n_predicted": len(entries),
        "extra_types": dict(extra),
        "lacking_types": dict(lacking),
    }


def aggregate_citations(packets: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool the per-packet classifications; F1 is pooled the same way as the scorer's."""
    n = sum(p["n_expected"] + p["n_predicted"] for p in packets)
    extra: Counter[str] = Counter()
    lacking: Counter[str] = Counter()
    for p in packets:
        extra.update(p["extra_types"])
        lacking.update(p["lacking_types"])

    def f1(tp: int) -> float:
        return round(2 * tp / n, 4) if n else 0.0

    return {
        **{c: sum(p[c] for p in packets) for c in CLASSES},
        "entry_f1_strict": f1(sum(p["exact"] for p in packets)),
        "entry_f1_tolerant": f1(sum(p["tp_tolerant"] for p in packets)),
        "extra_types": dict(extra.most_common()),
        "lacking_types": dict(lacking.most_common()),
    }
