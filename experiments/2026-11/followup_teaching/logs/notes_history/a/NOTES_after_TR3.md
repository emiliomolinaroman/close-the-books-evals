# Notes for the accounting benchmark (3 packets graded: #1 right, #2 partly wrong, #3 right)

## doc_refs (graded strictly: right accounts and amount but wrong doc set = miss)
- Cite ALL linked docs in the chain:
  - Supplier invoice with goods receipt: [GRN, invoice] on every line of that bill.
  - Customer invoice with delivery note (same Shipment Ref): [delivery note, invoice] on revenue, sales tax AND COGS.
  - Customer invoice, no delivery note: invoice + any exemption certificate/tax profile docs.
  - Payment advice: [original invoice, payment advice] (receipts and supplier payments).
  - GST supplier bill: [bill, tax regime notice]. Shrinkage: [adjustment note, count sheet].
  - Loan statement, equipment invoice, payroll, utilities, depreciation, expense receipt: just that doc.
- Opening TB (D001) and bank statements: no entries, never cited.

## Tax conventions
- Tax shown separately on a supplier bill (even US "Sales Tax"): Dr Input Tax Receivable for tax, Dr Inventory/expense for subtotal.
- Sales tax on customer invoice: separate entry Dr AR / Cr Sales Tax Payable.
- India GST same-state bill: split Dr Input CGST / Input SGST Receivable using shown amounts.
- Valid exemption certificate → 0% tax, revenue only.

## Entry conventions (confirmed)
- One entry per debit/credit pair (payroll: Salaries and Payroll Tax separately, Cr Cash; loan payment: principal Dr Loans Payable + Interest Expense separately; equipment: cash part Cr Cash, financed part Cr Notes Payable).
- Loan draw: Dr Cash / Cr Loans Payable.
- COGS = delivery note's stated extended cost.
- Shrinkage: Dr Inventory Shrinkage Expense / Cr Inventory.
- Depreciation: Dr Depreciation Expense / Cr Accumulated Depreciation (shown NEGATIVE in assets).
- Vendor invoice (non-goods): Dr the "Expense Label" account / Cr AP for total.
- Healthcare patient invoice: Dr AR / Cr Service Revenue gross.
- Loan statement opening principal not matching opening TB is NOT an inconsistency.

## Balance sheet
- Only balance-sheet accounts with nonzero balances. Close net income to Retained Earnings (may be negative). Owner's Equity unchanged unless docs change it.

## Inconsistency checks (do ALL before posting)
- Invoice lines sum = subtotal/total; subtotal × rate = tax; subtotal + tax = total.
- CGST + SGST = GST.
- Bank statement: opening + rows = each running balance AND = stated closing. A stated closing that differs from the last running balance → bank_closing_mismatch (confirmed correct). Also check the statement's opening against the TB cash.
- Payment advice = sum of allocations (partial payments fine).
- Loan: opening + draw − principal = ending; principal + interest = payment.
- Equipment: cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = adjustment.
- Same reference, different totals → duplicate_reference_conflict.
- Inconsistent output: has_inconsistency true, single most specific code, short note with the figures, entries [] and empty BS sections (confirmed accepted).
- Final: assets = liabilities + equity.

## Workflow
- Add by hand carefully, double-check each sum. Strict JSON only, 2 decimals, no separators.
