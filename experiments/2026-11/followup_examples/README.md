# Follow-up of 6 November 2026: code, or solved examples?

* `PREREGISTRATION.md`: question, arms, outcomes and the reading rule, written before the first
  launch, with two deviations appended as they happened and one later correction to the first.
* `design.json`: the three solved examples drawn and the eight groups of five packets.
* `build_workspaces.py`: rebuilds the 16 folders from `work/` (run after `ctb reproduce`).
* Briefs: `prompts/agent_briefs/direct_followup_control.md` and `direct_followup_examples3.md`
  (group 0; the other groups differ only in the folder name and the five file names, from
  `design.json`). The machine-specific folder prefix is shortened to `<root>`.
* Answers, unedited: `team_outputs/finbalance/direct/sample40_trial3` (control) and
  `sample40_examples3` (three solved examples), from the third launch on Claude Opus 5.5;
  `sample40_sonnet_control` and `sample40_sonnet_examples3` from the second launch, which ran on
  Claude Sonnet 5.5 by mistake and is reported apart.
* `audit.json`: per-transcript tools, model, Claude Code version, tokens and isolation check for
  all 48 transcripts of the three launches (paths shortened to `<root>`). `runs.csv`: token usage
  of the two scored launches. The transcripts themselves are not published.

Launches, all on 2026-11-06 (CET):

| Launch | Started | Model | What happened | Used for |
|---|---|---|---|---|
| r11 | 23:29 | Claude Sonnet 5.5 | No Glob tool in that Claude Code build; agents could not list their packets. 12 of 16 stopped without an answer (one also called ToolSearch); 4 (all with examples) broke the tool rule, listed the folder with Bash and answered | Nothing (discarded unscored; its answers are not in the repository) |
| r12 | 23:32 | Claude Sonnet 5.5 | All 80 answers; Read and Write only | Within-Sonnet comparison, reported apart |
| r13 | 23:39 | Claude Opus 5.5 | All 80 answers; Read and Write only; every path inside the agent's own folder | The pre-registered test |

`ctb reproduce` scores r12 and r13 and writes section 1b of `results/RESULTS.md`.

All transcripts ran in Claude Code 2.1.316 (the study used 2.1.318).

The pre-registration has no external timestamp. Its SHA-256 at each stage, as reported to the
author at the time: `05089675a3e4177852aaec21b79bbab447fda5df244a0103ba21cf67a59fc294`
(23:29, before the first launch), `ad3e4fc0cfdf148e280aeafe6351057521b562f34d460911b042e75f8d5faf50`
(23:38, with both deviations, before the third launch).
