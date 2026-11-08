# Follow-up of 8 November 2026: what teaches the direct answer the citation convention?

* `PREREGISTRATION.md`: question, arms, outcomes and the reading rule, written after a two-packet
  pilot on packets outside the test sample and before any session on the test packets. No
  deviation.
* `design.json`: the groups (those of 1b), the three solved examples and the two memory chains.
* `build_workspaces.py`: rebuilds every session folder from `work/` (run after `ctb reproduce`).
  `PILOT=1` builds the pilot instead.
* `harness.py`: runs the sessions with `claude -p` and decides every next step in code (test arms,
  training chains, seeding the notes, audit, collecting answers).
* Briefs: `prompts/agent_briefs/teaching_*.md`. The skill: `prompts/skills/journal-entry-prep/`
  (Anthropic's, unchanged, Apache 2.0, with its source commit).
* Feedback given in training: `src/ctb_evals/finbalance/feedback.py`. Transcript audit:
  `src/ctb_evals/stream_audit.py`.
* `logs/`: `audit.json` (all 80 sessions: models, tools, paths, skills, denials, version, cost),
  `runs.csv` (tokens and list-price cost per session), `tren_a_steps.json` and
  `tren_b_steps.json` (each practice step), `NOTES_a.md` and `NOTES_b.md` (the frozen notes the
  memory arms read) and `notes_history/` (the notes after every step). The transcripts and the
  feedback files are not published: they contain packet text and answer keys of the examples
  split.
* Answers, unedited: `team_outputs/finbalance/direct/sample40_cli_<arm>/`.

Run, all on 2026-11-08 (CET), Claude Code 2.1.319, Claude Opus 5.5 throughout, subscription login
(`apiKeySource: none`):

| Step | Time | What | Sessions |
|---|---|---|---|
| Isolation trap | 11:46 | A session asked to read a file inside and one outside its folder: inside read, outside denied by the CLI | 1 (not part of the study) |
| Pilot | 11:46 to 11:48 | Two packets of the examples split, every arm and a two-step chain; mechanics only, nothing scored against test keys | 8 |
| Pre-registration | 11:49:56 | SHA-256 `0e3d8a7f2ea4ede78a5b71d3a4ffafba125f208832ac883c45685d2b0f8cc646` | |
| Phase 1 | 11:50 to 11:59 | Control, scoring, examples and skill arms (two sessions at a time per arm), with both training chains alongside | 32 + 32 |
| Phase 2 | 11:59 to 12:03 | Both memory arms, four at a time each | 16 |

All 80 sessions are clean: every assistant message from `claude-opus-5-5`, only the listed tools,
no path outside the session's folder, no permission denial. The skill was called in 8 of 8
sessions of its arm. `ctb reproduce` scores the answers and writes section 1c of
`results/RESULTS.md`.

The pre-registration has no external timestamp. Its hash, as reported to the author when it was
written, is the one above.
