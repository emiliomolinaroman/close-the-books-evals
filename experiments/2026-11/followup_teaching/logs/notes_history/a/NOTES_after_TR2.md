# Notes for the accounting benchmark (2 packets graded: #1 fully right, #2 partly wrong)

## doc_refs (graded strictly: right accounts and amount but wrong doc set = miss)
- Cite ALL linked docs in the chain, not just the main one:
  - Supplier invoice with a goods receipt: [GRN doc, invoice doc] on every line of that bill.
  - Customer invoice with a delivery note (same Shipment Ref): [delivery note, invoice] on revenue, sales tax AND COGS entries.
  - Customer invoice with no delivery note: cite invoice + any exemption certificate/tax profile docs.
  - Payment advice: [original invoice doc, payment advice doc] (both customer receipts and supplier payments).
  - GST supplier bill: [bill, tax regime notice]. Shrinkage: [adjustment note, count sheet].
  - Loan statement, equipment invoice, payroll, utilities, depreciation: just that doc.
- Opening TB (D001) and bank statements: no entries, never cited.

## Tax conventions
- Sales tax shown separately on a supplier bill (even "Sales Tax" label, US-style): Dr Input Tax Receivable for the tax, Dr Inventory/expense for the subtotal — do NOT embed it in the cost (the grader expected separate input tax).
- Sales tax on customer invoice: separate entry Dr AR / Cr Sales Tax Payable.
- India GST same-state bill (backed by tax regime notice): split Dr Input CGST Receivable and Dr Input SGST Receivable using the amounts shown; subtotal to Inventory if it is a stock SKU.
- Exemption certificate valid → invoice at 0% tax, revenue only.

## Other entry conventions (confirmed correct)
- Split multi-part docs into one entry per debit/credit pair (e.g., payroll: Salaries and Payroll Tax separately, both Cr Cash; loan payment: principal Dr Loans Payable and Interest Expense separately; equipment: cash part Cr Cash, financed part Cr Notes Payable).
- Loan draw: Dr Cash / Cr Loans Payable.
- COGS from the delivery note's stated extended cost (even if unit×qty differs by a cent from rounding).
- Shrinkage: Dr Inventory Shrinkage Expense / Cr Inventory, adjustment note amount.
- Depreciation: Dr Depreciation Expense / Cr Accumulated Depreciation; show Accumulated Depreciation as a NEGATIVE number in assets (accepted).
- Vendor invoice (non-goods): Dr the expense label account / Cr AP for the total.
- Healthcare patient invoice: Dr AR / Cr Service Revenue gross, one entry.
- Loan statement opening principal not matching the opening TB is not an inconsistency; just post the period activity.

## Balance sheet
- Only balance-sheet accounts with nonzero balances. Close net income into Retained Earnings (can go negative). Owner's Equity unchanged unless docs change it.

## Checks to run every time (inconsistency detection)
- Invoice lines sum = subtotal; subtotal × rate = tax (round to cents); subtotal + tax = total.
- CGST + SGST = GST amount.
- Bank statement: opening + rows = closing; check each running balance.
- Payment advice = sum of allocations (partial payments are fine, not an inconsistency).
- Loan: opening + draw − principal = ending; principal + interest = bank payment.
- Equipment: paid cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = adjustment.
- Duplicate references with different totals → duplicate_reference_conflict.
- Final: assets = liabilities + equity.

## Workflow
- Add by hand carefully, double-check each sum. Strict JSON only, 2 decimals, no separators.
