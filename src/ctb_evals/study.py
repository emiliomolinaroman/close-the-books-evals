"""Reproduce every number in the November 2026 write-up from the committed team outputs.

``reproduce`` rebuilds the splits from the pinned FinBalance release, re-executes every team's
``run.py`` in the sandbox on both hidden splits, scores the public submissions and the two
direct-answer trials, aggregates the APEX judge verdicts, and writes ``results/summary.json`` plus
one JSONL of per-record outcomes per (team, split). ``report.render`` turns the summary into
``results/RESULTS.md``. Nothing here calls a model.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .apex.judge import agreement, load_verdicts, merge, summarize
from .finbalance import splits
from .finbalance.citations import aggregate_citations, classify_citations
from .finbalance.evaluate import evaluate_answer_dirs, evaluate_predictions, evaluate_program
from .io import read_json, read_jsonl, write_json, write_jsonl
from .stats import bootstrap_ci, mde, mean, mean_se, paired_diff, pooled_team_contrast, variance

Z975 = 1.959963984540054

HIDDEN = ("hidden_a", "hidden_b")


def _correct(result: dict[str, Any]) -> dict[str, float]:
    return {r["record_id"]: float(r["correct"]) for r in result["records"]}


def _arm_table(per_team: dict[str, dict[str, float]], teams: list[str], ids: list[str]) -> dict[str, Any]:
    """Arm score = mean over teams; SE over records of the per-record team mean; SD across teams."""
    per_record = [mean([per_team[t][i] for t in teams]) for i in ids]
    team_means = [mean([per_team[t][i] for i in ids]) for t in teams]
    return {
        "teams": teams,
        "n": len(ids),
        "accuracy": mean(per_record),
        "se": mean_se(per_record),
        "team_accuracies": team_means,
        "sd_across_teams": variance(team_means) ** 0.5 if len(teams) > 1 else 0.0,
    }


def _pooled_f1(outcomes: list[dict[str, Any]], tp_field: str = "tp_strict") -> float:
    tp = sum(o[tp_field] for o in outcomes)
    denom = sum(o["n_expected"] + o["n_predicted"] for o in outcomes)
    return 2 * tp / denom if denom else 0.0


def _f1_bootstrap(
    direct: dict[str, dict[str, Any]],
    teams: list[dict[str, dict[str, Any]]],
    ids: list[str],
    reps: int = 2000,
    tp_field: str = "tp_strict",
) -> dict[str, Any]:
    """Pooled entry F1, direct vs code (teams pooled), with a packet bootstrap of the difference."""
    rng = random.Random(1)

    def gap(sample: list[str]) -> float:
        code = sum((_pooled_f1([t[i] for i in sample], tp_field) for t in teams), 0.0) / len(teams)
        return code - _pooled_f1([direct[i] for i in sample], tp_field)

    diffs = sorted(gap([ids[rng.randrange(len(ids))] for _ in ids]) for _ in range(reps))
    return {"diff": gap(ids), "ci95_low": diffs[int(0.025 * reps)], "ci95_high": diffs[int(0.975 * reps)], "reps": reps}


def _boot_ci(stat: Callable[[list[str]], float], ids: list[str], reps: int, seed: int) -> list[float]:
    """95% percentile interval of ``stat`` over resamples of ``ids`` with replacement."""
    rng = random.Random(seed)
    vals = sorted(stat([ids[rng.randrange(len(ids))] for _ in ids]) for _ in range(reps))
    return [vals[int(0.025 * reps)], vals[int(0.975 * reps)]]


def examples_followup(
    cfg: dict[str, Any],
    ddir: Path,
    key_file: Path,
    sample: list[str],
    key_split: dict[str, Any],
    doc_types: dict[str, dict[str, str]],
    team_records: dict[str, dict[str, dict[str, Any]]],
    team_preds: dict[str, dict[str, Any]],
    out_records: Path,
) -> dict[str, Any]:
    """The 2026-11-06 follow-up: the direct brief again (control) and with three solved examples.

    Analysis as pre-registered in ``cfg["preregistration"]``: pooled strict entry F1 on the clean
    packets of the sample, examples minus control, with a paired packet bootstrap; the share of the
    code-vs-direct gap that the examples close; the secondary metrics side by side.
    """
    clean = [i for i in sample if not key_split[i]["has_inconsistency"]]
    teams = sorted(team_records)

    def cite(preds: dict[str, Any]) -> dict[str, dict[str, Any]]:
        out = {}
        for i in clean:
            p = preds.get(i)
            out[i] = classify_citations(
                key_split[i]["entries"], p.get("entries") if isinstance(p, dict) else None, doc_types[i]
            )
        return out

    rec: dict[str, dict[str, dict[str, Any]]] = {}
    cit: dict[str, dict[str, dict[str, Any]]] = {}
    arms: dict[str, Any] = {}
    for name in [*cfg["earlier_trials"], cfg["control"], cfg["examples"]]:
        res = evaluate_answer_dirs([ddir / name], key_file, sample, keep_predictions=True)
        if name in (cfg["control"], cfg["examples"]):
            write_jsonl(out_records / f"finbalance_direct_{name}.jsonl", res["records"])
        rec[name] = {r["record_id"]: r for r in res["records"]}
        cit[name] = cite(res["predictions"])
        summ = res["summary"]
        arms[name] = {
            "accuracy": summ["accuracy"],
            "entry_f1_strict": _pooled_f1([rec[name][i] for i in clean]),
            "entry_f1_tolerant": _pooled_f1([cit[name][i] for i in clean], "tp_tolerant"),
            "citations": aggregate_citations([cit[name][i] for i in clean]),
            **{k: summ[k] for k in ("inconsistency_recall", "inconsistency_code_accuracy", "false_alarms", "missing")},
            "unparseable": res["unparseable"],
        }
        # entries missing at least one of the key's documents: "under", plus "partial" (also adds others)
        arms[name]["entries_missing_a_key_document"] = sum(
            cit[name][i]["under"] + cit[name][i]["partial"] for i in clean
        )
    t_cit = {t: cite(team_preds[t]) for t in teams}
    code: dict[str, Any] = {
        "accuracy": mean([mean([float(team_records[t][i]["correct"]) for i in sample]) for t in teams]),
        "entry_f1_strict": mean([_pooled_f1([team_records[t][i] for i in clean]) for t in teams]),
        "entry_f1_tolerant": mean([_pooled_f1([t_cit[t][i] for i in clean], "tp_tolerant") for t in teams]),
        "entries_missing_a_key_document": {
            t: sum(t_cit[t][i]["under"] + t_cit[t][i]["partial"] for i in clean) for t in teams
        },
    }

    ctl, ex = cfg["control"], cfg["examples"]
    reps, seed = cfg["bootstrap"]["reps"], cfg["bootstrap"]["seed"]

    def f1(arm: str, ids: list[str], field: str = "tp_strict") -> float:
        src = rec[arm] if field == "tp_strict" else cit[arm]
        return _pooled_f1([src[i] for i in ids], field)

    def code_f1(ids: list[str]) -> float:
        return mean([_pooled_f1([team_records[t][i] for i in ids]) for t in teams])

    def diff(ids: list[str]) -> float:
        return f1(ex, ids) - f1(ctl, ids)

    def closed(ids: list[str]) -> float:
        return diff(ids) / (code_f1(ids) - f1(ctl, ids))

    def diff_tol(ids: list[str]) -> float:
        return f1(ex, ids, "tp_tolerant") - f1(ctl, ids, "tp_tolerant")

    def fewer_missing(ids: list[str]) -> float:  # not pre-registered
        def missing(arm: str) -> int:
            return sum(cit[arm][i]["under"] + cit[arm][i]["partial"] for i in ids)

        return float(missing(ctl) - missing(ex))

    out: dict[str, Any] = {
        "control": ctl,
        "examples": ex,
        "earlier_trials": cfg["earlier_trials"],
        "n": len(sample),
        "n_clean": len(clean),
        "arms": arms,
        "code_teams": {"teams": teams, **code},
        "entry_f1_strict_diff": {"diff": diff(clean), "ci95": _boot_ci(diff, clean, reps, seed)},
        "gap_closed": {"value": closed(clean), "ci95": _boot_ci(closed, clean, reps, seed)},
        "entry_f1_tolerant_diff": {"diff": diff_tol(clean), "ci95": _boot_ci(diff_tol, clean, reps, seed)},
        "fewer_entries_missing_a_key_document": {
            "diff": fewer_missing(clean),
            "ci95": _boot_ci(fewer_missing, clean, reps, seed),
        },
        "fully_right_paired": paired_diff(
            [float(rec[ctl][i]["correct"]) for i in sample], [float(rec[ex][i]["correct"]) for i in sample]
        ),
        "bootstrap": {"reps": reps, "seed": seed, "unit": "clean packet"},
    }
    if cfg["earlier_trials"]:  # not pre-registered: the same share against the study's own direct trials
        base = mean([arms[t]["entry_f1_strict"] for t in cfg["earlier_trials"]])
        out["vs_earlier_trials"] = {
            "trials_f1_mean": base,
            "gap_closed": (arms[ex]["entry_f1_strict"] - base) / (code["entry_f1_strict"] - base),
        }
    return out


def teaching_followup(cfg: dict[str, Any], repo: Path, *args: Any) -> dict[str, Any]:
    """The 2026-11-08 follow-up: each teaching arm against the same control, with the 1b analysis.

    ``cfg["arms"]`` maps a short label (P, E, S, Ma, Mb) to an answer folder; ``args`` are those of
    ``examples_followup`` after ``cfg``. Adds, from the harness logs committed with the follow-up,
    tokens and list-price cost per packet, which sessions called the skill, and the training chains.
    """
    import csv

    out: dict[str, Any] = {"date": cfg["date"], "preregistration": cfg["preregistration"], "control": cfg["control"]}
    arms: dict[str, Any] = {}
    for label, name in cfg["arms"].items():
        r = examples_followup({**cfg, "examples": name, "earlier_trials": []}, *args)
        arms[label] = {
            "name": name,
            "metrics": r["arms"][name],
            **{
                k: r[k]
                for k in (
                    "entry_f1_strict_diff",
                    "gap_closed",
                    "entry_f1_tolerant_diff",
                    "fewer_entries_missing_a_key_document",
                    "fully_right_paired",
                )
            },
        }
        out.update(n=r["n"], n_clean=r["n_clean"], code_teams=r["code_teams"], bootstrap=r["bootstrap"])
        out["control_metrics"] = r["arms"][cfg["control"]]
    out["arms"] = arms
    logs = repo / cfg["logs"]
    rows = list(csv.DictReader((logs / "runs.csv").open()))
    cols = (
        "input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens",
        "cost_usd_list_price",
    )
    per: dict[str, Any] = {}
    for prefix, label in cfg["log_arms"].items():
        mine = [r for r in rows if r["arm"] == prefix]
        per[label] = {
            "sessions": len(mine),
            "clean": sum(r["clean"] == "True" for r in mine),
            **{c: sum(float(r[c] or 0) for r in mine) / out["n"] for c in cols},
        }
        if prefix == "skill":
            per[label]["sessions_that_called_the_skill"] = sum(bool(r["skills"]) for r in mine)
    train = [r for r in rows if r["arm"] == "train"]
    per["training"] = {
        "sessions": len(train),
        "clean": sum(r["clean"] == "True" for r in train),
        "cost_usd_list_price": sum(float(r["cost_usd_list_price"] or 0) for r in train),
    }
    out["sessions"] = per
    out["training"] = {c: read_json(logs / f"tren_{c}_steps.json") for c in ("a", "b")}
    out["notes_words"] = {c: len((logs / f"NOTES_{c}.md").read_text(encoding="utf-8").split()) for c in ("a", "b")}
    return out


def followup_tokens(runs_csv: Path, arms: dict[str, str], packets: int) -> dict[str, dict[str, float]]:
    """Tokens per packet for each follow-up arm, from its runs.csv (workspace prefix -> arm)."""
    import csv

    rows = list(csv.DictReader(runs_csv.open()))
    cols = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    out = {}
    for arm, prefix in arms.items():
        mine = [r for r in rows if r["workspace"].startswith(prefix + "_")]
        out[arm] = {"agents": len(mine), **{c: sum(float(r[c]) for r in mine) / packets for c in cols}}
    return out


def bank_statement_convention(data_root: Path) -> dict[str, Any]:
    """How often the released answer keys cite the bank statement, over every record file of the release."""
    files = sorted(data_root.rglob("records.jsonl"))
    n_rec = with_bank = n_ent = citing = 0
    for f in files:
        for r in read_jsonl(f):
            n_rec += 1
            banks = {d["doc_id"] for d in r["documents"] if d["doc_type"] == "bank_statement"}
            with_bank += bool(banks)
            for e in r.get("expected_entries") or []:
                n_ent += 1
                citing += bool(banks & {str(x) for x in e["doc_refs"]})
    return {
        "files": [str(f.relative_to(data_root)) for f in files],
        "records": n_rec,
        "records_with_bank_statement": with_bank,
        "key_entries": n_ent,
        "key_entries_citing_bank_statement": citing,
    }


def reproduce(repo: str | Path, data_dir: str | Path, work_dir: str | Path) -> dict[str, Any]:
    repo, work = Path(repo), Path(work_dir)
    cfg = read_json(repo / "experiments" / "2026-11" / "study.json")
    fb_work = work / "finbalance"
    manifest = splits.build(Path(data_dir) / "finbalance" / "data", fb_work)
    keys = {s: fb_work / "keys" / f"{s}.json" for s in ("public", *HIDDEN)}
    split_files = {s: fb_work / "hidden" / f"{s}.jsonl" for s in HIDDEN}
    out_records = repo / "results" / "per_record"
    fb: dict[str, Any] = {"manifest": manifest["splits"], "teams": {}}
    correct: dict[str, dict[str, dict[str, float]]] = defaultdict(dict)  # split -> team -> rid -> 0/1
    timings: dict[str, float] = {}
    records: dict[str, dict[str, dict[str, dict[str, Any]]]] = defaultdict(dict)  # split -> team -> rid -> outcome
    team_preds: dict[str, dict[str, Any]] = {}  # team -> rid -> answer, on the direct-answer split

    teams_dir = repo / "team_outputs" / "finbalance"
    for team, arm in cfg["finbalance"]["teams"].items():
        tdir = teams_dir / team
        if not (tdir / "run.py").exists():
            continue
        entry: dict[str, Any] = {"arm": arm}
        pub = tdir / "public_predictions.json"
        if pub.exists():
            res = evaluate_predictions(pub, keys["public"], fb_work / "keys" / "public_source_ids.json")
            entry["public"] = res["summary"]
            write_jsonl(out_records / f"finbalance_{team}_public.jsonl", res["records"])
        for s in HIDDEN:
            res = evaluate_program(
                tdir / "run.py",
                split_files[s],
                keys[s],
                timeout=cfg["finbalance"]["timeout_s"],
                keep_predictions=s == cfg["finbalance"]["direct"]["split"],
            )
            if "predictions" in res:
                team_preds[team] = res.pop("predictions")
            timings[f"{team}:{s}"] = res["seconds"]  # machine-dependent: kept out of the committed summary
            entry[s] = {
                **res["summary"],
                "error": res["error"],
                "wrote_to_program_dir": res["wrote_to_program_dir"],
            }
            correct[s][team] = _correct(res)
            records[s][team] = {r["record_id"]: r for r in res["records"]}
            write_jsonl(out_records / f"finbalance_{team}_{s}.jsonl", res["records"])
        fb["teams"][team] = entry

    # arm-level comparisons, paired by record
    arms: dict[str, list[str]] = defaultdict(list)
    for team, arm in cfg["finbalance"]["teams"].items():
        if team in fb["teams"]:
            arms[arm].append(team)
    fb["arms"] = {}
    fb["arm_contrasts"] = {}
    for s in HIDDEN:
        ids = list(read_json(keys[s]))
        fb["arms"][s] = {a: _arm_table(correct[s], ts, ids) for a, ts in arms.items()}
        base = "no-prep"
        for a, ts in arms.items():
            if a == base:
                continue
            x = [mean([correct[s][t][i] for t in arms[base]]) for i in ids]
            y = [mean([correct[s][t][i] for t in ts]) for i in ids]
            c: dict[str, Any] = dict(paired_diff(x, y))
            ta = fb["arms"][s][base]["team_accuracies"]
            tb = fb["arms"][s][a]["team_accuracies"]
            c["team_level_se"] = (variance(ta) / len(ta) + variance(tb) / len(tb)) ** 0.5
            c["teams"] = [len(ta), len(tb)]
            # team-to-team SD pooled over all arms, t interval (each team is one draw)
            by_arm = {x: fb["arms"][s][x]["team_accuracies"] for x in arms}
            c["pooled_teams"] = pooled_team_contrast(by_arm, base, a)
            fb["arm_contrasts"][f"{s}:{a}-vs-{base}"] = c

    # direct-answer baseline, paired with the code-writing teams on the same packets
    dcfg = cfg["finbalance"]["direct"]
    split = dcfg["split"]
    ddir = teams_dir / "direct"
    code_teams = sorted(correct[split])
    sd_code = variance([mean(list(correct[split][t].values())) for t in code_teams]) ** 0.5
    direct: dict[str, Any] = {"code_teams": code_teams}

    full = evaluate_answer_dirs([ddir / d for d in dcfg["full_set"]["dirs"]], keys[split], keep_predictions=True)
    write_jsonl(out_records / "finbalance_direct_full.jsonl", full["records"])
    ids = [r["record_id"] for r in full["records"]]
    d_full = _correct(full)
    code = [mean([correct[split][t][i] for t in code_teams]) for i in ids]
    dvec = [d_full[i] for i in ids]
    pd = paired_diff(dvec, code)
    direct["full"] = {
        "n": len(ids),
        "direct": full["summary"],
        "unparseable": full["unparseable"],
        "code_accuracy": mean(code),
        "code_se": mean_se(code),
        "direct_accuracy": mean(dvec),
        "direct_se": mean_se(dvec),
        "code_summary_mean": {
            k: mean([fb["teams"][t][split][k] for t in code_teams])
            for k in ("bs_exact", "entry_f1_lax", "entry_f1_strict", "inconsistency_code_accuracy")
        },
        "paired": pd,
        "bootstrap_ci95": bootstrap_ci(dvec, code),
        # run-to-run spread of code teams adds variance the per-packet SE does not see
        "se_with_team_variance": (pd["se"] ** 2 + sd_code**2 / len(code_teams)) ** 0.5,
        "sd_code_teams": sd_code,
        "mde_80pct_power": mde(variance([y - x for x, y in zip(dvec, code, strict=True)]) ** 0.5, len(ids)),
    }
    se_t = direct["full"]["se_with_team_variance"]
    direct["full"]["ci95_with_team_variance"] = [pd["diff"] - Z975 * se_t, pd["diff"] + Z975 * se_t]

    # sensitivity, chosen after the fact: without the v7 teams (their scaffold was revised after reading
    # hidden-A errors), and with the no-preparation teams only
    arm_of = cfg["finbalance"]["teams"]
    subsets = {
        "without_scaffold_v7": [t for t in code_teams if arm_of[t] != "scaffold-v7"],
        "no_prep_only": [t for t in code_teams if arm_of[t] == "no-prep"],
    }
    direct["full"]["sensitivity"] = {}
    for name, ts in subsets.items():
        sub = [mean([correct[split][t][i] for t in ts]) for i in ids]
        pds = paired_diff(dvec, sub)
        sd_s = variance([mean([correct[split][t][i] for i in ids]) for t in ts]) ** 0.5
        se_s = (pds["se"] ** 2 + sd_s**2 / len(ts)) ** 0.5
        direct["full"]["sensitivity"][name] = {
            "teams": ts,
            "code_accuracy": mean(sub),
            "diff": pds["diff"],
            "se_with_team_variance": se_s,
            "ci95_with_team_variance": [pds["diff"] - Z975 * se_s, pds["diff"] + Z975 * se_s],
        }

    # where the gap comes from: by packet type and difficulty, and the secondary metrics with uncertainty
    level = {r["record_id"]: r["difficulty_level"] for r in read_jsonl(split_files[split])}
    d_rec = {r["record_id"]: r for r in full["records"]}
    groups: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        groups["contradiction" if d_rec[i]["inconsistent"] else "clean"].append(i)
        groups[f"level {level[i]}"].append(i)
    direct["full"]["breakdown"] = {
        g: {
            "n": len(m),
            "direct": mean([d_full[i] for i in m]),
            "code": mean([mean([correct[split][t][i] for t in code_teams]) for i in m]),
        }
        for g, m in sorted(groups.items())
    }
    clean = groups["clean"]
    direct["full"]["bs_exact_paired"] = paired_diff(
        [float(d_rec[i]["bs_exact"]) for i in clean],
        [mean([float(records[split][t][i]["bs_exact"]) for t in code_teams]) for i in clean],
    )
    direct["full"]["entry_f1_strict_ci95"] = _f1_bootstrap(d_rec, [records[split][t] for t in code_teams], clean)

    # how the citations of correctly booked entries differ from the key (finbalance/citations.py)
    key_split = read_json(keys[split])
    doc_types = {
        r["record_id"]: {d["doc_id"]: d["doc_type"] for d in r["documents"]} for r in read_jsonl(split_files[split])
    }

    def citations(preds: dict[str, Any]) -> dict[str, dict[str, Any]]:
        out = {}
        for i in clean:
            p = preds.get(i)
            out[i] = classify_citations(
                key_split[i]["entries"], p.get("entries") if isinstance(p, dict) else None, doc_types[i]
            )
        return out

    d_cite = citations(full["predictions"])
    t_cite = [citations(team_preds[t]) for t in code_teams]
    direct["full"]["citations"] = {
        "direct": aggregate_citations(list(d_cite.values())),
        "code_teams": {t: aggregate_citations(list(c.values())) for t, c in zip(code_teams, t_cite, strict=True)},
        "entry_f1_tolerant_ci95": _f1_bootstrap(d_cite, t_cite, clean, tp_field="tp_tolerant"),
    }

    rep = dcfg["repeat_sample"]
    sample = read_json(repo / rep["sample"])
    trials: dict[str, Any] = {}
    trial_correct: dict[str, dict[str, float]] = {}
    for trial in rep["trials"]:
        res = evaluate_answer_dirs([ddir / trial], keys[split], sample)
        trials[trial] = {**res["summary"], "unparseable": res["unparseable"]}
        trial_correct[trial] = _correct(res)
        write_jsonl(out_records / f"finbalance_direct_{trial}.jsonl", res["records"])
    t1, t2 = (trial_correct[t] for t in rep["trials"])
    code40 = [mean([correct[split][t][i] for t in code_teams]) for i in sample]
    mean40 = [(t1[i] + t2[i]) / 2 for i in sample]
    direct["repeat_sample"] = {
        "n": len(sample),
        "trials": trials,
        "agreement": sum(1 for i in sample if t1[i] == t2[i]) / len(sample),
        "pass_both": mean([min(t1[i], t2[i]) for i in sample]),
        "pass_either": mean([max(t1[i], t2[i]) for i in sample]),
        "code_accuracy": mean(code40),
        "paired_vs_trial_mean": paired_diff(mean40, code40),
    }
    if "examples_followup" in dcfg:
        fcfg = dcfg["examples_followup"]
        args = (ddir, keys[split], sample, key_split, doc_types, records[split], team_preds, out_records)
        direct["examples_followup"] = examples_followup(fcfg, *args)
        if "runs" in fcfg:
            direct["examples_followup"]["tokens_per_packet"] = followup_tokens(
                repo / fcfg["runs"]["file"], fcfg["runs"]["arms"], len(sample)
            )
        if "sonnet_run" in fcfg:  # the launch that ran on the wrong model: a within-Sonnet comparison only
            son = examples_followup({**fcfg, **fcfg["sonnet_run"], "earlier_trials": []}, *args)
            direct["examples_followup"]["sonnet_run"] = {
                "model": fcfg["sonnet_run"]["model"],
                **{
                    k: son[k] for k in ("control", "examples", "arms", "entry_f1_strict_diff", "entry_f1_tolerant_diff")
                },
                "fully_right_paired": son["fully_right_paired"],
            }
    if "teaching_followup" in dcfg:
        targs = (ddir, keys[split], sample, key_split, doc_types, records[split], team_preds, out_records)
        direct["teaching_followup"] = teaching_followup(dcfg["teaching_followup"], repo, *targs)
    fb["direct"] = direct
    fb["bank_statement_convention"] = bank_statement_convention(Path(data_dir) / "finbalance" / "data")

    # APEX
    res_dir = repo / "results"
    judges = {}
    for j in ("judge1", "judge2"):
        judges[j] = merge(
            *[
                load_verdicts(res_dir / f"apex_{g}_{j}.json", read_json(res_dir / f"apex_{g}_{j}_labels.json"))
                for g in cfg["apex"]["groups"]
            ]
        )
    apex = {j: summarize(v) for j, v in judges.items()}
    apex["agreement"] = agreement(judges["judge1"], judges["judge2"])
    apex["per_task"] = {
        t: {
            arm: {"passed": sum(judges["judge1"][t][arm]), "criteria": len(judges["judge1"][t][arm])}
            for arm in ("A", "B")
        }
        for t in sorted(judges["judge1"], key=lambda x: int(x[1:]))
    }

    summary = {
        "study": {k: cfg[k] for k in ("id", "dates", "model", "harness", "list_prices_usd_per_mtok") if k in cfg},
        "finbalance": fb,
        "apex": apex,
        "effort": effort_summary(res_dir / "runs.csv", answered=f_answered(direct)),
    }
    write_json(res_dir / "summary.json", summary)
    write_json(work / "timings.json", timings)
    return summary


def f_answered(direct: dict[str, Any]) -> int:
    """Packets answered by direct-answer agents: the full set plus the repeated trial."""
    return int(direct["full"]["n"] + direct["repeat_sample"]["n"])


def effort_summary(runs_csv: Path, answered: int) -> dict[str, Any]:
    """Tokens and tool calls per run, by kind of run, from the transcript audit (results/runs.csv)."""
    import csv

    if not runs_csv.exists():
        return {}
    kinds: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in csv.DictReader(runs_csv.open()):
        ws = row["workspace"]
        kind = (
            "direct_answer"
            if "/directo" in ws
            else "finbalance_team"
            if "/fb_" in ws
            else "apex_team"
            if "/apex_" in ws
            else "apex_judge"
            if "/corregir" in ws
            else None
        )
        if kind:
            kinds[kind].append(row)
    out: dict[str, Any] = {}
    cols = ("tool_calls", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "input_tokens")
    for kind, rows in sorted(kinds.items()):
        out[kind] = {"runs": len(rows), **{f"{c}_per_run": mean([float(r[c]) for r in rows]) for c in cols}}
    if "direct_answer" in out:
        total_out = sum(float(r["output_tokens"]) for r in kinds["direct_answer"])
        out["direct_answer"]["packets_answered"] = answered
        out["direct_answer"]["output_tokens_per_packet"] = total_out / answered
        total_cache = sum(float(r["cache_read_input_tokens"]) for r in kinds["direct_answer"])
        out["direct_answer"]["cache_read_tokens_per_packet"] = total_cache / answered
    return out


def runs_table(audit: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten an audit into rows for results/runs.csv."""
    rows = []
    for a in audit:
        u = a.get("usage", {})
        rows.append(
            {
                "workspace": a["workspace"],
                "arm": a["arm"],
                "turns": a["turns"],
                "tool_calls": a["tool_calls"],
                "minutes": a["minutes"],
                "input_tokens": u.get("input_tokens", 0),
                "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
                "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
                "output_tokens": u.get("output_tokens", 0),
                "breaches": len(a["breaches"]),
            }
        )
    return rows


def dumps(obj: Any) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False)
