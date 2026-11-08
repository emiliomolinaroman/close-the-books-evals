# The November 2026 study

* `study.json`: arms, teams, splits and settings; `ctb reproduce` reads it.
* `sample_40.json`: the 40 hidden-A packets answered twice in the direct arm (stratified: 32 clean
  across difficulty levels, 8 with a contradiction; seed 99).
* `scaffolds_as_run/v6`, `v7`: the scaffolds exactly as copied into the B and C team workspaces
  (Spanish). `scaffold/` at the repository root holds the later v7.1 in English and Spanish.
* `original_scripts/`: the scripts as they were run (Spanish names, paths of the original
  machine). The package reproduces their outputs exactly; they are kept for the record.
* `followup_examples/`: the pre-registered follow-up of 6 November (direct answers with three
  solved examples): pre-registration, design, workspace builder, token usage and audit.
* `followup_teaching/`: the pre-registered follow-up of 8 November (what teaches the convention:
  scoring section, examples, Anthropic's skill, the agent's own notes), with its harness and logs.
* `practice_rounds/`: notes and scores from rounds 1 to 6 on Claude-written practice challenges,
  which motivated the scaffold. No number in the README comes from them.
