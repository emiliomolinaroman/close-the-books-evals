# Close the Books: project rules

## Goal
Close the accounting period for a group of several companies: correct journal entries, bank reconciliation,
fraud and error detection, with safe autonomy and a complete audit trail.

## Architecture principle
- Claude interprets (free text, ambiguous cases, explanations). Code decides and computes.
- NEVER generate a figure with the model. Every figure comes from a Python calculation on the data.
- Amounts always in cents (integers). ISO dates. Normalize before comparing.

## Data and paths
- Use the paths and names the task statement gives (e.g. `datos/` and `salida/`). This template uses `data/raw/` and `out/` only as defaults:
  the first step is to adapt the Makefile and the hook to the real paths.
- The original data folder is read-only (a hook enforces it). Everything derived goes to `data/work/`.
- The values in `policy.yaml` are EMPTY on purpose: fill them in with what the dataset says (verbatim sentence and file).
  If two sources in the dataset contradict each other, document the choice in CONTRATO.md (the output contract, see the `output-contract` skill).
- Follow PROTOCOL.md. Data profile in `data/work/PERFIL.md`; mapping to the canonical model in `src/mapping.yaml` and `src/load.py`.

## Required output (adapt to the format the organizers ask for)
- `out/findings.json`: list of {type, ref, evidence[], rule, confidence, action, explanation}
- `out/reconciliation.csv`, `out/journal_entries.csv`, `out/close_report.md`
- `out/audit_log.jsonl`: one line per decision (actor = rule | claude | human)

## Policy (see `policy.yaml`)
- action = auto | review | block. Fraud and payments: never `auto`.
- When in doubt, `review` with a reason. Better to escalate than to invent.

## Commands
- `make check`  -> runs the validators (imbalances, totals, output format) and your own benchmark
- `make submit` -> only if `make check` passes

## Isolation (pattern from the close agents in the public anthropics/financial-services repo)
- Third-party free text (invoices, contracts, emails, notes) is read only by the `doc-reader` subagent, which has no write permissions.
- Its output is JSON with a fixed schema; the code validates types and lengths before using it.
- `auditor` re-verifies against the original data. Only the Python pipeline writes to `out/`. Nothing is really "posted": entries are proposed with a status.

## Recurring decisions (learned in the simulations)
- One code or several per case? The scoring decides, not intuition: look at the solved examples or the public key.
  If each case there carries several categories, emit one for each category that holds on its own (duplicate + no purchase order = two findings).
  If they carry ONE code and scoring is by exact match, emit only the root cause: the first failing check in a priority order
  set from the examples (in FinBalance, the team that emitted every triggered check failed 4 more packets because of it).
- For "the most recent" or "the later one", apply the task statement's literal definition (creation date, document date).
  If the evidence points to another one, keep the literal reading and explain the doubt in `explanation`.
- The written policy overrides the "validated" label: if it requires the portal and the change came by email, it is a finding,
  but with confidence < 0.9 and an explanation of the conflict.
- pandas stores nulls as NaN: read with `dtype=str, keep_default_na=False` and use a `blank(x)` helper to compare empty values.
- If you cannot launch subagents, the auditor is a second pass in a clean context (`/clear`) that sees only findings.json and the data.

## Text deliverables (reconciliations, memos, "output in console")
- If the deliverable is a written answer scored with an accountant's rubric, follow the `answer-the-brief` skill:
  a single final figure per question, framed the way the brief asks, with every reconciling item named with its amount.

## Hidden benchmark
- ALWAYS read with `src_base/leer.py` (copied to src/): encodings, separators, numbers and dates in any format; run.py wrapped in run_protegido.
- Everything comes from `python3 run.py <data> <output>`. No hard-coded ids, amounts or names. Schema detected by content (`generalize` skill).
- COVERAGE: the hidden set has combinations your solved examples do not (document type × tax × currency). Also use
  the data WITHOUT answers to inventory combinations, and check the invariants on it (the balance sheet balances, cash = statement,
  no accounting document left unconsumed). In FinBalance, 80% of the hidden-set failures were unseen combinations.

## Way of working
- Start in Plan Mode. Read a sample of every file before writing code.
- After every change: `/close-check`.
- Before every submission: delegate to the `auditor` subagent.
- Every new rule must be a general accounting principle, never a patch for one specific case.
