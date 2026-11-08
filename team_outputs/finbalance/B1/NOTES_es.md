# NOTAS (equipo fb_B1)
1. `run.py` (solo stdlib): parsea el OCR genérico (`Clave: valor` + filas `- K v | K v`, une líneas cortadas, números US/EU) y aplica un manejador por `doc_type` (≈40 tipos) que genera asientos; el balance = apertura + asientos, con resultados cerrados a Retained Earnings y cuentas a cero omitidas.
2. Copias secundarias, referencias retiradas por `cancellation_note` y duplicados no se contabilizan; el extracto bancario se usa como evidencia (importe exacto de prepagos, cobros anticipados que solo aparecen en el banco).
3. Impuestos: IVA/GST/sales tax separados (Input Tax Receivable / Sales Tax Payable); India GST con CGST+SGST o IGST según campos/jurisdicción; US sales tax en compras se integra en el coste.
4. Inconsistencias: ~20 cuadres aritméticos (banco, extractos, rollforwards, leasing, bajas, impuesto diferido, FX, ASC 606, transferencias, reclasificaciones, impuestos); si salta alguno se marca y se vacían asientos/balance.
5. Comprobación: 30/30 ejemplos resueltos (balance exacto, F1 asientos 1.0); en público 15 marcados (coinciden con los NEG del id, sin usar el id) y la caja cuadra con todos los extractos de los 45 limpios; test de mutación por código.
6. No sé distinguir con seguridad `invoice_total_mismatch` de `tax_total_mismatch` cuando subtotal+impuesto≠total: uso el sentido del error (total mayor = invoice_total).
7. Sin ejemplos resueltos para SaaS/ASC 606, retainers, FX, leasing modificado e impuesto diferido: asientos razonados según el enunciado (factura→Unearned Revenue, liberación según calendario), no verificados.
8. `reclassification_memo` en paquetes limpios: la cuenta destino se infiere del texto/las líneas del recibo; puede fallar. `renewal_notice` no genera asiento.
9. Orden de `doc_refs` aproximado (F1 estricto puede bajar); códigos poco vistos (input_tax, jurisdiction, exemption_conflict, ssp) solo probados con mutaciones.
