---
name: close-check
description: Verification loop for the close. Use it after every change to the pipeline and before every submission to the leaderboard.
---
1. Run `make check`. If it fails, read the error, fix it and run it again (at most 3 rounds, then report).
2. Check the invariants:
   - Every entry balances (debit = credit) and the trial balance balances per company.
   - Total of the period's invoices = movement in the vendor account.
   - No fraud or payment finding has action = auto.
   - Every row in `out/findings.json` has rule, evidence and explanation.
   - The output format matches exactly what the organizers ask for.
3. Run your own benchmark (`python3 practica/score.py ...`) and compare it with the last score. If it drops, revert or explain why.
4. Summarize in three lines: what passes, what fails, next step.
