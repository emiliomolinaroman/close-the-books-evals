---
name: output-contract
description: Pins down the exact delivery format, creates a validator and makes a first trivial valid submission. Use it in the first hour, before building rules.
---
1. Copy the organizers' delivery specification verbatim into `CONTRATO.md` (file names, fields, types,
   allowed values, categories). If anything is ambiguous, write it down as a question and pick the most likely reading.
2. Write `src/validate.py`: it checks the schema, types, allowed categories, that every cited id exists in the data,
   that there are no duplicates (type, ref), and that every row has rule, evidence and explanation. It exits with code 1 if anything fails.
3. Generate a trivial valid submission (for example, an empty list or one safe finding) and upload it to confirm the format.
4. From here on, no submission without passing `validate.py` (the hook enforces it).
