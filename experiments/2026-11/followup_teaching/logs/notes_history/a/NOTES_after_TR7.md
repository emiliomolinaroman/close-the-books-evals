# Accounting benchmark notes (7 graded: 6 fully right, 1 partly wrong)

## Step 1: check for inconsistency FIRST (cheap, saves work)
Check every doc before posting:
- Invoice lines sum = subtotal; subtotal × rate = tax (cents); subtotal + tax = total; CGST + SGST = GST.
- Bank: opening + rows = each running balance AND closing (bank_closing_mismatch).
- Payment advice = sum of allocations (partial fine). AR aging remaining = invoice − receipts. Vendor statement open = bill − payments.
- Loan: opening + draw − principal = ending; principal + interest = bank payment.
- Equipment: cash + financed = total. Payroll: gross + employer tax = cash out.
- Stock count: (system − counted) × unit cost = write-down.
- EVERY inventory rollforward: opening + additions − usage − write-down = ending (inventory_rollforward_mismatch, confirmed TR7). Check each rollforward separately; one may tie, another not.
- Same reference, different totals (secondary copy, vendor statement) → duplicate_reference_conflict / statement_balance_mismatch.
- Inconsistent output: has_inconsistency true, single most specific code, short note with figures, entries [] and empty BS sections (confirmed format).
- NOT inconsistencies: loan opening ≠ TB; rollforward opening ≠ TB inventory; customer invoice rate differing from supplier tax regime notice. (Loan ending principal negative but arithmetic ties: unverified, probably not flagged.)

## doc_refs (graded strictly)
- Supplier bill with GRN: [GRN, bill] on every line incl. tax lines.
- Customer invoice with delivery note (same Shipment Ref): [delivery note, invoice] on revenue, tax AND COGS.
- Customer invoice with work order: [work order, invoice] on revenue and tax.
- Exempt invoice: [invoice, exemption certificate, customer tax profile].
- Payment advice: [original invoice/bill, payment advice].
- Supplier bill with no GRN doc but tax regime notice tied to it (same tax amount): [bill, tax regime notice]. Bills with GRN: no notice.
- Shrinkage: [adjustment note or inventory rollforward, count sheet].
- Bad debt: [original invoice, AR aging, credit memo].
- Plain bill, loan statement, equipment invoice, payroll, utilities, depreciation rollforward, expense receipt, accrual memo: just that doc.
- Never cite/post: opening TB, bank statements, secondary copies, vendor statements, info memos.

## Tax
- Separately shown tax on supplier bill (VAT, US sales tax, unsplit GST): Dr Input Tax Receivable tax, Dr inventory/expense subtotal (separate entries, Cr AP).
- If tax regime notice says US purchase sales tax is capitalized into inventory: Dr Inventory incl. tax (unverified whether one or two entries).
- Customer invoice tax: separate Dr AR / Cr Sales Tax Payable.
- India GST: same-state CGST+SGST (separate entries, shown amounts); different-state IGST.
- Valid exemption → revenue only; exempt invoice without delivery note → no COGS.
- Supplier goods bills → Inventory.

## Entries
- One entry per debit/credit pair. Payroll: Salaries and Payroll Tax separately, Cr Cash. Loan payment: Dr Loans Payable principal + Dr Interest Expense, Cr Cash. Loan draw: Dr Cash / Cr Loans Payable. Equipment: cash part Cr Cash, financed Cr Notes Payable.
- Expense receipt: one entry for total, Cr Cash. Bill "Expense Category" = debit account.
- Utility invoice: Dr Utilities Expense / Cr AP total. Accrual memo: Dr expense / Cr Accrued Expenses.
- Depreciation: rollforward's Current Charge; Cr Accumulated Depreciation (negative in assets).
- COGS = delivery note extended cost. Shrinkage: Dr Inventory Shrinkage Expense / Cr Inventory.
- Credit memo bad debt: Dr Bad Debt Expense / Cr AR. Healthcare patient invoice: Dr AR / Cr Service Revenue gross.

## Balance sheet
- Nonzero balance-sheet accounts only (keep untouched opening ones). Close net income to Retained Earnings. Owner's Equity unchanged unless docs change it.
- Cash should equal bank closing.

## Workflow
- Add by hand carefully, re-add twice. If BS doesn't balance, re-sum P&L. Strict JSON, 2 decimals.
