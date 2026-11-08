# Notes for the accounting benchmark (one packet graded so far: fully right)

## Conventions confirmed correct
- Opening trial balance (D001) and bank statements with no rows: no entries.
- Vendor invoice: Dr the "Expense Label" account shown on the bill / Cr Accounts Payable, for the full total. Cite only that invoice's doc id.
- Patient invoice (healthcare): Dr Accounts Receivable / Cr Service Revenue for the GROSS charge as one entry (don't split patient vs insurer share). Cite the invoice id.
- One entry per document; doc_refs = [that document id].
- Balance sheet: list only balance-sheet accounts. Close net income (revenue − expenses) into "Retained Earnings" (shown even if there was no opening RE). Keep Owner's Equity at its opening amount unless docs change it.
- Leave out revenue/expense accounts from the balance sheet. Leave out accounts with no balance.

## Checks to run every time (to spot inconsistent packets)
- Sum the invoice lines and compare with the total (invoice_total_mismatch).
- Patient due + insurer due = gross charge.
- Bank statement: opening + movements = closing (bank_closing_mismatch).
- Payment advice amount = sum of allocations; transfers must match on both bank sides.
- Duplicate references with different totals → duplicate_reference_conflict.
- Final check: assets = liabilities + equity.

## Workflow
- Add up carefully by hand (no calculator allowed); check each sum twice.
- Output strict JSON only, numbers rounded to 2 decimal places, no thousands separators.
