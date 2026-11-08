# NOTAS (equipo fb_A4)
1. `run.py` es autocontenido (solo stdlib): parsea el OCR (pares `Clave: valor` y filas `- A | B`, números US/EU), aplica una regla de asiento por tipo de documento y enlaza soportes por referencia (GRN, albarán, FGT, work order, PRE-, LEASE-, ASC606-, FXINV-...).
2. Balance = apertura + asientos; cuentas de resultados se cierran a Retained Earnings; cuentas a cero se omiten. Ejemplos resueltos: 30/30 balances/códigos exactos y F1 de asientos (cuenta+importe) = 1.0.
3. Inconsistencias: comprobaciones aritméticas (banco, facturas, impuestos, rollforwards, leases, disposals, SSP/POB, FX, transfers, reclasificaciones, exenciones, duplicados). Si salta alguna: entries [] y balance vacío.
4. Autochequeo sin etiquetas en público: Cash/Reserve Cash finales cuadran con el cierre de los extractos bancarios en los 45 paquetes que doy por limpios; 15 marcados como inconsistentes.
5. El record_id de los paquetes negativos lleva el código ("..._NEG_..._MISMATCH"); NO lo uso para predecir (sólo lo he mirado como control a posteriori).
6. Dudas: si subtotal+impuesto != total, uso invoice_total_mismatch en facturas de proveedor y tax_total_mismatch en las de cliente (heurística sacada de 1 caso de cada).
7. Sin respuestas de referencia para SaaS/ASC 606, FX, deferred tax y modificación de lease: los asientos son mi lectura de la especificación (diferido a Unearned Revenue y liberación según schedule/POB/aceptación; FX al tipo del exchange_rate_notice).
8. Códigos nunca vistos (duplicate_reference_conflict, payment_allocation, ssp_allocation, asset_disposal, lease_remeasurement, exchange_rate, input_tax, jurisdiction, tax_exemption) están implementados pero sin validar con casos reales.
9. No sé resolver: movimientos sólo visibles en el banco (salvo "Advance collection"), cuentas de gasto de facturas sin etiqueta, y paquetes donde fallan varias reglas a la vez (devuelvo todos los códigos).
