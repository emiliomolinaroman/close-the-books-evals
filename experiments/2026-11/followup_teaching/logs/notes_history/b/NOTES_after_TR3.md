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
   - Noise that is NOT an inconsistency (verified): differing "Planned Units" across batch docs; payment dated before invoice; batch sheet showing labor/overhead 0 while separate labor record/overhead memo exist; requisition issue value not equal to qty x supplier unit cost (use the slip's issue value).
3. If any mismatch: has_inconsistency true, single best code, short note, entries [], empty balance_sheet sections (verified correct).
4. If consistent: book entries, roll forward balances, check A = L + E.

## Booking conventions (VERIFIED on graded packets)
- Revenue/expense close into Retained Earnings (RE = opening RE + net income); no P&L lines in BS.
- PURCHASE BILL TAX (sales tax or VAT): when "Input Tax Receivable" is allowed and the bill shows tax separately, TWO entries: Dr inventory/expense (subtotal) / Cr AP, and Dr Input Tax Receivable (tax) / Cr AP. Docs [bill].
- Customer invoice: Dr AR / Cr Sales Revenue (subtotal) and Dr AR / Cr Sales Tax Payable (tax; also used for VAT output), separate entries.
- Sale of finished goods: COGS = FG transfer value: Dr COGS / Cr FG, docs [invoice, transfer note].
- Payment advice: Dr Cash / Cr AR or Dr AP / Cr Cash; docs [payment advice, invoice/bill settled].
- Payroll: Dr Salaries Expense (gross) / Cr Cash and Dr Payroll Tax Expense (employer tax) / Cr Cash, docs [payroll].
- Manufacturing chain:
  - Material issue: Dr WIP / Cr Raw Materials; docs [supplier invoice of that material, requisition slip, batch sheet].
  - Direct labor: Dr WIP / Cr Cash; docs [batch sheet, labor record].
  - Overhead accrual: Dr WIP / Cr Accrued Expenses; docs [batch sheet, overhead memo].
  - FG transfer: Dr FG / Cr WIP; docs [batch sheet, transfer note].
  - Scrap of opening stock (lot "OPEN-FG"): Dr Inventory Shrinkage Expense / Cr FG; docs [opening TB doc, scrap report].
- Bank statement rows only confirm; no entries from them.

## doc_refs lesson (cost most points)
Grading matches doc_refs exactly. Cite ALL linked documents: the primary doc plus every doc it references (batch sheet for every batch posting, invoice/bill a payment or issue links to, opening TB when an opening balance is written down).
- CUSTOMER INVOICE WITH "Contract Ref" (e.g. FGT-xxxx transfer note): cite [invoice, transfer note] on BOTH the revenue and the sales-tax entries (and COGS). Missing this cost points.
- Order doesn't matter; never cite a bank statement.

## Other
- Opening TB = starting state only; don't journalize it.
- Use the expense label on a vendor bill as debit account.
- Amounts are JSON numbers rounded to cents.
