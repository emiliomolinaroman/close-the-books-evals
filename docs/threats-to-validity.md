# Threats to validity

Ordered roughly by how much each could change the conclusions.

## Construct validity: what the benchmarks measure

* **Templated documents.** FinBalance packets are rendered from human-written templates by a
  generator. A parser written against 90 packets generalises to new packets from the same
  generator far better than it would to real invoices and bank statements. This favours the
  code-writing arm, and it is the main reason not to read the results as "code beats reading" in
  general. The hidden splits use another seed, not another generator.
* **Public generator.** The FinBalance generator, its templates and its paper have been public
  since June 2026. A model that has seen them knows how the documents are laid out, which helps a
  parser more than a reader, so it would favour the code arm.
* **"Fully right" is all-or-nothing.** One wrong account on one entry fails a packet even if the
  close is otherwise correct. The secondary metrics (balance sheet exact, entry F1 with and
  without citations) are reported for that reason.
* **APEX is ten tasks in one company world.** 89 criteria, but they cluster in ten tasks; the
  task-clustered SEs (about 6 points) show how little ten tasks pin down.

## Internal validity: could something other than the arm explain the difference?

* **Different scopes of work.** The code teams saw 30 solved examples and could test against
  them, and their task statement said citations are scored; the direct-answer agents saw only
  the specification and the packet. That is the comparison intended (a team building a tool vs a
  model answering), but it is not "the same information, with and without code", and it matters
  most for citations: answering directly, Claude adds the bank statement to entries the key
  supports with one document (the specification allows "support-only docs ... when needed") and
  leaves out one or more of the key's documents (in 198 of 265 cases, one of two). About half of the citation gap goes
  away when extra documents are allowed (RESULTS.md, section 1). The pre-registered follow-up
  (section 1b) ran the direct arm with three solved examples: they closed 0.56 [0.42, 0.69] of
  the citation gap, mostly by dropping the extra bank statement (entries only adding documents 85
  to 9); entries missing one of the key's documents fell less (112 to 90; the programs 15 to 55
  per team). Its limits: 40 packets, three examples against the code teams' 30, run a
  day after the study on another machine and Claude Code version (2.1.316 against 2.1.318). Its
  control cited worse than the study's two direct trials (0.50 vs 0.57 entry F1), so the share
  closed is 0.45 measured against those trials. Fully right moved -2.5 points, which 40 packets
  cannot tell from zero. The pre-registered rule calls a share of 0.5 or more "most of the gap";
  the README reads it as about half, for the reasons above.
* **Scaffold v7 was designed after seeing hidden-A errors.** Its rule about emitting a single
  contradiction code came from team B2's hidden-A result. For v7 only hidden B is a clean test.
* **Public record ids leaked the contradiction code.** In the experiment the public split kept the
  original FinBalance ids (for example `MAIN_NEG_02_BANK_CLOSING_MISMATCH`). Seven of the eight
  teams say in their notes that they checked their detectors against those ids, some only for
  which packets were flagged and others for the codes as well (B2 says it did not use the ids);
  none reads the id in `run.py`. Hidden ids were always neutral and every
  program was re-run on hidden data, so no program could read an answer at test time. But seven
  teams could check their detectors against 15 labelled contradiction packets the direct arm
  never had, and the effect of that on hidden scores was not measured. Public scores are not interpreted.
  The package now anonymises public ids as well.
* **Isolation was by instruction.** Agents were told to stay in their folders and not use the
  network; nothing enforced it. The audit of all 95 transcripts found no tool call touching answer
  keys, other teams' workspaces or the raw datasets, and no forbidden tool in the direct arm.
  Its limits: it matches absolute paths under the experiment root, so relative paths, globs or
  paths built inside code would not show; 48 of the 95 transcripts are from the practice rounds,
  47 from this study; and one team (A2) listed the orchestrating session's folder, which is where
  the shared scratch folder lives.
* **Shared scratch folder.** The audit also found that agents wrote throwaway helper files to a
  scratch folder all agents could see. Six file names were used by more than one agent
  (`dump.py`, `ev.py`, `show.py`, `view.py`, `types.txt`, `res.json`), and team A3 reported that
  another agent overwrote one of its helper scripts while it was working. These were small viewers
  and evaluators each agent wrote for itself; none contains answers, and every final `run.py` is
  self-contained and was re-executed from its own folder. It still means team runs were not
  perfectly independent. `ctb run-team` now gives each team a private `TMPDIR`.
* **Agent effort budget.** Teams were asked to finish in about 60 to 90 tool calls; FinBalance
  teams used 34 to 56. Longer budgets might change both arms.
