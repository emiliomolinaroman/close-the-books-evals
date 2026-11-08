# Accounting benchmark notes (8 graded: 7 BS right, doc_refs sometimes off)

## Step 1: check for inconsistency FIRST
- Invoice lines sum = subtotal; subtotal × rate = tax (cents); subtotal + tax = total; CGST + SGST = GST.
- Bank: opening + rows = running balances AND closing (bank_closing_mismatch).
- Payment advice = sum of allocations (partial fine). AR aging remaining = invoice − receipts. Vendor statement open = bill − payments.
- Loan: opening + draw − principal = ending; principal + interest = bank payment.
- Equipment: cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = write-down.
- EVERY inventory rollforward: opening + additions − usage − write-down = ending (inventory_rollforward_mismatch). Check each separately.
- Same reference, different totals → duplicate_reference_conflict / statement_balance_mismatch.
- Inconsistent output: has_inconsistency true, single most specific code, short note with figures, entries [] and empty BS.
- NOT inconsistencies: loan opening ≠ TB; rollforward opening ≠ TB inventory; customer invoice rate ≠ supplier tax notice; manufacturing unit counts differing (planned vs completed units) or issue unit cost ≠ purchase unit cost when values tie (TR8 confirmed fine).

## doc_refs (graded strictly; BS can be right while refs wrong)
- Supplier bill with GRN: [GRN, bill] on every line incl. tax.
- Customer invoice with delivery note (same Shipment Ref): [delivery note, invoice] on revenue, tax AND COGS.
- Customer invoice with work order: [work order, invoice] on revenue and tax.
- Exempt invoice: [invoice, exemption certificate, customer tax profile].
- Payment advice: [original invoice/bill, payment advice].
- Supplier bill w/o GRN but tax notice tied to it: [bill, tax notice].
- Shrinkage: [adjustment note or rollforward, count sheet]. Bad debt: [invoice, AR aging, credit memo].
- MANUFACTURING chain (confirmed TR8): cite the previous-step doc too:
  - Raw material bill: [bill]. Dr Raw Materials Inventory / Cr AP.
  - Issue to WIP: [supplier bill of that material, requisition slip, batch sheet]. Dr WIP / Cr RM.
  - Completion: [batch sheet, FG transfer note]. Dr FG / Cr WIP.
  - Sale invoice referencing FG transfer (Contract Ref = transfer no.): [transfer note, invoice] on revenue AND COGS (Dr COGS / Cr FG at transfer value).
- Plain bill, loan statement, equipment invoice, payroll, utilities, depreciation rollforward, expense receipt, accrual memo: just that doc.
- Never cite/post: opening TB, bank statements, secondary copies, vendor statements, info memos.

## Tax
- Separately shown tax on supplier bill: Dr Input Tax Receivable tax, Dr inventory/expense subtotal (separate entries, Cr AP).
- Tax notice says US purchase sales tax capitalized: Dr Inventory incl. tax.
- Customer invoice tax: separate Dr AR / Cr Sales Tax Payable.
- India GST: same-state CGST+SGST separate entries; different-state IGST.
- Valid exemption → revenue only; no delivery note → no COGS.

## Entries
- One entry per debit/credit pair. Payroll: Salaries and Payroll Tax separately, Cr Cash. Loan payment: Dr Loans Payable + Dr Interest Expense, Cr Cash. Loan draw: Dr Cash / Cr Loans Payable. Equipment: cash part Cr Cash, financed Cr Notes Payable.
- Expense receipt: one entry total, Cr Cash. Bill "Expense Category" = debit account.
- Utility: Dr Utilities Expense / Cr AP. Accrual memo: Dr expense / Cr Accrued Expenses.
- Depreciation: rollforward Current Charge; Cr Accumulated Depreciation (negative in assets).
- COGS = delivery note extended cost (or FG transfer value). Shrinkage: Dr Inventory Shrinkage Expense / Cr Inventory.
- Bad debt: Dr Bad Debt Expense / Cr AR. Healthcare invoice: Dr AR / Cr Service Revenue gross.

## Balance sheet
- Nonzero accounts only (keep untouched opening ones; omit zeroed WIP/FG). Close net income to Retained Earnings. Share Capital/Owner's Equity unchanged unless docs change it.
- Cash = bank closing.

## Workflow
- Add by hand carefully, re-add twice. If BS doesn't balance, re-sum P&L. Strict JSON, 2 decimals.
