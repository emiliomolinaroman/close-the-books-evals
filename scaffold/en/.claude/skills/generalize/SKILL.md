---
name: generalize
description: Makes the code work on the hidden benchmark and not just on the visible data. Use it from the first submission if the challenge runs your program on other data, and before freezing in any case.
---
1. A single entry point: `python3 run.py <data> <output>` regenerates the WHOLE submission from scratch, with no prior state and no hard-coded paths.
   No reading data/work from a previous run; no hard-coded ids, amounts, third-party names or dates in the code.
1b. READING: copy `src_base/leer.py` to `src/` and read EVERYTHING with it (leer_tabla, num with detectar_decimal, fecha with detectar_mdy,
   run_protegido). In round 4, 2 of 3 teams scored F1 = 0 on a hidden set because the CSVs came in cp1252 with tabs and
   their run.py crashed opening them. A read failure on ONE file is logged and the rest carry on; it never takes down the submission.
2. Schema detection by content, not by position: find columns by synonyms (fecha/date/data/f_asiento; importe/amount/import;
   debe/cargo/debit; haber/abono/credit; nif/cif/vat/tax_id...) and by the shape of the values (IBAN, NIF, date). Detect the separator and
   the decimal mark (`csv.Sniffer`, comma vs dot by pattern). Dates: try ISO, dd/mm/yyyy, mm/dd/yyyy and break ties with values > 12.
3. FULL POLICY (this is where hidden-set points are lost): for every normative sentence in the policy, implement the rule
   AND ALL ITS EXCEPTIONS even if the visible data does not use them (e.g. "do not post if it is already among the previous month's pending items",
   "tolerance of X €", "unless approved by Y"). Write `src/politica_tabla.md`: verbatim sentence → function → exception → synthetic test.
   A case your code cannot match (unreadable document, new template, truncated description) is NOT a finding: it stays "unmatched" with a reason.
3b. Thresholds and rules: read them from the dataset's policy on every run (regex over the .md); if they are not found, use a reasonable default
   + a warning in the log, never a crash. At the start of run.py, print every parameter read and the sentence it comes from.
4. Perturbation test (in addition to mutation-testing): `src/perturbar.py` creates copies of the data (in data/work/) with reordered columns,
   another date and decimal format, a thousands separator, another field separator (including tab), cp1252 encoding and UTF-8 with BOM, renumbered ids and changed third-party names. run.py must give the same
   findings (modulo the renamed ids). If it changes, something is tied to the form and not to the content.
5. Robustness: every check in try/except with logging; a global timeout; if a source is missing, carry on with the others. Measure run.py's running time.
6. Before freezing: run run.py in a clean folder (copy only run.py + src/ + the data) and validate the output.
7. COVERAGE (what cost the most points with human-written data): write `src/cobertura.py`, which counts across ALL the data (including the data
   without answers) every document type × tax regime × currency × sector. Every cell needs a handler. Write the code in
   layers that combine: document type → base entry; a tax layer per regime (VAT, sales tax, GST with CGST+SGST or IGST...)
   independent of the document type; an independent currency layer. That way "hosting invoice with Indian GST" comes out on its own even if you have never seen it solved.
8. Unconsumed-document detector: after generating the entries, list the accounting-type documents (invoice, payment, statement, adjustment
   memo) that have not produced any entry and have not been classified as a copy, voided or supporting document. Each one is a missing handler
   or a new case: on data without answers, it is your best error signal. The same goes for document amounts that appear in no entry.
9. Invariants on data without answers: the balance sheet balances, closing cash = closing balance of the statement, no account outside the allowed
   list, a number of cases flagged as issues similar to the proportion in the examples. A detector that fires on a case
   whose invariants hold is a suspected false alarm: review it before keeping it.
