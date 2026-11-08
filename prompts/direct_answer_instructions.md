You are given a packet of accounting documents for one reporting period.
Read the documents, infer the journal entries, and produce the final balance sheet.
Some packets may contain distractor documents, secondary copies, cancellation notes, statements, or other non-posting paperwork.
A small number of packets may be internally inconsistent and cannot be reconciled into a sound answer.
Some postings require multiple documents together, such as one payment applied across several invoices, inter-bank transfers, or internal reclassification memos.
Some invoices and bills include indirect tax such as sales tax, VAT, or GST.
Packets may contain country-specific tax rules, exemption certificates, and jurisdiction profiles.
Packets may contain ASC 606 bundled contracts where invoice line items do not equal the accounting allocation.
Packets may contain fixed asset disposals, deferred tax from book/tax depreciation differences, lease accounting, or lease modifications.
Some documents may be denominated in a foreign currency while the final answer still needs to be expressed in the functional currency for the record.

Rules:
- Use only the allowed account names.
- The opening trial balance is starting state only. Do not turn it into journal entries.
- Do not use 'Opening Balance' as an account name.
- Create entries only for period activity and period-end adjustments supported by the documents.
- Some documents are support-only or distractors and should not create entries by themselves.
- One payment document may settle multiple references, and some allocations may be only partial.
- Some cash movements may be transfers between company-controlled bank accounts and should not create revenue or expense.
- Some entries may be internal corrections or reclassifications with no external counterparty.
- Do not fold indirect tax into revenue, inventory, or expense when the document shows tax separately.
- US sales tax on purchases is embedded in the asset, inventory, or expense cost unless a visible support document says otherwise.
- India GST uses CGST plus SGST for same-state transactions and IGST for different-state transactions.
- Exemption certificates can override the default tax treatment when the certificate is valid for the counterparty and period.
- For ASC 606 bundled contracts, use visible SSP rate cards and performance-obligation schedules; invoice line splits may differ from accounting allocation.
- Implementation revenue is released on acceptance when an implementation acceptance memo supports it.
- Platform or subscription revenue is released ratably only when the schedule supports the release amount.
- For fixed asset disposals, compute net book value from original cost less accumulated depreciation, remove both cost and accumulated depreciation, and record proceeds plus gain or loss.
- For deferred tax, use only visible book depreciation, tax depreciation, tax rates, and deferred tax rollforward support.
- For leases, use visible lease agreements, amortization schedules, payment notices, and modification notices for ROU asset, liability, interest, principal, amortization, and remeasurement entries.
- Use the exchange-rate evidence shown in the packet when a document is denominated in a foreign currency.
- Use only visible rates, SSPs, tax rules, schedules, and support documents; do not invent missing exchange rates, tax rates, SSPs, lease rates, or assumptions.
- Return all journal entries and the final balance sheet in the functional currency shown in the record context.
- If the packet is internally inconsistent, set has_inconsistency to true, choose one or more values from inconsistency_codes, explain briefly in inconsistency_notes, and leave entries as [] and balance_sheet sections empty.
- If has_inconsistency is true, inconsistency_codes must contain at least one key from the allowed list below.
- If the packet is reconcilable, set has_inconsistency to false, set inconsistency_codes to [], and provide the full entries and final balance sheet.
- Use only inconsistency codes from the allowed list below. Do not invent new codes.
- Amounts must be JSON numbers, not strings, and must not contain thousands separators.
- Do not round except to cents for final monetary amounts.
- Return strict JSON only. Do not add markdown or prose.
- The top-level JSON must have exactly these keys: has_inconsistency, inconsistency_codes, inconsistency_notes, entries, balance_sheet.
- Each entry must have doc_refs, debit_account, credit_account, and amount.
- doc_refs must list the document ids that support the posting.
- If one posting depends on multiple documents, include all relevant document ids.
- Use the document ids that are primary evidence for the posting; support-only docs may also be included when needed.
- The final balance sheet must balance: assets = liabilities + equity.
- The balance_sheet object must have exactly these keys: assets, liabilities, equity.

Allowed inconsistency codes:
{
  "invoice_total_mismatch": "Invoice total does not match the visible line items.",
  "bank_closing_mismatch": "Bank statement closing balance does not reconcile with the listed movements.",
  "statement_balance_mismatch": "Statement closing balance does not reconcile with the listed open lines.",
  "payment_allocation_mismatch": "Payment advice amount does not reconcile with the listed invoice allocations.",
  "duplicate_reference_conflict": "Two documents show the same reference with conflicting totals or status.",
  "schedule_rollforward_mismatch": "Schedule opening, additions, and releases do not roll forward to the stated ending balance.",
  "inventory_rollforward_mismatch": "Inventory rollforward does not reconcile from opening through ending balance.",
  "transfer_mismatch": "Inter-bank transfer support does not reconcile between the advice and bank evidence.",
  "reclassification_support_mismatch": "Correction memo details do not reconcile with the linked original posting support.",
  "tax_total_mismatch": "Subtotal, indirect tax, and total do not reconcile on the document.",
  "tax_rate_mismatch": "Shown indirect tax amount does not reconcile with the shown tax rate and basis.",
  "input_tax_mismatch": "Recoverable input tax fields do not reconcile with the underlying bill amounts.",
  "jurisdiction_tax_mismatch": "Jurisdiction-specific tax treatment does not reconcile with the applicable support documents.",
  "tax_exemption_conflict": "Tax exemption certificate evidence conflicts with the invoice tax treatment.",
  "ssp_allocation_mismatch": "ASC 606 allocation does not reconcile transaction price to standalone selling prices.",
  "performance_obligation_release_mismatch": "Performance obligation release evidence does not reconcile to the recognition schedule.",
  "asset_disposal_mismatch": "Fixed asset disposal support does not reconcile cost, accumulated depreciation, NBV, proceeds, and gain or loss.",
  "deferred_tax_rollforward_mismatch": "Deferred tax rollforward does not reconcile the opening liability, current movement, and ending liability.",
  "lease_schedule_mismatch": "Lease amortization schedule does not reconcile payment, interest, principal, and ending liability.",
  "lease_remeasurement_mismatch": "Lease modification support does not reconcile liability remeasurement and equal ROU asset adjustment.",
  "exchange_rate_mismatch": "Exchange-rate support does not reconcile the foreign amount into the stated functional amount.",
  "fx_settlement_mismatch": "Foreign-currency settlement support does not reconcile booked amount, paid amount, and FX difference.",
  "remeasurement_mismatch": "Closing-rate remeasurement does not reconcile the open foreign balance to the stated functional amount."
}

Output JSON shape per record:
{"has_inconsistency": false, "inconsistency_codes": [], "inconsistency_notes": [],
 "entries": [{"doc_refs": ["D003"], "debit_account": "Accounts Receivable", "credit_account": "Service Revenue", "amount": 1250.0}],
 "balance_sheet": {"assets": {}, "liabilities": {}, "equity": {}}}
Inconsistent packet: has_inconsistency true, codes, notes, entries [] and empty balance_sheet sections.
