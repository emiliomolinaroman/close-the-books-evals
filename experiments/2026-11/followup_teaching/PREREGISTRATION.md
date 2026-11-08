# Follow-up of 2026-11-08: what teaches the direct answer the citation convention?

Written on 2026-11-08 at 11:50 CET, after a pilot on two packets of the examples split (not in the
test sample; its answers are not scored or used anywhere) and before any session on the test
packets. Nothing below is changed after the run; anything decided later is marked as such.

## Why

In the 2026-11-06 follow-up (results section 1b) three solved examples closed 0.56 [0.42, 0.69] of
the strict entry F1 gap between the direct answer and the code teams. Two questions remain.

1. **A confound** found in a blind review on 2026-11-08: only the code teams' brief told them that
   citations are scored (`prompts/finbalance_task_en.md`, section "Scoring"). The direct-answer
   instructions say what `doc_refs` must hold, not that it is scored.
2. **Other ways a builder would teach the convention** in practice: Anthropic's own journal-entry
   skill (`journal-entry-prep`, finance plugin of `anthropics/knowledge-work-plugins`, used as
   shipped), and a memory the agent writes itself from checked practice, as in Anthropic's "The
   components of agent memory" (2026-11-06).

## Runtime (not the one of 1b)

Headless Claude Code 2.1.319 (`claude -p`), driven by `harness.py` in this folder, which decides
every next step in code. Each session: a fresh context in its own folder, model `claude-opus-5-5`,
tools fixed with `--tools` (Read and Write; the skill arm also has Skill), project settings only,
no MCP servers, auto memory off, at most 40 turns, the subscription login (no API key). Reading
outside the folder needs a permission no one can grant in print mode (checked with a trap before
this was written). Because the runtime differs from 1b (subagents, Claude Code 2.1.316), every arm
is compared only with the control run in this follow-up, and the 1b examples arm is repeated.

## Arms

All on the 40 packets of `experiments/2026-11/sample_40.json` (hidden A), in the 8 groups of 5 of
1b, one session per group and arm. Briefs in `prompts/agent_briefs/teaching_*.md`.

* **C, control.** The 1b control brief word for word, with the new folder.
* **P, told the scoring.** C plus `PUNTUACION.md`: the "Scoring" section of the code teams' brief,
  verbatim, without its last line (about the hidden set). The brief adds "and PUNTUACION.md (how
  answers are scored)".
* **E, three solved examples.** The 1b examples brief and the same three examples.
* **S, Anthropic's skill.** C plus `journal-entry-prep` installed unchanged as a project skill
  (`.claude/skills/`, copy and licence in `prompts/skills/journal-entry-prep/`); the brief says to
  call it with the Skill tool and follow it. Whether it was called is checked in every transcript.
* **Ma, Mb, memory.** C plus `memoria/NOTES.md`, written by the agent itself in a training chain of
  8 packets from the examples split (6 consistent, 2 inconsistent; E's three left out; chain b
  disjoint from chain a; draw in `design.json`). Each step: a fresh session answers one packet; the
  harness scores it and writes the feedback (`src/ctb_evals/finbalance/feedback.py`: entries not
  matched exactly, with document ids and types, inconsistency codes, balance-sheet lines that
  differ); the same session is resumed to read the feedback and update its notes; then everything
  but `memoria/` leaves the folder. The notes are frozen after step 8 and copied into each test
  folder. Test packets never get feedback.

Launch: C, P, E and S together, two sessions at a time per arm, with both training chains running
alongside; then Ma and Mb, four at a time each.

## Outcomes

Primary, for each of P, E, S, Ma and Mb against C: pooled strict entry F1 on the 32 consistent
packets, arm minus C, with a 95% interval from 10,000 paired bootstrap resamples of packets (seed
7); and the gap closed, (F1 arm - F1 C) / (F1 code - F1 C), where F1 code is the mean strict entry
F1 of the eight code teams on the same 32 packets (0.899 before the run), with an interval from the
same bootstrap. That is five comparisons against one control. No correction for multiplicity is
applied; the results say there are five.

Secondary: citation classes; tolerant entry F1; entries missing at least one of the key's documents
(under plus partial); fully right on the 40 packets (paired difference); inconsistency recall and
code accuracy; tokens and list-price cost per packet. For S, the share of sessions that called the
skill. For M, the score of each training step and the size of the notes.

## How the result will be read

Decided now:
* **P:** if P closes 0.25 or more of the gap with its interval above zero, part of the citation gap
  is just being told that citations count, and the article says so. If P closes under 0.10, or its
  interval includes zero, being told does not explain it.
* **E:** a replication. Its gap closed is reported next to the 0.56 of 1b, with no new reading.
* **S, Ma, Mb:** the 1b rule. A gap closed of 0.5 or more with the interval above zero: closes most
  of the gap. Under 0.25: does not close it. In between: partly, with the number.
* **Memory against examples:** Ma and Mb are reported next to E, with what each saw (8 checked
  attempts against 3 solved packets). Not a pre-registered test.
* **Environment:** C is reported next to the 1b control (r13). Not interpreted.

Fully right is underpowered on 40 packets: it is reported, and no conclusion rests on it.

## Handling

* A packet without a parseable answer counts as wrong, as in the scorer.
* A session that stops before writing its answers is not rerun; its missing packets count as wrong
  and are listed. The one exception is a harness failure before the session reached the model,
  which is logged and relaunched.
* Every transcript is audited (`src/ctb_evals/stream_audit.py`): every assistant message from
  `claude-opus-5-5`, only the listed tools, no path outside the session's folder, permission
  denials counted. A session that tried a path outside is reported, and its answers are still
  scored, since the CLI denied the read.
* The answers go unedited to `team_outputs/finbalance/direct/sample40_cli_<arm>/` and are scored
  by `ctb reproduce`.

## What the pilot showed

Two packets of the examples split, one session per arm and a two-step chain, at 11:46 to 11:48: all 8
transcripts clean (Opus 5.5 only, listed tools only, no path outside); the skill was called; the
chain wrote 554 words of notes and the memory session read them. The pilot only checked the
mechanics. No answer of it was scored against the test keys, and nothing was changed after it.
