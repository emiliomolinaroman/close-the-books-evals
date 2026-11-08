# Benchmark notes (accounting packets)

## Workflow
1. Read rules, then packet.
2. FIRST consistency-check EVERY document:
   - Line items sum = subtotal; tax = subtotal x rate (~1 cent). Check rate even when subtotal + tax = total ties (real case -> `tax_rate_mismatch`).
   - Subtotal + tax = total (`tax_total_mismatch`); line sum vs total -> `invoice_total_mismatch`.
   - Bank statement: opening + movements = running balances and closing (`bank_closing_mismatch`).
   - Payment advice = sum of allocations (`payment_allocation_mismatch`).
   - Duplicate refs with conflicting totals (`duplicate_reference_conflict`).
   - Schedules/rollforwards tie. Manufacturing: FG transfer = material + labor + overhead.
   - Healthcare: patient due + insurer due = gross charge.
   - NOT inconsistencies (verified): differing "Planned Units" across batch docs; payment dated before invoice; batch sheet showing labor/overhead 0 while separate labor record/overhead memo exist; requisition issue value != qty x unit cost (use slip value); "india_gst" regime label when docs show no tax (just book without tax).
3. If mismatch: has_inconsistency true, single best code, short note, entries [], empty BS sections (verified).
4. If consistent: book entries, roll forward, check A = L + E.

## Booking conventions (VERIFIED on graded packets)
- Revenue/expense close into Retained Earnings (RE = opening RE + net income); no P&L lines in BS.
- PURCHASE BILL TAX: when "Input Tax Receivable" allowed and tax shown separately, TWO entries: Dr expense/inventory (subtotal) / Cr AP and Dr Input Tax Receivable / Cr AP. Docs [bill].
- Vendor bill without tax: one entry Dr Expense Label account / Cr AP (total). Docs [bill].
- Customer invoice: Dr AR / Cr Sales Revenue (subtotal) and Dr AR / Cr Sales Tax Payable (tax), separate entries.
- Healthcare clinic (verified fully right): patient invoice -> ONE entry Dr AR / Cr Service Revenue for GROSS charge, docs [invoice] (don't split patient/insurer). Insurer remittance -> Dr Cash / Cr AR (paid amount), docs [remittance, invoice]. Copay receipt -> Dr Cash / Cr AR, docs [receipt, invoice].
- Sale of FG: Dr COGS / Cr FG = transfer value, docs [invoice, transfer note].
- Payment advice: Dr Cash / Cr AR or Dr AP / Cr Cash; docs [advice, invoice/bill settled].
- Payroll: Dr Salaries Expense (gross) / Cr Cash and Dr Payroll Tax Expense / Cr Cash, docs [payroll].
- Manufacturing:
  - Material issue: Dr WIP / Cr Raw Materials; docs [supplier invoice, requisition slip, batch sheet].
  - Direct labor: Dr WIP / Cr Cash; docs [batch sheet, labor record].
  - Overhead: Dr WIP / Cr Accrued Expenses; docs [batch sheet, overhead memo].
  - FG transfer: Dr FG / Cr WIP; docs [batch sheet, transfer note].
  - Scrap of opening stock ("OPEN-FG"): Dr Inventory Shrinkage Expense / Cr FG; docs [opening TB doc, scrap report].
- Bank statements, vendor statements, opening TB: no entries (vendor statement showing bill outstanding just confirms AP stays open).

## doc_refs lesson (cost most points)
Grading matches doc_refs exactly. Cite primary doc plus every doc it references (batch sheet for every batch posting, invoice/bill a payment links to, opening TB when an opening balance is written down).
- Customer invoice with "Contract Ref" (e.g. FGT transfer note): cite [invoice, transfer note] on revenue, sales-tax AND COGS entries.
- Order doesn't matter; never cite bank/vendor statements.

## Other
- Opening TB = starting state only.
- Amounts JSON numbers, cents.
- Keep untouched opening accounts in BS at opening value.
