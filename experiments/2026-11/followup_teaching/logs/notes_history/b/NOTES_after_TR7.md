# Benchmark notes

## Workflow
1. FIRST check every document (most points):
   - Lines = subtotal; tax = subtotal x rate (check even if totals tie: `tax_rate_mismatch`); subtotal+tax != total `tax_total_mismatch`; lines vs total `invoice_total_mismatch`.
   - Bank: opening + movements = each running balance and closing (`bank_closing_mismatch`).
   - Advice = sum of allocations (`payment_allocation_mismatch`); conflicting duplicate refs.
   - Rollforwards tie; FG transfer = material + labor + overhead.
   - Lease (verified): interest = opening x rate/12; principal = payment - interest; ending = opening - principal.
   - Disposal: NBV = cost - acc dep; gain = proceeds - NBV. Equipment: cash + financed = total.
   - Healthcare: patient + insurer due = gross.
   - Retail: gross - returns = net; cash + card = net + tax; batch total - fee = deposit.
   - NOT inconsistencies (verified): differing Planned Units; payment before invoice; batch labor/overhead 0 with separate record; requisition value != qty x cost (use slip); invoice line qty x unit cost off by cents (unit cost rounded); india_gst label without tax; loan statement opening != TB loan (book draw only); depreciation charge a few cents off or not prorated (book stated charge); retail VAT rate not 20% / not shown (use stated tax).
2. Mismatch -> true, one best code, short note, entries [], empty BS sections (verified).
3. Else book, roll forward, check A = L + E; final Cash should equal bank closing.

## Conventions (verified)
- P&L closes to Retained Earnings (may go negative); no P&L lines in BS. Accumulated Depreciation in assets as negative.
- Separate purchase tax + Input Tax Receivable: Dr Inventory/expense (subtotal)/Cr AP and Dr Input Tax Receivable/Cr AP [bill].
- Bill/utility without tax: Dr expense/Cr AP total [bill].
- Customer invoice: Dr AR/Cr Revenue (subtotal); Dr AR/Cr Sales Tax Payable (tax), separate.
- Healthcare: one Dr AR/Cr Service Revenue gross; remittance Dr Cash/Cr AR [remittance, invoice].
- FG sale: Dr COGS/Cr FG at transfer value [invoice, transfer note].
- Payment advice (partial OK): Dr Cash/Cr AR or Dr AP/Cr Cash [advice, linked invoice/bill/rent roll].
- Payroll: Dr Salaries gross/Cr Cash; Dr Payroll Tax Expense/Cr Cash [payroll].
- Manufacturing: Dr WIP/Cr Raw Materials [supplier inv, requisition, batch]; Dr WIP/Cr Cash [batch, labor record]; Dr WIP/Cr Accrued Expenses [batch, memo]; Dr FG/Cr WIP [batch, transfer note]; scrap Dr Inventory Shrinkage/Cr FG [opening TB, scrap report].
- Retail (verified): per sales summary, split EACH tender proportionally into revenue and tax: tender revenue = tender x net/(net+tax) (e.g. tender/1.125), tax = tender - revenue. Four entries: Dr Cash/Cr Sales Revenue, Dr Card Settlement Clearing/Cr Sales Revenue, Dr Cash/Cr Sales Tax Payable, Dr CSC/Cr Sales Tax Payable; plus Dr COGS/Cr Inventory. ALL cite [sales summary, its POS batch report] (batch total = card sales). Settlement: Dr Cash/Cr CSC net deposit [settlement, batch]; fee Dr Maintenance Expense/Cr CSC [batch, settlement] (no fee account -> Maintenance Expense). Batch with no settlement: stays in CSC, no fee entry. Shrinkage Dr Inventory Shrinkage Expense/Cr Inventory [adj note, count sheet]. Depreciation [schedule]. Loan draw [loan stmt]. Equipment: Dr fixed-asset account/Cr Cash and /Cr Notes Payable [equip inv].
- Property mgmt (fully right): rent roll Dr AR/Cr Rental Revenue [roll]; deposit Dr Cash/Cr Security Deposits Payable [notice]; refund Dr SDP/Cr Cash [refund, original notice]; insurance Dr Prepaid Insurance/Cr Cash [notice]; release Dr Insurance Expense/Cr Prepaid [memo, notice]; Dr Depreciation/Cr Acc Dep [FA rollforward only].
- No entries: bank/vendor statements, opening TB, admin memos.
- Unverified: prepaid rent then release; transfer Dr Reserve Cash/Cr Cash; lease Dr ROU/Cr Lease Liability, payment Dr Liability + Dr Interest/Cr Cash, Dr Amortization/Cr ROU; disposal Dr Cash, Dr Acc Dep, Dr Loss/Cr Equipment.
- Missing natural account (e.g. fees): use closest allowed expense; never leave a real cost unbooked.

## doc_refs (graded exactly)
Primary doc plus every doc it explicitly references or pairs with (batch report for sales summary). "Contract Ref" invoice: cite both on revenue, tax AND COGS. Never cite statements.

## Other
Amounts JSON numbers, cents. Untouched opening accounts keep opening values.
