"""Blind pairwise grading for APEX-Accounting answers, and aggregation of judge verdicts.

Workflow
1. ``build_blind_bundle`` writes, per task, the request, the rubric, the expert answer and the two
   answers to compare under neutral labels X/Y. The X/Y assignment is random per bundle and stored
   in a separate ``labels.json`` the judge never sees.
2. A judge (a model or a person) writes ``verdicts.json``: ``{task: {"X": [0/1 per criterion], "Y": [...]}}``.
3. ``load_verdicts`` maps X/Y back to arms; ``summarize`` reports criteria passed per arm with a
   task-clustered standard error, the paired difference, and judge-vs-judge agreement.

A second judge should get the opposite label assignment, so that any label or position bias shows
up as disagreement rather than as an arm effect. Agreement between two model judges is not
calibration against people: see docs/threats-to-validity.md.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from ..io import read_json, write_json
from ..stats import clustered_se, cohens_kappa, mean, paired_diff

Verdicts = dict[str, dict[str, list[int]]]  # task -> arm -> criterion scores


def rubric_criteria(grading_config: str | Path) -> list[str]:
    cfg = read_json(grading_config)
    return [v["verifier_values"]["criteria"] for v in cfg["verifiers"]]


def build_blind_bundle(
    task_id: str,
    request: str,
    criteria: list[str],
    expert_answer: str,
    answers: dict[str, str],
    out_dir: str | Path,
    seed: int,
    swap: bool = False,
) -> dict[str, str]:
    """Write a judge bundle for one task. ``answers`` maps arm name -> answer text (exactly two arms)."""
    if len(answers) != 2:
        raise ValueError("blind pairwise grading needs exactly two answers")
    arms = sorted(answers)
    random.Random(f"{seed}:{task_id}").shuffle(arms)
    if swap:
        arms.reverse()
    labels = {"X": arms[0], "Y": arms[1]}
    d = Path(out_dir) / task_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "request.md").write_text(request, encoding="utf-8")
    (d / "rubric.md").write_text("\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria)) + "\n", encoding="utf-8")
    (d / "expert_answer.txt").write_text(expert_answer, encoding="utf-8")
    for lab, arm in labels.items():
        (d / f"answer_{lab}.md").write_text(answers[arm], encoding="utf-8")
    return labels


def load_verdicts(verdicts_path: str | Path, labels: dict[str, str] | dict[str, dict[str, str]]) -> Verdicts:
    """Map X/Y verdicts back to arms. ``labels`` is either one mapping for all tasks or one per task."""
    raw = read_json(verdicts_path)
    out: Verdicts = {}
    for task, by_label in raw.items():
        per_task = labels.get(task)
        lab: dict[str, str] = per_task if isinstance(per_task, dict) else labels  # type: ignore[assignment]
        out[task] = {lab[x]: [int(v) for v in by_label[x]] for x in ("X", "Y")}
    return out


def flatten(v: Verdicts, arm: str) -> tuple[list[int], list[str]]:
    """Per-criterion scores for one arm, with the task of each criterion (the cluster)."""
    scores, clusters = [], []
    for task in sorted(v):
        for s in v[task][arm]:
            scores.append(s)
            clusters.append(task)
    return scores, clusters


def summarize(v: Verdicts, arm_a: str = "A", arm_b: str = "B") -> dict[str, Any]:
    a, ca = flatten(v, arm_a)
    b, _ = flatten(v, arm_b)
    pd = paired_diff([float(x) for x in a], [float(x) for x in b])
    diffs = [y - x for x, y in zip(a, b, strict=True)]
    return {
        "criteria": len(a),
        "tasks": len(v),
        arm_a: {"passed": sum(a), "rate": mean(a), "se_clustered": clustered_se(a, ca)},
        arm_b: {"passed": sum(b), "rate": mean(b), "se_clustered": clustered_se(b, ca)},
        "diff": pd["diff"],
        "diff_se_clustered": clustered_se(diffs, ca),
        "criteria_b_only": pd["b_better"],
        "criteria_a_only": pd["a_better"],
    }


def agreement(v1: Verdicts, v2: Verdicts) -> dict[str, Any]:
    """Criterion-level agreement between two judges over every (task, arm, criterion)."""
    r1, r2 = [], []
    for task in sorted(v1):
        for arm in sorted(v1[task]):
            x, y = v1[task][arm], v2[task][arm]
            if len(x) != len(y):
                raise ValueError(f"{task}/{arm}: judges graded a different number of criteria")
            r1.extend(x)
            r2.extend(y)
    same = sum(1 for x, y in zip(r1, r2, strict=True) if x == y)
    return {"pairs": len(r1), "agree": same, "rate": same / len(r1), "kappa": cohens_kappa(r1, r2)}


def merge(*parts: Verdicts) -> Verdicts:
    out: Verdicts = {}
    for p in parts:
        overlap = set(out) & set(p)
        if overlap:
            raise ValueError(f"tasks graded twice: {sorted(overlap)}")
        out.update(p)
    return out


def dump_bundle_index(out_dir: str | Path, labels: dict[str, dict[str, str]]) -> None:
    """Labels go to a sibling file outside the bundle, so the judge's workspace never contains them."""
    write_json(Path(str(out_dir).rstrip("/") + "_labels.json"), labels)
    (Path(out_dir) / "VERDICT_FORMAT.json").write_text(
        json.dumps({"<task>": {"X": [1, 0, "..."], "Y": [1, 1, "..."]}}, indent=1) + "\n", encoding="utf-8"
    )
