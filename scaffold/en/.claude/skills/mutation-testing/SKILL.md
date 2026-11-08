---
name: mutation-testing
description: Builds your own labelled test without having the key: copy the real data, inject known errors and measure what your pipeline detects. Use it as soon as the pipeline produces output, and before every submission.
---
0. Write it together with load.py: they share utilities.
1. `src/mutate.py <canonical_data> <output> --seed N`: copies the canonical model and injects the following, saving the key in `mutations.json`:
   - duplicate an invoice with its number reformatted (and another one with two digits transposed);
   - repeat a full payment 2 days later;
   - change the VAT amount of one invoice (+/- 2-40 €) and the rate of another;
   - add an unvalidated IBAN change by email and a payment to the new IBAN 3 days later;
   - unbalance an entry; move an invoice to the next month; break an intercompany balance;
   - one mutation for EACH category your pipeline covers (master data too: shared IBAN, duplicate vendor record, invalid NIF (Spanish tax ID); invoice splitting; contract price; injection);
   - plan the mutations so they do not overlap: each one on a different document and with no prior payments;
   - AND THEIR LEGITIMATE TWINS (IBAN change via the portal and validated, foreign NIF, monthly subscription): a payment in two instalments, a partial delivery, a bank fee, a 2-cent rounding.
2. Run the pipeline on the mutated copy and score it: recall on the mutations and false positives on the twins.
3. Repeat with 3 seeds. A rule only goes into the submission if it improves here, not just on the leaderboard.
