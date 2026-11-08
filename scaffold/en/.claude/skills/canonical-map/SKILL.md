---
name: canonical-map
description: Converts any input schema into a normalized canonical model (companies, vendors, invoices, purchase orders, contracts, bank, journal, master data changes, intercompany, history). Use it after explore-data.
---
1. Write `src/mapping.yaml`: for each canonical concept, the source file and column (taken from PERFIL.md).
2. Write `src/load.py`, which returns canonical DataFrames with (read with `dtype=str, keep_default_na=False` and define `blank(x)` for empty/NaN values):
   - amounts in cents (int), accepting 1.234,56 / 1234.56 / € / spaces; a unified sign (bank outflow < 0);
   - dates as date, accepting ISO and dd/mm/yyyy;
   - IBAN without spaces, in uppercase; NIF (Spanish tax ID) in uppercase; invoice numbers normalized (only [0-9A-Z], no leading zeros) in a separate column;
   - nested JSON flattened (invoice lines, VAT and withholding blocks);
   - policy thresholds and rules loaded from what the dataset says (never hard-coded).
3. Test: `load.py` prints the rows per table and the % of joins that match; compare it with PERFIL.md. If a join drops, check the normalization before going on.
4. The rules work ONLY on the canonical model. That way, if the dataset changes, only mapping.yaml changes.
