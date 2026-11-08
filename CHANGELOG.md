# Changelog

## 1.3.0 (2026-11-08)

A second pre-registered follow-up with new agent runs; no earlier output, grade or number changed.

* Follow-up (`experiments/2026-11/followup_teaching/`, RESULTS.md section 1c): the 40 sample
  packets in six arms, 80 headless Claude Code sessions (`claude -p`, Claude Opus 5.5), every
  next step decided by a harness in code. Share of the citation gap closed against the same
  control: notes the agent wrote itself after 8 practice packets checked by the scorer 0.90
  [0.77, 1.02] and 1.03 [0.95, 1.10] (two chains; entry F1 with citations 0.86 and 0.91, code
  teams 0.90); three solved examples, repeated, 0.57 [0.41, 0.71] (0.56 in 1b); being told that
  citations are scored, which only the code teams' brief said, 0.00 [-0.25, 0.19]; Anthropic's
  `journal-entry-prep` skill as shipped -0.05 [-0.25, 0.10], called in 8 of 8 sessions. Fully
  right with the notes +12.5 and +15.0 points (underpowered, pre-registered as such). No
  deviation; all 80 sessions clean.
* README finding 1 rewritten: the citation gap comes from learning from checked practice, not from
  writing code. The confound found in review (only the code teams were told that citations are
  scored) is tested and does not explain it.
* New: `ctb_evals.finbalance.feedback` (expected, given and where, for one answer),
  `ctb_evals.stream_audit` (audit of `claude -p` stream-json transcripts) and their tests; the
  reading rule of the pre-registration as code (`report.teaching_reading`), tested at its edges.
* Anthropic's `journal-entry-prep` skill vendored unchanged under `prompts/skills/` with its
  licence and source commit.
* `.gitignore` also ignores any `Privado - no publicar/` folder.
* Two-sided p-values are rounded to 12 decimals: `NormalDist().cdf` uses the platform's `erf`, whose
  last bits differ between macOS and Linux, and the CI check that `results/` is unchanged caught it
  (14 p-values moved by less than 5e-13; no reported number changed).

## 1.2.0 (2026-11-06)

A pre-registered follow-up with new agent runs; no earlier output, grade or number changed.

* Follow-up (`experiments/2026-11/followup_examples/`, RESULTS.md section 1b): the 40 sample
  packets answered again by 16 fresh Claude Opus 5.5 agents, 8 with the trial-2 brief and 8 with
  three solved examples added. Entry F1 with citations 0.50 to 0.72 (code teams 0.90 on the same
  packets): +0.22 [+0.17, +0.28], closing 0.56 [0.42, 0.69] of the citation gap. Entries only
  adding documents 85 to 9; entries missing one of the key's documents 112 to 90 (programs 15 to
  55); fully right -2.5 [-11.1, +6.1]. Two deviations, recorded as they happened: the first
  launch had no Glob tool and was discarded unscored (12 agents stopped, 4 broke the tool rule);
  the second ran on Claude Sonnet 5.5 and is reported apart (+0.33 [+0.27, +0.39]).
* Bank-statement convention counted on the whole public release: all 1,706 records have one and
  none of the 18,704 key entries cites it (`study.bank_statement_convention`).
* Correction: the FinBalance figure of 52% is document-reference mismatches on expected postings
  for one model (Gemini 3 Flash) on the authors' 143-record compact split, not "across their six
  models"; their evidence-only condition lowers it by 26 points.
* Practice-round notes: the APEX figure for Opus 4.8 is marked as unsourced (it is used nowhere).
* CI also fails if `ctb reproduce` writes a file under `results/` that is not committed.

## 1.1.0 (2026-11-06)

Review before publication. No team output, no grade and no headline number changed; every new
figure is computed by `ctb reproduce` from the committed outputs.

* Citation taxonomy (`ctb_evals.finbalance.citations`): for entries with the right accounts and
  amount, how `doc_refs` differ from the key. Answering directly, every citation shares at least
  one document with the key's; it adds the bank statement (294 of 320 extra documents), leaves
  documents out (265 entries, 198 of them one of two), or both (68).
  New "cites at least the key's documents" F1: 0.73 vs 0.91, gap +0.18 [+0.15, +0.22], against
  +0.34 for the strict F1.
* Fully-right gap with run-to-run variance between teams: 95% CI [-0.4, +11.8]. Sensitivity
  without the v7 teams and with no-preparation teams only.
* Scaffold contrasts with the team-to-team SD pooled over arms and a t interval
  (`stats.pooled_team_contrast`): v7 vs no preparation on hidden B, -0.3 [-7.8, +7.1].
* Cost at list prices, all token types, from `study.json` (`list_prices_usd_per_mtok`).
* Corrections: seven of eight teams, not two, checked their detectors against the leaked public
  ids (some only which packets were flagged); the scaffold was a written method the teams read (no subagent or skill calls); the audit's
  limits; team-to-team spread 1.3 (not 0.5) to 7.9 points; judge languages.
* CI now also fails if `results/per_record/` changes.

## 1.0.0 (2026-11-06)

* `ctb` package: deterministic FinBalance splits identical to the experiment, exact scorer with
  per-record outcomes, network-blocked sandbox for `run.py`, statistics (paired, clustered and
  team-level SEs, bootstrap, power), blind APEX judging, transcript audit, report generator,
  optional Claude Agent SDK runner with enforced isolation.
* Direct-answer baseline extended from 40 to all 143 hidden-A packets; the headline gap on fully
  right packets moved from +12.9 to +5.7 points. Two more no-preparation teams (A3, A4).
* Public record ids anonymised (the originals revealed the contradiction code).
* Datasets pinned by commit and checksummed; nothing redistributed.
* Scaffold translated to English; the exact v6 and v7 scaffolds the teams received are kept in
  `experiments/2026-11/scaffolds_as_run/`.

## 0.1.0 (2026-11-05)

* First write-up: 6 code-writing teams, 40-packet direct-answer comparison, APEX blind judging.