* **What the scaffold arm received.** The scaffold was copied into the team's workspace, and the
  brief told the team to read `CLAUDE.md` and `PROTOCOLO.md` and to read the skill and agent
  files "when the protocol or the task asks". Teams ran as subagents of one orchestrating Claude
  Code session, whose project was another folder, and the audit shows only Bash and Write calls
  in the scaffold teams: no subagent and no skill was invoked. The result is about a written
  method in the workspace, not about Claude Code's skill, subagent and hook features.

## Statistical conclusion validity

* **Few runs per arm.** Four no-preparation teams and two per scaffold arm. Team-to-team spread
  was 1.3 to 7.9 points, comparable to the arm differences. The packet-level SEs for scaffold
  contrasts hold these specific programs fixed and should not be read as evidence about the
  scaffold. With the team-to-team SD pooled over the three arms, two teams per arm cannot detect
  scaffold effects under about 8 points (v7 on hidden B: -0.3, 95% CI -7.8 to +7.1).
* **The headline gap counts eight programs as fixed.** Counting run-to-run variance between
  teams, the fully-right gap is +5.7 with a 95% CI of -0.4 to +11.8. The eight include the two
  v7 teams, whose scaffold was revised after reading hidden-A errors; without them the gap is
  +5.9 (-0.7 to +12.6), and with the no-preparation teams only it is +7.5 (+1.8 to +13.3). Those
  two cuts were chosen after seeing the results.
* **One direct-answer trial on most packets.** 103 of the 143 packets were answered once. On the
  40 packets answered twice, the trials agreed on 92.5% of packets, so trial-to-trial variance is
  small next to packet-to-packet variance, but it is estimated from 40 packets.
* **The first comparison was underpowered.** The original 40-packet comparison (+12.9 points)
  overstated the gap; on all 143 packets it is +5.7. The 40 packets were a stratified sample on
  which the direct answer happened to do worse. This is reported, not hidden.
* **Multiple comparisons.** Several metrics and splits are reported. The comparison named as
  primary in `study.json` is "fully right, code vs direct, hidden A"; there is no dated
  pre-registration. Counting team variance, that gap is not significant even before any
  correction; the citation F1 gap stays clear under any correction. Treat the rest as
  descriptive.

## External validity

* **One model, one harness, one month.** Claude Opus 5.5 in Claude Code 2.1.318. Other models,
  or the same model with a different agent loop, may behave differently; that is what
  `ctb run-team --model` is for.
* **APEX numbers are not APEX-Accounting scores.** The dataset card asks that dev-set results not
  be reported as such. Our agent had direct file access instead of the official MCP tools, and
  our judges were Claude instead of the official judge; one run per task instead of three.
* **Model judges, not accountants.** Two Claude judges agreeing (177/178) shows consistency, not
  correctness. Both are the same model with the same rubric and the expert answer in front of
  them; judge 1 read Spanish instructions and judge 2 English, with the labels swapped. Agreement
  is informative mainly on the 12 or 13 criteria where the arms differ, and the one disagreement
  is there: it moves the scaffold's APEX advantage from two criteria to one. A human calibration set (an accountant grading a sample of criteria blind) is the
  missing piece; the bundle format in `ctb_evals.apex.judge` is designed so a person can grade
  the same files.

## The 2026-11-08 follow-up (section 1c)

* **Another runtime.** Sections 1 and 1b ran as Claude Code subagents (2.1.318 and 2.1.316); 1c
  runs headless sessions (`claude -p`, 2.1.319) with a different system prompt. Its arms are
  compared only with its own control, run at the same time; the 1b examples arm is repeated
  inside 1c for that reason.
* **Isolation is enforced, not only instructed.** In 1c the tool list, the model and the turn
  limit are command-line flags, and a read outside the session's folder needs a permission that
  print mode cannot grant (checked with a trap file before the run). This is stronger than the
  main study, where isolation was an instruction checked afterwards.
* **The skill is Anthropic's, used as shipped.** `journal-entry-prep` is general month-end
  guidance, written for accruals and manual entries, not for this benchmark, and it refers to a
  `CONNECTORS.md` that is not installed with it. So arm S measures what installing the official
  skill does on this task, not what a skill written for FinBalance could do.
* **The memory learns from the answer key of practice packets.** The feedback shows every key
  entry the agent missed, with document ids and types, for 8 packets of the public examples
  split. Test packets never get feedback, and the notes are frozen before the test. Two chains
  with disjoint packets show how much the result depends on what a chain happened to write; the
  notes after every step are kept in `experiments/2026-11/followup_teaching/logs/`.
* **Five comparisons, one control, no correction for multiplicity.** With five intervals at 95%,
  one could exclude zero by chance; the pre-registered reading uses each interval as it is.

## Relationship to earlier, Claude-written challenges

Rounds 1 to 6 (in `experiments/2026-11/practice_rounds/`) used 15 challenges written by Claude.
They motivated the scaffold but are not evidence about accountant-written data and are not used
in any number in the README.
