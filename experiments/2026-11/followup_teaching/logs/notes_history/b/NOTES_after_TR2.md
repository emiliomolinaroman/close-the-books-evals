# Benchmark notes (accounting packets)

## Workflow
1. Read INSTRUCCIONES.md rules, then packet.
2. FIRST run a consistency check on EVERY document before booking entries:
   - Line items sum = subtotal.
   - Tax amount = subtotal x shown rate (round to cents; allow ~1 cent). Check even when subtotal + tax = total ties (real case: total tied, rate x base did not -> `tax_rate_mismatch`).
   - Subtotal + tax = total (else `tax_total_mismatch`; line sum vs total -> `invoice_total_mismatch`).
   - Bank statement: opening + movements = each running balance and closing (else `bank_closing_mismatch`).
   - Payment advice amount = sum of allocations (`payment_allocation_mismatch`).
   - Duplicate references with conflicting totals (`duplicate_reference_conflict`).
   - Schedules/rollforwards (deferred revenue, inventory, lease, DTL, FX) tie. Manufacturing: FG transfer value = material + labor + overhead.
   - Noise that is NOT an inconsistency: differing "Planned Units" across batch docs; payment dated before the invoice.
3. If any mismatch: has_inconsistency true, single best code, short note, entries [], empty balance_sheet sections (verified correct).
4. If consistent: book entries, roll forward balances, check A = L + E.

## Booking conventions (VERIFIED on a graded reconcilable packet)
- Revenue/expense close into Retained Earnings (RE = opening RE + net income); no P&L lines in BS. Correct.
- SALES TAX ON PURCHASE BILLS: when "Input Tax Receivable" is in the allowed account list and the bill shows tax separately, book TWO entries: Dr inventory/expense (subtotal) / Cr AP, and Dr Input Tax Receivable (tax) / Cr AP. Do NOT embed tax in cost (this overrode the "US sales tax embedded" rule even in a sales_tax regime).
- Customer invoice: Dr AR / Cr Sales Revenue (subtotal) and Dr AR / Cr Sales Tax Payable (tax), separate entries.
- Sale of finished goods: book COGS = FG transfer value: Dr Cost of Goods Sold / Cr Finished Goods Inventory, docs [invoice, transfer note]. Correct.
- Payment advice: Dr Cash / Cr AR (customer) or Dr AP / Cr Cash (supplier); docs [payment advice, the invoice/bill it settles]. Correct.
- Payroll summary: Dr Salaries Expense (gross) / Cr Cash and Dr Payroll Tax Expense (employer tax) / Cr Cash, docs [payroll]. Correct.
- Manufacturing chain:
  - Material issue: Dr WIP / Cr Raw Materials; docs [supplier invoice of that material, requisition slip, batch sheet].
  - Direct labor: Dr WIP / Cr Cash; docs [batch sheet, labor record].
  - Overhead accrual: Dr WIP / Cr Accrued Expenses; docs [batch sheet, overhead memo].
  - FG transfer: Dr FG / Cr WIP; docs [batch sheet, transfer note].
  - Scrap of opening stock (lot "OPEN-FG"): Dr Inventory Shrinkage Expense / Cr FG; docs [opening trial balance doc, scrap report].
- Bank statement rows only confirm; no entries from them.

## doc_refs lesson (cost most points)
Grading matches doc_refs exactly. Cite ALL linked documents: the primary doc plus every doc it references or depends on (batch sheet for every batch-related posting, the invoice/bill a payment or issue links to, the transfer note referenced by a customer invoice's contract ref, the opening TB when an opening balance is written down). Order doesn't seem to matter; never cite a bank statement.

## Other
- Opening TB = starting state only; don't journalize it.
- Use the expense label on a vendor bill as debit account.
- Amounts are JSON numbers rounded to cents.
