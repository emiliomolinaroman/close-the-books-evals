# Eval card: Close the Books

A short datasheet in the spirit of model cards and *Datasheets for Datasets*.

| | |
|---|---|
| **What it measures** | Whether Claude, working as an agent on month-end close tasks written by people, gets more right by writing a program than by answering directly; and whether a project scaffold helps. |
| **Tasks** | FinBalance: document packets to journal entries plus an exact balance sheet, or a contradiction code. APEX-Accounting dev set: ten open-ended close requests graded by binary rubric criteria. |
| **Splits** | FinBalance: 30 solved examples, 60 public, hidden A (143, another generator seed), hidden B (150, another seed). APEX: 10 tasks, 89 criteria. |
| **Metrics** | FinBalance: packet fully right (primary), balance sheet exact, entry F1 with and without document citations, contradiction-code accuracy, false alarms. APEX: share of criteria met. |
| **Graders** | FinBalance: exact, deterministic code. APEX: blind Claude judge, run twice with labels swapped; agreement and kappa reported. |
| **Uncertainty** | SE for every rate; paired SEs for same-item comparisons; task-clustered SEs for APEX; team-level SEs for arm comparisons; bootstrap checks; minimum detectable effect. |
| **Primary result** | Hidden A, fully right: answering directly 76.9% (3.5), writing code 82.6% (2.8), paired gap +5.7 (2.8); 95% CI -0.4 to +11.8 counting team variance. Citation F1 0.57 vs 0.91, and 0.73 vs 0.91 when extra cited documents are allowed. Pre-registered follow-up on 40 packets: three solved examples raise the direct answer's citation F1 from 0.50 to 0.72 (code 0.90), closing 0.56 [0.42, 0.69] of the gap. |
| **Systems evaluated** | Claude Opus 5.5 in Claude Code 2.1.318, November 2026; the follow-up in Claude Code 2.1.316 (plus one launch on Claude Sonnet 5.5, reported apart). |
| **Intended use** | Comparing ways of deploying a model on structured close work; a starting harness for running the same comparison on other models. |
| **Not intended for** | Ranking models on APEX-Accounting (dev set, unofficial harness and judge); claims about real, messy documents; claims that a scaffold does or does not help in general (two teams per arm). |
| **Data provenance** | FinBalance (Devansh1105/finbalance @ a1062b7, data CC BY 4.0) and APEX-Accounting (mercor/apex-accounting-harbor @ 1662b7e, CC BY 4.0). Pinned and checksummed. |
| **Contamination** | Both datasets are public; the model may have seen the public parts in training. The hidden FinBalance splits come from a later generator seed (July 2026 release), but the generator and its templates are public, which would favour the code arm. APEX dev tasks are public. |
| **Known issues** | See [threats-to-validity.md](threats-to-validity.md): templated documents, few runs per arm, direct arm without solved examples (three in the follow-up, against 30 for the code teams), public-id leak used by seven of eight teams to check their detectors (fixed in the package), shared scratch folder (fixed in the runner), scaffold delivered as files to read, model judges without human calibration. |
| **Maintenance** | `ctb reproduce` and CI re-derive every committed number. Open an issue for errors. |
