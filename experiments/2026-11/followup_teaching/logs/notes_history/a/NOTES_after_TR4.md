# Notes for the accounting benchmark (4 packets graded: #1 right, #2 partly wrong, #3 right, #4 fully right)

## doc_refs (graded strictly: right accounts and amount but wrong doc set = miss)
- Cite ALL linked docs in the chain:
  - Supplier invoice with goods receipt: [GRN, invoice] on every line of that bill.
  - Customer invoice with delivery note (same Shipment Ref): [delivery note, invoice] on revenue, sales tax AND COGS.
  - Customer invoice with work order (same customer, approved amount = subtotal): [work order, invoice] on revenue AND sales tax (confirmed).
  - Customer invoice, no delivery note/work order: invoice + any exemption certificate/tax profile docs.
  - Payment advice: [original invoice, payment advice] (receipts and supplier payments) (confirmed).
  - GST supplier bill: [bill, tax regime notice]. Shrinkage: [adjustment note, count sheet].
  - Plain supplier bill (no GRN), loan statement, equipment invoice, payroll, utilities, depreciation rollforward, expense receipt, accrual memo: just that doc (confirmed).
- Opening TB (D001), bank statements, secondary copies, vendor statements: no entries, never cited.

## Tax conventions (confirmed)
- Tax shown separately on a supplier bill (even US "Sales Tax"): Dr Input Tax Receivable for tax, Dr expense/inventory for subtotal (two entries, both Cr AP).
- Sales tax on customer invoice: separate entry Dr AR / Cr Sales Tax Payable.
- India GST same-state bill: split Dr Input CGST / Input SGST Receivable using shown amounts.
- Valid exemption certificate → 0% tax, revenue only.

## Entry conventions (confirmed)
- One entry per debit/credit pair (payroll: Salaries and Payroll Tax separately, Cr Cash; loan payment: principal Dr Loans Payable + Interest Expense separately; equipment: cash part Cr Cash, financed part Cr Notes Payable).
- Loan draw: Dr Cash / Cr Loans Payable.
- Expense receipt (any payment method: cash/card/debit): ONE entry for the receipt total to the named expense (e.g. "Fuel Expense" + "Fuel Incidentals" lines → Fuel Expense total), Cr Cash.
- Supplier bill "Expense Category" field = debit account for subtotal.
- Utility invoice: Dr Utilities Expense / Cr AP for total.
- Service period / accrual memo: Dr named expense / Cr Accrued Expenses for recognized amount.
- Depreciation: use the rollforward's stated Current Charge (even if cost/life differs by a cent); Dr Depreciation Expense / Cr Accumulated Depreciation (shown NEGATIVE in assets).
- COGS = delivery note's stated extended cost. Shrinkage: Dr Inventory Shrinkage Expense / Cr Inventory.
- Healthcare patient invoice: Dr AR / Cr Service Revenue gross.
- Loan statement opening principal not matching opening TB is NOT an inconsistency.
- Bill line qty × unit cost off by cents vs stated line amount: not an inconsistency (unit cost rounded); use line amounts.

## Balance sheet
- Only balance-sheet accounts with nonzero balances. Close net income to Retained Earnings (may be negative). Owner's Equity unchanged unless docs change it.
- Cash should equal bank statement closing when all cash moves are on it — a good cross-check.

## Inconsistency checks (do ALL before posting)
- Invoice lines sum = subtotal; subtotal × rate = tax (round to cents); subtotal + tax = total.
- CGST + SGST = GST.
- Bank statement: opening + rows = each running balance AND = stated closing. Stated closing ≠ last running balance → bank_closing_mismatch (confirmed). Check statement opening vs TB cash.
- Payment advice = sum of allocations (partial payments fine).
- Loan: opening + draw − principal = ending; principal + interest = payment.
- Equipment: cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = adjustment.
- Same reference, different totals (incl. secondary copy, vendor statement) → duplicate_reference_conflict / statement_balance_mismatch.
- Inconsistent output: has_inconsistency true, single most specific code, short note with figures, entries [] and empty BS sections (confirmed).

## Workflow
- Add by hand carefully; re-add every expense group twice (a 0.10 slip happened, caught only by the BS not balancing). If BS doesn't balance, re-sum the P&L groups first.
- Strict JSON only, 2 decimals, no separators.
