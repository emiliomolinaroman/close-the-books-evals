# Follow-up of 2026-11-06: is the citation gap about code, or about having seen examples?

Written on 2026-11-06 at 23:28 CET, before any agent of this follow-up was started. Nothing below
is changed after the run; anything decided later is marked as such in the results.

## Why

In the main study the code teams beat direct answers by +0.34 in strict entry F1 on hidden A. Half
of that gap is a citation convention: the answer key never cites the bank statement, and all 30
worked examples the code teams saw follow that rule; the direct arm saw none. So the gap may come
from having seen examples, not from writing a program. This follow-up separates the two.

## Arms

Both on the 40 packets of `experiments/2026-11/sample_40.json` (hidden A), in the same 8 groups
of 5, one fresh Claude Code subagent (Claude Opus 5.5) per group and arm, all 16 started together.

* **D0, control.** The trial-2 brief (`prompts/agent_briefs/direct_trial2.md`) word for word, with
  the new folder path. Same instructions file, same packet rendering. It measures what changed
  with the environment (another machine, another Claude Code version) since trials 1 and 2.
* **D3, three worked examples.** The same brief plus one sentence pointing at `ejemplos/`: three
  packets from the public examples split (`examples.jsonl`) with their correct answers. Chosen by a
  fixed rule before the run: seed 20261106, two consistent and one inconsistent packet, order
  shuffled, record ids replaced by EX1 to EX3. Drawn: COV_HEA_M4_0063, MAIN_NEG_01_BANK_CLOSING_MISMATCH,
  DB_PRO_M4_00012. Every one of the 30 examples has a bank statement and no key entry cites it.

Same tool rule as trials 1 and 2: Read, Write and Glob only, no code or calculator.

## Outcomes

Primary: pooled strict entry F1 on the 32 consistent packets, D3 minus D0, with a 95% interval
from 10,000 paired bootstrap resamples of packets (seed 7).

Gap closed: (F1 D3 − F1 D0) / (F1 code − F1 D0), where F1 code is the mean strict entry F1 of the
eight code teams on the same 32 packets (0.899 before the run). Interval from the same bootstrap.

Secondary, all D3 against D0:
* citation classes (`finbalance/citations.py`): entries that over-cite, and of those how many add a
  bank statement; entries that under-cite;
* tolerant entry F1 (exact plus over-citation);
* fully right on the 40 packets (paired difference, packet-level SE);
* inconsistency recall and code accuracy on the 8 contradictions.

Environment check: D0 against trials 1 and 2 on strict entry F1 and fully right. Before the run
they were 0.583 and 0.561 (strict F1), 0.700 and 0.725 (fully right).

## How the result will be read

Decided now:
* gap closed of 0.5 or more and the D3 − D0 interval above zero: most of the citation gap is
  examples, not code. The article says so and the headline rests on fully right and cost.
* gap closed under 0.25: examples alone do not close it; the article says writing a program matters
  for citations too, with this result as the evidence.
* in between: partly; the article gives the number.

Fully right is underpowered here (40 packets; on all 143 the main study's interval already
crosses zero once team variance is counted), so it is reported but no conclusion rests on it.

## Handling

* A packet without a parseable answer counts as wrong, as in the scorer.
* An agent that stops before writing its five answers is not rerun; its missing packets count as
  wrong and are listed.
* The transcripts are audited with `ctb audit` and with a stricter check: every path a tool call
  names must be inside the agent's own folder.
* The answers are added unedited to `team_outputs/finbalance/direct/` and scored by `ctb reproduce`.

## Deviation (added 2026-11-06, 23:31 CET, after the first launch)

The first launch (23:29) produced nothing: all 16 agents stopped after three tool calls without
reading a packet. In this Claude Code build subagents have no Glob tool, and the brief forbids
Bash, so they could not list `paquetes/`. No packet had been read, so this is not a model result.

Change for the second launch, the same in both arms: the brief names the five packet files of the
folder, and the clause "(Glob only to list the packets)" is dropped, which leaves the trial-1
wording of the tool rule. Everything else as above, with 16 fresh agents.

## Deviation 2 (added 2026-11-06, 23:38 CET, after the second launch, before scoring it)

The audit of the second launch (r12, 23:32) shows every assistant message came from Claude Sonnet
5.5, not Claude Opus 5.5: this session's default subagent model is Sonnet and the launch did not set
the model. The study is Opus 5.5 throughout, so r12 does not answer the question above. It is kept
and reported apart as a within-Sonnet comparison (same two briefs, same packets), not scored before
this note was written.

Third launch (r13): identical folders and briefs, model set to Opus explicitly, 16 fresh agents
started together. It is the pre-registered run; the analysis above applies to it unchanged.

## Correction to deviation 1 (added 2026-11-07, after scoring, from the transcript audit)

Deviation 1 was written at 23:31, when 10 of the 16 first-launch agents had reported. It is wrong
about the other six. Final count: 12 agents stopped without writing an answer (one of them also
called ToolSearch); 4 agents of the examples arm broke the tool rule, listed `paquetes/` with Bash
and wrote their five answers. The whole launch was still discarded unscored, as decided at 23:31;
none of its answers is in the repository. Nothing else above changes.
