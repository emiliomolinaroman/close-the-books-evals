"""Score submissions: a ``run.py`` executed on a hidden split, a predictions file, or one JSON per packet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..io import read_json
from ..sandbox import run_program
from .scoring import aggregate, score_records


def _result(
    preds: dict[str, Any], keys: dict[str, Any], keep_predictions: bool = False, **extra: Any
) -> dict[str, Any]:
    outcomes = score_records(preds, keys)
    res = {"summary": aggregate(outcomes), "records": [o.as_dict() for o in outcomes], **extra}
    if keep_predictions:
        res["predictions"] = preds
    return res


def evaluate_program(
    program: str | Path,
    split_file: str | Path,
    key_file: str | Path,
    timeout: float = 600,
    keep_predictions: bool = False,
) -> dict[str, Any]:
    run = run_program(program, split_file, timeout=timeout)
    return _result(
        run.predictions,
        read_json(key_file),
        keep_predictions,
        seconds=run.seconds,
        error=run.error,
        wrote_to_program_dir=run.wrote_to_program_dir,
    )


def evaluate_predictions(
    pred_file: str | Path, key_file: str | Path, id_map_file: str | Path | None = None
) -> dict[str, Any]:
    """Score a {record_id: answer} file. ``id_map_file`` maps original FinBalance ids to neutral ids."""
    preds = read_json(pred_file)
    if id_map_file:
        id_map = read_json(id_map_file)
        preds = {id_map.get(k, k): v for k, v in preds.items()}
    return _result(preds, read_json(key_file))


def load_answer_dir(answer_dir: str | Path) -> tuple[dict[str, Any], list[str]]:
    """Read one ``<record_id>.json`` per packet; return predictions and the files that did not parse."""
    preds: dict[str, Any] = {}
    bad: list[str] = []
    for f in sorted(Path(answer_dir).glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                preds[f.stem] = json.load(fh)
        except ValueError:
            bad.append(f.name)
    return preds, bad


def evaluate_answer_dirs(
    answer_dirs: list[str | Path],
    key_file: str | Path,
    sample: list[str] | None = None,
    keep_predictions: bool = False,
) -> dict[str, Any]:
    preds: dict[str, Any] = {}
    bad: list[str] = []
    for d in answer_dirs:
        p, b = load_answer_dir(d)
        preds.update(p)
        bad.extend(b)
    keys = read_json(key_file)
    if sample is not None:
        keys = {r: keys[r] for r in sample}
    return _result(preds, keys, keep_predictions, unparseable=bad)
