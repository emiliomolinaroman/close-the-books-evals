# Benchmark notes (accounting packets)

## Workflow
1. Read INSTRUCCIONES.md rules, then packet.
2. FIRST run a consistency check on EVERY document before booking entries:
   - Line items sum = subtotal.
   - Tax amount = subtotal x shown rate (round to cents; allow ~1 cent). Check this even when subtotal + tax = total ties, because a wrong tax amount can still make the total tie (that was a real case: total tied, rate x base did not -> `tax_rate_mismatch`).
   - Subtotal + tax = total (else `tax_total_mismatch`; line sum vs total -> `invoice_total_mismatch`).
   - Bank statement: opening + movements = each running balance and closing (else `bank_closing_mismatch`).
   - Payment advice amount = sum of allocations (`payment_allocation_mismatch`).
   - Duplicate references with conflicting totals (`duplicate_reference_conflict`).
   - Schedules/rollforwards (deferred revenue, inventory, lease, DTL, FX) tie.
3. If any mismatch: has_inconsistency true, give the specific code(s), a short note, entries [], and empty balance_sheet sections. Verified correct with a single code (the one that best describes the error); don't add extra codes you aren't sure of.
4. If consistent: book entries, roll forward balances, check A = L + E.

## Booking conventions (from the rules; not yet checked against a graded reconcilable packet)
- Opening TB = starting state only; no entries from it.
- Customer invoice with sales tax: Dr AR total split into Cr Service Revenue (subtotal) + Cr Sales Tax Payable (tax). A separate entry for each credit, same doc_ref.
- US sales tax on purchases goes into the expense/asset cost (Dr expense for the total, Cr AP) unless support says it is recoverable.
- Use the expense label shown on a vendor bill as the debit account.
- Cash expense receipt: Dr Expense / Cr Cash (receipt total, or one entry per line if the lines map to different accounts).
- Payment advice for a customer: Dr Cash / Cr AR; for a supplier: Dr AP / Cr Cash. Card/bank transfer both = Cash unless the packet shows separate bank accounts.
- Revenue/expense accounts in the final BS: probably close them into Retained Earnings (net income); check this when the first reconcilable packet is graded.
- Bank statement rows confirm entries made from other docs; they don't create entries themselves.
- Amounts are JSON numbers rounded to cents.
