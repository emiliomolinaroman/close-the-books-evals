# Challenge APEX: close requests written by accountants

A simulated hackathon. The requests, the data and the correct answers were written by real accountants
(the APEX-Accounting benchmark by Mercor with Ramp). Company: Sterling, Marsh & Associates LLP, a Philadelphia law
firm (fictional), December 2024 close.

- `world/`: the firm's shared files (QuickBooks, Gusto and Clio exports, PDF bank statements, Excel
  workpapers...). `world/quickbooks_app/` holds the QuickBooks application data (journal entries, chart of
  accounts, vendor master, bank transactions).
- `tasks/T<n>/REQUEST.md`: the request. `tasks/T<n>/files/`: files specific to that request (memos, review
  notes, drafts).

Deliverable: for each task, `output/T<n>.md` with your final answer, in English, as you would write it in the
final message to whoever made the request: the requested figures with two decimals and $, each item with its
cause, and the proposed journal entries with account, amount and side when asked.

Scoring: each task has a hidden rubric of binary criteria written by the accountant (exact figures ±$0.01
and explanations). The score is the % of criteria met, reading ONLY your output file.
No network. You may use Python (pandas, openpyxl, pdfplumber/pypdf if installed; otherwise pdftotext).
