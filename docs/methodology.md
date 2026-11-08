# Methodology

This document describes how the November 2026 study was run and how to run it again, with the
same model or another one. The numbers themselves live in [`results/RESULTS.md`](../results/RESULTS.md).

## Question

When Claude does month-end close work on data written by accountants, does it do better by
**writing a program that computes the answer** than by **reading the documents and answering
directly**? And does a prepared project scaffold (a `CLAUDE.md`, a protocol, skill and subagent files)
help a team that writes code?

## Benchmarks

| | FinBalance | APEX-Accounting (dev set) |
|---|---|---|
| Source | [Devansh1105/finbalance](https://github.com/Devansh1105/finbalance) @ `a1062b7` (paper: arXiv 2606.15949) | [mercor/apex-accounting-harbor](https://huggingface.co/datasets/mercor/apex-accounting-harbor) @ `1662b7e` |
| Who wrote it | People wrote the scenarios, document templates, chart of accounts and contradiction templates; a deterministic ledger computes the answers | Practising accountants wrote the requests, the gold answers and the rubrics |
| Unit | A packet of 5 to 50 OCR'd documents for one company and period | An open-ended close request against a shared company world |
| Answer | Journal entries with document citations, and the final balance sheet; or a contradiction code | Free text: figures, causes, proposed entries |
| Grading | Exact, by code (`ctb_evals.finbalance.scoring`) | Binary rubric criteria, by a blind model judge |
| License | Data CC BY 4.0, code Apache-2.0 | CC BY 4.0 |

Neither dataset is redistributed here. `ctb fetch` clones both at the pinned revisions and
`ctb verify` checks the SHA-256 of every file the evals read
([`src/ctb_evals/data_manifest.json`](../src/ctb_evals/data_manifest.json)).

## FinBalance splits

`ctb finbalance build` derives four splits deterministically (seeds 7 and 2026). The package
reproduces the experiment's files byte for byte; `tests/test_scoring.py` and `ctb reproduce`
check that the scores are identical.

| Split | Source | Packets | With a contradiction | Seen by teams |
|---|---|---|---|---|
| examples | `data/main` | 30 | 6 | yes, with answers |
| public | `data/main` | 60 | 15 | yes, without answers |
| hidden A | `fresh_seed_20260712/coverage` (all) | 143 | 23 | no |
| hidden B | `fresh_seed_20260712/main` (sample) | 150 | 30 | no |

The hidden splits come from a different generator seed than the data teams saw, so a program
that memorised the public packets gains nothing. Only whitelisted fields reach participants:
no document `role`, no generator metadata, no expected values. Hidden record ids are neutral
(`H000`, `Q000`). In the experiment the public split still carried the original FinBalance ids,
which spell out the contradiction code (for example `MAIN_NEG_02_BANK_CLOSING_MISMATCH`). Seven
of the eight teams say in their notes that they checked their contradiction detectors against
those ids (some only for which packets were flagged); none reads the id in `run.py`. Public scores are therefore reported but not
interpreted. The
package now anonymises public ids too (`P000`).

## Arms

**Code-writing teams.** Each team is one Claude Code agent with its own workspace, the task
statement ([`prompts/finbalance_task_es.md`](../prompts/finbalance_task_es.md); English version
[`prompts/finbalance_task_en.md`](../prompts/finbalance_task_en.md)) and the examples and public
packets. It must deliver public predictions and a `run.py` that answers new packets with no
network and no model calls. Briefs are in [`prompts/agent_briefs/`](../prompts/agent_briefs/).
Three arms: no preparation (4 teams), scaffold v6 (2 teams), scaffold v7 (2 teams).

**Direct answer.** Agents read each packet as plain text (`ctb_evals.finbalance.render`) and
write the JSON answer by hand. Only Read, Write, Edit and Glob are allowed: no shell, no code,
no calculator. Each agent handles 5 or 7 packets. All 143 packets of hidden A were answered once
with the same prompt; 40 of them were also answered a second time by fresh agents to measure
repeatability.

**Follow-up with solved examples (6 November).** To separate writing code from having seen solved
examples, the 40 sample packets were answered again by 16 fresh Claude Opus 5.5 subagents started
together, in the same groups of five: 8 with the trial-2 brief (control) and 8 with the same
brief plus three solved examples from the examples split, drawn by a fixed rule (seed 20261106,
two consistent and one inconsistent, ids replaced by EX1 to EX3). The question, the primary
outcome (pooled entry F1 with citations on the 32 clean packets, paired packet bootstrap,
10,000 resamples) and the rule for reading it were written down before the first launch, in
[`experiments/2026-11/followup_examples/PREREGISTRATION.md`](../experiments/2026-11/followup_examples/PREREGISTRATION.md).
Two deviations are recorded there: the Claude Code build had no Glob tool, so the first launch
was discarded unscored (12 of 16 agents stopped, 4 broke the tool rule to list their files) and
both briefs now name the five packet files; the second launch ran on Claude Sonnet 5.5 (the
session's default subagent model) and is reported apart. Only Read and Write were used,
and every path any tool call names is inside the agent's own folder
([`audit.json`](../experiments/2026-11/followup_examples/audit.json)).

**Second follow-up: what teaches the convention (8 November).** Two things were left open by the
first follow-up: only the code teams' brief said that citations are scored, and a builder would
more likely teach a convention with a skill or with memory than with solved examples. The same 40
packets, in the same groups, were answered in six arms by headless Claude Code sessions
(`claude -p`, Claude Opus 5.5), one per group and arm: the control brief; the control plus the
"Scoring" section of the code teams' brief; the three solved examples again; Anthropic's
`journal-entry-prep` skill, installed unchanged as a project skill and called through the Skill
tool; and, twice, notes the agent wrote itself over 8 practice packets of the examples split, each
checked by the scorer, with feedback that names the expected and the given entries and their
documents ([`feedback.py`](../src/ctb_evals/finbalance/feedback.py)). A harness in code
([`harness.py`](../experiments/2026-11/followup_teaching/harness.py)) decides every step; model,
tools, turn limit, settings sources and MCP servers are fixed on the command line, and a read
outside a session's folder is denied by the CLI. Every transcript is audited
([`stream_audit.py`](../src/ctb_evals/stream_audit.py)). Pre-registered in
[`experiments/2026-11/followup_teaching/PREREGISTRATION.md`](../experiments/2026-11/followup_teaching/PREREGISTRATION.md),
after a two-packet pilot on packets outside the test sample.

**APEX.** Ten tasks in two groups of five; per group one no-preparation team and one scaffold v6
team. Answers were graded blind (below).

## Running hidden evaluations

`ctb_evals.sandbox.run_program` runs `python run.py records.jsonl predictions.json` in a fresh
temporary directory with a 600-second limit, a `sitecustomize` that disables sockets and DNS,
no `*_API_KEY` variables, and the whole process group killed on timeout. It also reports any file
the program writes next to itself. The socket block stops ordinary Python networking but is not a
security boundary; for untrusted code use a container with `--network none`.

## Grading APEX blind

For each task the judge sees the request, the rubric, the expert answer and two answers labelled
X and Y, never which arm wrote which. The judge prompt is
[`prompts/apex_judge.md`](../prompts/apex_judge.md) and the full briefs are in
`prompts/agent_briefs/apex_judge*.md`. Judge 2 graded every task again with X and Y swapped, so
label or position bias would show up as disagreement. `ctb_evals.apex.judge` maps labels back,
aggregates and reports agreement with Cohen's kappa. Both judges are Claude; agreement between
them is not agreement with accountants (see [threats](threats-to-validity.md)).

## Statistics

Following [Miller (2024), *Adding Error Bars to Evals*](https://arxiv.org/abs/2411.00640) and
Anthropic's guidance on statistical rigour in evals:

* every rate is reported with its standard error and *n*;
* comparisons on the same packets use the **paired** difference and its SE (Miller eq. 7), plus a
  percentile bootstrap with 5,000 resamples as a check;
* APEX criteria are clustered within tasks, so their SEs are **clustered by task** (eq. 4);
* runs vary, so arm-level results also report the spread across teams and a team-level SE
  (each team counted as one draw). With two teams per scaffold arm that SE is large and the
  report says so instead of testing;
* the report gives the minimum detectable effect at 80% power for the main comparison.

Everything is in `ctb_evals.stats`, pure Python, with tests.

## Isolation and audit

In the experiment each agent was told to stay inside its workspace and not use the network.
That is a rule, not a wall, so every transcript was audited afterwards (`ctb audit`): every tool
call is checked for paths under the experiment root outside the agent's workspace, and for tools
the arm forbids. It matches absolute paths only, so a relative path that climbs out of the
workspace would not show. The audit also lists paths in scratch folders several agents could
see; see [threats](threats-to-validity.md) for what it found.

For new runs, `ctb run-team` (Claude Agent SDK, `pip install -e ".[agents]"`) enforces the rules
in code: no web tools, a `can_use_tool` guard that denies paths outside the workspace, the SDK's
Bash sandbox with no network, no operator settings loaded, and a private `TMPDIR`. The strongest
setup is one container per team that never mounts the answer keys.

## Reproducing

```bash
pip install -e ".[dev]"
ctb fetch finbalance --data data      # ~150 MB; add `apex` (needs git-lfs) to rebuild APEX workspaces
ctb reproduce --data data --work work # re-runs every team's run.py, rescoring everything (~10 s)
```

`ctb reproduce` writes `results/summary.json`, `results/RESULTS.md` and per-record outcomes in
`results/per_record/`. CI runs it on every push and fails if the committed results differ.

## Running a new model

1. `ctb finbalance build` and copy `work/finbalance/participant/` into a fresh workspace with
   `prompts/finbalance_task_en.md` as `TASK.md` (add `scaffold/en/` for the scaffold arm).
2. `ctb run-team <workspace> --prompt <brief> --model <model-id>`.
3. `ctb finbalance score --split hidden_a --program <workspace>/run.py` (and `hidden_b`).
4. Repeat for several teams per arm; the team-to-team spread in this study was 1.3 to 7.9 points.
