---
name: regulations
description: Turns policies, manuals and circulars into parameters and rules the code applies, robust to rewording, new circulars, retroactivity, per-company scope and exceptions to exceptions. Use it whenever there is a normative document in prose.
---
Lesson from the simulations: one team lost 14 hidden-set findings because its code looked for the phrase "where it says … it should read"
and the new circular said "it is reworded … replacing «X» with «Y»". Another lost 4 by hard-coding the public set's tolerance.

1. Parameters by structure, not by phrase:
   - The parameter table, if there is one (| name | value |): the primary source.
   - Amendments: extract pairs of quoted values («…» or "…") inside a clause that mentions a section (\d+(\.\d+)+);
     the first is the old value and the last is the new one, whatever the verb (amends, replaces, new wording, should read, is worded as).
   - Amounts in any format (500,00 euros / 500 € / EUR 500) and percentages; normalize before comparing with the old value.
   - Amendments WITHOUT quotes ("the threshold in section 5.5.1 becomes 600 euros", "the amount set in 3.1.3 is raised to 750 €"):
     for each clause that cites a section, take ALL the amounts/percentages in the clause; the one that matches the current value
     of that section is the old one, the other is the new one. If there is only one, it is the new one.
   - Tables in circulars or annexes (Before | Now, "Parameter table"): parse any markdown table; a row with a parameter name
     and two amounts is an amendment; a complete table replaces the manual's table (repeated values change nothing).
   - Corrigenda: correct the value from the origin (as if it had always said that), not from the corrigendum's date.
   - Effective date not stated in the document ("from its publication in the register"): look for it in any regulation-register CSV.
     Future effective date (effects after the close): the circular exists but does not apply to the period.
   - Circulars that change glossary DEFINITIONS (what counts as a "supply", a "recurring vendor"...) change functions, not thresholds:
     every glossary definition must be a function parameterized by date.
2. Hierarchy in a single algorithm (src/normativa.py), tested with synthetic cases:
   effective date (date of effect, "the following day", retroactive) → scope (all companies or one) → annulled (ex tunc: as if it never
   existed) or repealed (ex nunc: stops applying from its date) → special prevails over general UNLESS there is an express clause
   ("notwithstanding the provisions of …", "also applies to …") → later prevails over earlier.
   The result is a parameter × company × date table that the rest of the code queries with (parameter, company, date of the event).
3. Glossary: definitions (e.g. "recurring vendor", "business day", "amount" with or without VAT) are functions, not text.
4. Precedence between categories: if the policy says "only the first one is reported", apply it at the end, over all the findings for a document.
5. Detector of what was not understood (MANDATORY, with a test): at the end of parsing, count the amounts and percentages in each circular
   that have not been turned into a parameter; if there are any, run.py prints them prominently and writes them to data/work/. In round 5,
   the best team was still losing 13+10 findings to amendments with new formulas that its parser ignored without warning.
   Detector of what was not understood: every normative clause with a number, an amount or a quoted value that no parser has consumed
   goes to `data/work/normativa_no_entendida.txt` and to the run.py log. If the file is not empty, review it before submitting.
   On the hidden benchmark, a circular that was not understood must send the affected findings to review, not make them disappear.
6. If the challenge allows calling a model inside run.py (ask), use the model ONLY to convert the regulations into the JSON of
   the table in step 2, validate it with a schema and compare it with the deterministic parser; if they disagree, the more conservative one wins and a warning is raised.
7. Before freezing: write 3 synthetic circulars with different wording (another amendment formula, a specific scope with an
   express clause, a repeal) and check that the table changes as it should.
