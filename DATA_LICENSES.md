# Data licences and attribution

This repository's code is MIT-licensed (see [LICENSE](LICENSE)). It does **not** redistribute
either benchmark: `ctb fetch` downloads them from their authors at pinned revisions.

## FinBalance

* Source: <https://github.com/Devansh1105/finbalance>, commit `a1062b7b392eaf53311308c2f63cf748b68bb8cf`.
* Paper: *FinBalance*, arXiv:2606.15949 (EMNLP 2026 Findings).
* Licence: data CC BY 4.0, code Apache-2.0.
* Used here: `data/main`, `data/fresh_seed_20260712/coverage`, `data/fresh_seed_20260712/main`.

## APEX-Accounting

* Source: <https://huggingface.co/datasets/mercor/apex-accounting-harbor>, revision `1662b7e4c3b04b8717f2f723df823e7b6cbe2118`.
* Built by Mercor in partnership with Ramp. Licence: CC BY 4.0.
* The dataset card asks that dev-set results not be reported as APEX-Accounting scores; none are here.

## Derived material in this repository

`team_outputs/` and `results/` contain agent outputs and per-record outcomes that include
account names, amounts and record identifiers derived from the two datasets, and
`team_outputs/apex/` contains answers that quote figures from the APEX world. These derived
files are shared under **CC BY 4.0**, with attribution to the dataset authors above. The
answer keys themselves are not committed; `ctb finbalance build` regenerates them from the
original data.
