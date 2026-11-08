# Notes for the accounting benchmark (5 graded: #1,#3,#4,#5 fully right; #2 partly wrong)

## doc_refs (graded strictly: wrong doc set = miss)
- Cite ALL linked docs in the chain:
  - Supplier invoice with goods receipt: [GRN, invoice] on every line of that bill.
  - Customer invoice with delivery note (same Shipment Ref): [delivery note, invoice] on revenue, tax AND COGS.
  - Customer invoice with work order (approved amount = subtotal): [work order, invoice] on revenue AND tax (confirmed x2).
  - Customer invoice alone: invoice + any exemption certificate/tax profile docs.
  - Payment advice: [original invoice/bill, payment advice] (receipts and supplier payments) (confirmed x2).
  - India GST supplier bill: [bill, tax regime notice]. Shrinkage: [adjustment note, count sheet].
  - Plain supplier bill (no GRN), loan statement, equipment invoice, payroll, utilities, depreciation rollforward, expense receipt, accrual memo: just that doc (confirmed).
- Opening TB (D001), bank statements, secondary copies, vendor statements: no entries, never cited.

## Tax conventions (confirmed)
- Tax shown separately on supplier bill (US sales tax, or plain "GST" unsplit): Dr Input Tax Receivable for tax, Dr expense/inventory for subtotal (two entries, both Cr AP).
- Tax on customer invoice (sales tax or plain unsplit "GST"): separate entry Dr AR / Cr Sales Tax Payable.
- India GST same-state: split CGST/SGST accounts using shown amounts; different-state: IGST.
- Valid exemption certificate → 0% tax, revenue only.

## Entry conventions (confirmed)
- One entry per debit/credit pair (payroll: Salaries and Payroll Tax separately, Cr Cash; loan payment: principal Dr Loans Payable + Interest Expense separately; equipment: cash part Cr Cash, financed part Cr Notes Payable).
- Loan draw: Dr Cash / Cr Loans Payable.
- Expense receipt (any payment method): ONE entry for receipt total to the named expense (e.g. "Fuel Expense" + "Fuel Incidentals" → Fuel Expense total), Cr Cash (confirmed x2).
- Supplier bill "Expense Category" field = debit account for subtotal.
- Utility invoice: Dr Utilities Expense / Cr AP for total.
- Accrual memo: Dr named expense / Cr Accrued Expenses.
- Depreciation: use rollforward's stated Current Charge; Dr Depreciation Expense / Cr Accumulated Depreciation (NEGATIVE in assets).
- COGS = delivery note's extended cost. Shrinkage: Dr Inventory Shrinkage Expense / Cr Inventory.
- Healthcare patient invoice: Dr AR / Cr Service Revenue gross.
- Loan statement opening principal ≠ opening TB is NOT an inconsistency.
- Line qty × unit cost off by cents vs stated line amount: not an inconsistency; use line amounts.

## Balance sheet
- Only balance-sheet accounts with nonzero balances (keep untouched opening accounts). Close net income to Retained Earnings (may be negative). Owner's Equity unchanged unless docs change it.
- Cash should equal bank statement closing when all cash moves are on it — good cross-check.

## Inconsistency checks (do ALL before posting)
- Invoice lines sum = subtotal; subtotal × rate = tax (cents); subtotal + tax = total.
- CGST + SGST = GST.
- Bank statement: opening + rows = each running balance AND = stated closing (else bank_closing_mismatch, confirmed). Statement opening vs TB cash.
- Payment advice = sum of allocations (partial fine).
- Loan: opening + draw − principal = ending; principal + interest = payment.
- Equipment: cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = adjustment.
- Same reference, different totals (secondary copy, vendor statement) → duplicate_reference_conflict / statement_balance_mismatch.
- Inconsistent output: has_inconsistency true, single most specific code, short note with figures, entries [] and empty BS sections (confirmed).

## Workflow
- Add by hand carefully; re-add every group twice. If BS doesn't balance, re-sum P&L first.
- Strict JSON only, 2 decimals, no separators.
