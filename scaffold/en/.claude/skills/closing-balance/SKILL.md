---
name: closing-balance
description: Closes the period in code: opening balances + journal + proposed adjusting entries = trial balance, which must balance. Use it when the challenge asks for adjusting entries, a balance sheet, a reconciliation or closing statements.
---
The model NEVER adds up. A script (`src/libro.py`) builds the general ledger:
1. Load the opening balances and the journal into the canonical model (cents, normalized account, company, currency).
   Single convention: balance = debit - credit. Check that every journal entry balances (debit = credit) BEFORE anything else.
2. Every finding that implies a correction generates an adjusting entry in code (`src/ajustes.py`): one function per error type,
   with the amount computed from the data (never typed by hand), a reason and refs to the documents. Every adjustment balances.
3. Balance = opening + journal + adjustments, per account (and company). Automatic checks:
   the sum of all balances = 0; assets = liabilities + equity + profit or loss; bank accounts = closing balance of the statement
   (if not, the difference is explained in the reconciliation); subaccounts mapped to the chart of accounts the task statement asks for.
4. Currencies: convert at the rate the policy states for each item (closing rate for monetary items, historical or average rate for the rest)
   and post the exchange difference as a separate entry. Round only at the end, per account.
5. Reconciliation: for every pair of sources that should agree (bank↔books, customer/vendor↔ledger, intercompany A↔B,
   payroll↔payment, subledger↔ledger), a table with matched items, open items with a reason, and the total difference. Whatever does not match
   is NOT forced: it stays open and, if there is a proven error, it goes in as a finding + adjustment.
6. Before delivering: the balance sheet balances, every adjustment has existing refs, and no adjustment touches a fraud finding
   (that is blocked for human review, not "fixed" in the books, unless the task statement asks for it).

7. When the task statement does not say HOW to adjust, use the conventional PGC (Spanish chart of accounts) treatment and say so in the reason (in round 4 all three
   teams lost 10-30% of the balance sheet by not reclassifying suspicious payments):
   - Payment to an unverified IBAN or suspected fraud: the debt is not treated as paid; Dr 555 (suspense account) / Cr 400 (vendors; restores the vendor's balance).
   - Unidentified receipt or payment: 555 until it is applied.
   - Goods or services received without an invoice: Dr 6xx (expenses) / Cr 4009 (vendors, invoices pending receipt).
   - Invoice from an impersonated vendor, or a duplicate already posted: reversing entry of the original (cancel it), never delete.
   - Unposted credit note: Dr 400 / Cr 6xx or 608/609 (purchase returns / purchase rebates) and Cr input VAT.
   - Prepaid expense (insurance, annual licence): 480 (prepaid expenses) for the part not yet accrued.
   - Income received in advance: 485 (deferred income). Accrued expense without an invoice: 6xx / 4009 or 410 (creditors for services).
   - Exchange differences: 668 (loss) / 768 (gain). Revaluation of monetary items at the closing rate.
   - Depreciation: 68x (depreciation expense) / 28x (accumulated depreciation); asset disposal: remove cost and accumulated depreciation, gain or loss to 671/771.
   - Bad-debt provision: 694 (impairment loss) / 490 (allowance for doubtful receivables); IRPF (Spanish personal income tax) withheld from professionals: 4751 (withholdings payable to the tax authority); non-deductible input VAT: added to the expense.
   If the dataset's chart of accounts has a different account for that concept, use the dataset's.
8. Your own tests (perturbation, mutation) write ONLY inside the project folder (data/work/), never to /tmp or to
   parent folders: if the challenge measures safety, writing outside counts as a violation.
