# Hackathon-day protocol (works for any dataset)

What 62 simulations across 17 challenges show, two of the challenges written by accountants (see experiments/2026-11/practice_rounds/round_notes_es.md in the close-the-books-evals repository): Claude on its own
already scores between 85 and 100%. This template is INSURANCE, not an engine: it prevents zeros on the hidden set, in order of impact:
(1) run.py crashing when it reads a new format; (2) hard-coded parameters; (3) rules without their exceptions; (4) regulations worded
differently; (5) unseen combinations (coverage); and it fixes how to answer a rubric (answer-the-brief).
The rest of the score comes from safe autonomy, auditability and the demo. The protocol aims at that and is deliberately light.

| Phase | Time | What to do | Skill |
| --- | --- | --- | --- |
| 0. Rules | 0:00-0:15 | Task statement and delivery format; ask the organizers: do false positives cost points? how are autonomy and auditability scored? how many submissions? is our code run on the hidden set? does the hidden set use the same regulations? can run.py call Claude? Adapt the paths in the Makefile and the hook | output-contract |
| 1. Explore | 0:15-0:45 | Profile, joins and match %; policy read IN FULL and turned into a sentence → rule → exception table; parameters by structure | explore-data, dirty-data, regulations |
| 2. First solution | 0:45-2:00 | End-to-end run.py reading with src_base/leer.py and wrapped in run_protegido (canonical load, checks from the 6 families, adjustments and balance sheet in code) + validator; first submission | check-catalog, closing-balance |
| 3. Think about the hidden set | 2:00-4:00 | Coverage matrix over ALL the data (including the unanswered data) and composable layers; unconsumed documents; exceptions to every rule with a synthetic test; parameters read and printed; perturbation; mutation | generalize, mutation-testing |
| 4. What the judges score | 4:00-7:00 | Auto / review / blocked statuses with their % (do not block everything); audit_log; close report; a simple dashboard or demo; auditor in a clean context | close-check, auditor |
| 5. Freeze | -1:30 | Last good version tagged in git; fixes only | — |
| 6. Demo | -1:00 | 3 minutes: problem, architecture (the model interprets, the code computes), one blocked case with its evidence, % automated, what production would need | — |

Split for a team of 3: (1) pipeline and run.py, (2) policy → rules → exceptions → tests, (3) demo, report and statuses.

Non-negotiable rules
1. No model-generated figures: every number comes from code.
2. Never force a match: whatever does not match stays "unreconciled" with a reason. Not matching ≠ error.
3. Every output cites existing ids (the validator checks this) and the full chain of linked documents.
4. Fraud and doubtful payments: never automatic. What is safe does get automated, and you state what percentage.
5. No hard-coded ids, amounts or thresholds in the code; everything comes from the data and the policy, on every run (in round 4, the only team that hard-coded a tolerance lost 4 hidden-set findings).
6. Every check isolated (try/except): one failure does not take down the submission.
7. One code or several per case, as the solved examples show, not by intuition. When the task statement gives a literal definition, apply the literal one.
8. In written answers: one final figure per question, no alternatives; what the brief asks for and nothing more (answer-the-brief skill).
