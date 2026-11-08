# Benchmark notes (accounting packets)

## Workflow
1. Read rules, then packet.
2. FIRST, check that EVERY document is consistent (most points come from this):
   - Line sum = subtotal; tax = subtotal x rate (~1 cent). Check the rate even when subtotal + tax = total ties (`tax_rate_mismatch`). Subtotal+tax != total -> `tax_total_mismatch`; lines vs total -> `invoice_total_mismatch`.
   - Bank: opening + movements = each running balance and the closing (`bank_closing_mismatch`).
   - Payment advice = sum of allocations (`payment_allocation_mismatch`). Duplicate refs that conflict (`duplicate_reference_conflict`).
   - Schedules/rollforwards tie. Manufacturing: FG transfer = material + labor + overhead.
   - LEASE (verified: caught a real `lease_schedule_mismatch`): interest = opening liability x rate/12; principal = payment - interest; ending = opening - principal. Check the stated ending liability. ROU amortization = ROU/term.
   - Disposal: NBV = cost - acc dep; gain/loss = proceeds - NBV. Depreciation = cost/life months. Equipment invoice: cash + financed = total.
   - Healthcare: patient due + insurer due = gross.
   - NOT inconsistencies (verified): differing "Planned Units"; payment dated before invoice; batch sheet with labor/overhead 0 while a labor record/overhead memo exists; requisition value != qty x cost (use the slip value); "india_gst" label with no tax shown.
3. Mismatch -> has_inconsistency true, single best code, short note, entries [], empty BS sections (verified twice).
4. If consistent: book the entries, roll forward, check A = L + E.

## Booking conventions (verified)
- Revenue/expense close into Retained Earnings (RE = opening + net income); no P&L lines in the BS.
- Purchase tax shown separately and Input Tax Receivable allowed (VAT/GST-type): Dr expense (subtotal)/Cr AP plus Dr Input Tax Receivable/Cr AP. Docs [bill]. (Unverified: under the US sales_tax regime, the rules say embed the tax in the expense, so Dr expense for the total.)
- Bill without tax: Dr expense label/Cr AP (total).
- Customer invoice: Dr AR/Cr Revenue (subtotal) and Dr AR/Cr Sales Tax Payable (tax), as separate entries.
- Healthcare: patient invoice -> ONE entry Dr AR/Cr Service Revenue for the gross amount. Remittance/copay -> Dr Cash/Cr AR, docs [remittance or receipt, invoice].
- Sale of FG: Dr COGS/Cr FG at transfer value, docs [invoice, transfer note].
- Payment advice: Dr Cash/Cr AR or Dr AP/Cr Cash; docs [advice, invoice/bill].
- Payroll: Dr Salaries (gross)/Cr Cash and Dr Payroll Tax Expense/Cr Cash.
- Manufacturing: material Dr WIP/Cr Raw Materials [supplier inv, requisition, batch sheet]; labor Dr WIP/Cr Cash [batch, labor record]; overhead Dr WIP/Cr Accrued Expenses [batch, memo]; FG Dr FG/Cr WIP [batch, transfer note]; scrap of opening stock Dr Inventory Shrinkage Expense/Cr FG [opening TB doc, scrap report].
- Bank statements, vendor statements, opening TB: no entries.
- Unverified plan: rent prepayment Dr Prepaid Rent/Cr Cash, then memo release Dr Rent Expense/Cr Prepaid Rent; transfer Dr Reserve Cash/Cr Cash; loan draw Dr Cash/Cr Loans Payable; equipment Dr Equipment/Cr Cash + Cr Notes Payable; lease Dr ROU/Cr Lease Liability, payment Dr Lease Liability (principal) + Dr Lease Interest Expense/Cr Cash, Dr Lease Amortization Expense/Cr ROU; disposal Dr Cash, Dr Acc Dep, Dr Loss/Cr Equipment.

## doc_refs (cost the most points)
Grading matches doc_refs exactly. Cite the primary doc plus every doc it references (the batch sheet for every batch posting, the invoice/bill a payment links to, the opening TB when an opening balance is written down). An invoice with a "Contract Ref" (transfer note): cite both on the revenue, tax AND COGS entries. Order doesn't matter; never cite statements.

## Other
Amounts are JSON numbers in cents. Keep untouched opening accounts at their opening values.
