1. run.py: parser genérico del OCR (secciones, "Clave: valor", filas "- K v | K v" con líneas partidas), decimal (1.234,56 / 1,234.56) detectado por paquete.
2. Primero comprueba la aritmética de cada documento (banco, factura/IVA/tipo, extracto, asignación de pagos, rollforwards de ingresos/inventario/impuesto diferido, leasing, bajas, FX, reclasificaciones, ASC 606, exención, jurisdicción); si algo no cuadra: inconsistente con esos códigos.
3. Si cuadra: un manejador por tipo de documento genera asientos (enlazando por referencias: GRN, envío, lote, contrato, PRE-, LEASE-, FX...), y el balance = apertura + asientos, con el resultado a Retained Earnings.
4. Ignora copias, memos informativos, extractos y facturas retiradas por nota de cancelación (y duplicados con el mismo número).
5. Comprobado: 30/30 ejemplos resueltos (F1 asientos 1.0), 30/30 con documentos barajados e ids renumerados; en público, Caja final = cierre bancario en los 45 limpios y 0 asientos con cuentas no permitidas.
6. No usa record_id ni importes fijos. 60 paquetes en <1 s.
7. Dudas: "invoice_total" vs "tax_total" cuando la factura tiene impuesto (elijo tax_total); input_tax_mismatch casi no se detecta (no hay campos de ejemplo).
8. Sin ejemplos resueltos para SaaS/ASC 606, FX, impuesto diferido, modificación de leasing ni cobros anticipados: los asientos siguen la especificación, sin verificar contra respuesta.
9. Cuentas de apertura que acaban a 0 se dejan con 0.0 (no sé si el corrector las quiere fuera).
10. Plantillas o tipos de documento nuevos en el oculto no se contabilizan (fallan en silencio por documento, no tumban el paquete).
