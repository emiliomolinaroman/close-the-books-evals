"""Render a FinBalance record as the plain-text packet a model reads in the direct-answer arm."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_packet(r: dict[str, Any]) -> str:
    c = r["context"]
    lines = [
        "Record context:",
        f"- Record ID: {r['record_id']}",
        f"- Industry: {r['industry']}",
        f"- Difficulty level: {r['difficulty_level']}",
        f"- Period: {c.get('period_label')}",
        f"- Period start: {r['period_start']}",
        f"- Period end: {r['period_end']}",
        f"- Entity: {c.get('entity_name')}",
        f"- Document display currency: {c.get('currency_code')} ({c.get('currency_symbol')})",
        f"- Functional currency for the answer: {c.get('functional_currency_code') or c.get('currency_code')}",
        f"- Document date format: {c.get('date_format')}",
        f"- Indirect tax regime for this packet: {c.get('tax_regime')}",
        "",
        "Opening balance:",
        json.dumps(r["opening_balance"], indent=1),
        "",
        "Allowed account names:",
        json.dumps(r["allowed_accounts"], indent=1),
        "",
        "Documents:",
    ]
    for doc in r["documents"]:
        lines += [
            "",
            f"Document ID: {doc['doc_id']}",
            f"Document Type: {doc['doc_type']}",
            f"Document Title: {doc['title']}",
            "Document OCR Text:",
            (doc["ocr_text"] or "").strip(),
        ]
    return "\n".join(lines) + "\n"


def write_direct_workspaces(
    records: list[dict[str, Any]], spec: str, out_dir: str | Path, per_agent: int, prefix: str = "direct"
) -> list[Path]:
    """Split records into folders of ``per_agent`` packets, each with the benchmark spec and an empty output dir."""
    made = []
    for g in range(0, len(records), per_agent):
        d = Path(out_dir) / f"{prefix}_{g // per_agent}"
        (d / "packets").mkdir(parents=True, exist_ok=True)
        (d / "output").mkdir(exist_ok=True)
        (d / "INSTRUCTIONS.md").write_text(spec, encoding="utf-8")
        for r in records[g : g + per_agent]:
            (d / "packets" / f"{r['record_id']}.txt").write_text(render_packet(r), encoding="utf-8")
        made.append(d)
    return made
