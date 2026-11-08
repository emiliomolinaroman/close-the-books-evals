# Notes for the accounting benchmark (6 graded: #1,#3,#4,#5,#6 fully right; #2 partly wrong)

## doc_refs (graded strictly: wrong doc set = miss)
- Cite ALL linked docs in the chain:
  - Supplier invoice with goods receipt: [GRN, invoice] on every line of that bill (incl. CGST/SGST lines) (confirmed x2).
  - Customer invoice with delivery note (same Shipment Ref): [delivery note, invoice] on revenue, tax AND COGS (confirmed x2).
  - Customer invoice with work order (approved amount = subtotal): [work order, invoice] on revenue AND tax.
  - Customer invoice with exemption: [invoice, exemption certificate, customer tax profile] (confirmed).
  - Payment advice: [original invoice/bill, payment advice] (confirmed x3).
  - India GST supplier bill whose GRN doc is absent but tax regime notice ties to it (same tax amount): [bill, tax regime notice] (confirmed). Bills with GRN doc: don't add the notice.
  - Shrinkage: [adjustment note or inventory rollforward, count sheet] (confirmed).
  - Bad debt write-off: [original invoice, AR aging, credit memo] (confirmed — don't omit the invoice).
  - Plain supplier bill (no GRN), loan statement, equipment invoice, payroll, utilities, depreciation rollforward, expense receipt, accrual memo: just that doc (confirmed).
- Opening TB (D001), bank statements, secondary copies, vendor statements, info memos: no entries, never cited.

## Tax conventions (confirmed)
- Tax shown separately on supplier bill (US sales tax, or plain unsplit "GST"): Dr Input Tax Receivable for tax, Dr expense/inventory for subtotal (separate entries, all Cr AP).
- Tax on customer invoice (sales tax or unsplit GST): separate entry Dr AR / Cr Sales Tax Payable.
- India GST same-state: separate entries for CGST and SGST using shown amounts (Input CGST/SGST Receivable; CGST/SGST Payable); different-state: IGST.
- Supplier goods bills ("Premium Kit", widgets, etc.) → Inventory.
- Valid exemption certificate → 0% tax, revenue only. Exempt invoice without a delivery note → no COGS.
- Customer invoice rate differing from a supplier-specific tax regime notice is NOT an inconsistency.

## Entry conventions (confirmed)
- One entry per debit/credit pair (payroll: Salaries and Payroll Tax separately, Cr Cash; loan payment: principal Dr Loans Payable + Interest Expense separately; equipment: cash part Cr Cash, financed part Cr Notes Payable).
- Loan draw: Dr Cash / Cr Loans Payable.
- Expense receipt: ONE entry for receipt total to the named expense, Cr Cash.
- Supplier bill "Expense Category" field = debit account for subtotal.
- Utility invoice: Dr Utilities Expense / Cr AP for total.
- Accrual memo: Dr named expense / Cr Accrued Expenses.
- Depreciation: use rollforward's stated Current Charge even if cost/life differs by cents; Dr Depreciation Expense / Cr Accumulated Depreciation (NEGATIVE in assets).
- COGS = delivery note's stated extended cost (even if qty × unit cost is off by cents). Shrinkage / rollforward write-down: Dr Inventory Shrinkage Expense / Cr Inventory.
- Credit memo "bad debt writeoff": Dr Bad Debt Expense / Cr AR.
- Healthcare patient invoice: Dr AR / Cr Service Revenue gross.
- Loan statement opening principal ≠ opening TB is NOT an inconsistency. Inventory rollforward opening ≠ TB inventory is fine.

## Balance sheet
- Only balance-sheet accounts with nonzero balances (keep untouched opening accounts). Close net income to Retained Earnings. Owner's Equity unchanged unless docs change it.
- Cash should equal bank statement closing — good cross-check.

## Inconsistency checks (do ALL before posting)
- Invoice lines sum = subtotal; subtotal × rate = tax (cents); subtotal + tax = total; CGST + SGST = GST.
- Bank statement: opening + rows = each running balance AND stated closing (else bank_closing_mismatch).
- Payment advice = sum of allocations (partial fine). AR aging remaining = invoice − receipts.
- Loan: opening + draw − principal = ending; principal + interest = payment.
- Equipment: cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = adjustment; rollforward opening + additions − usage − write-down = ending.
- Same reference, different totals (secondary copy, vendor statement) → duplicate_reference_conflict / statement_balance_mismatch.
- Inconsistent output: has_inconsistency true, single most specific code, short note with figures, entries [] and empty BS sections.

## Workflow
- Add by hand carefully; re-add every group twice. If BS doesn't balance, re-sum P&L first.
- Strict JSON only, 2 decimals, no separators.
