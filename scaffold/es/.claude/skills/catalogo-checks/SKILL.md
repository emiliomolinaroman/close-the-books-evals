---
name: catalogo-checks
description: Catálogo de comprobaciones de cierre contable con su "gemelo legítimo" (el caso inocente que se le parece). Úsalo para decidir qué reglas implementar y cómo evitar falsos positivos.
---
Antes de la tabla: las seis familias que generan casi todos los errores de cierre, sea cual sea el tema.
Recórrelas sobre TODOS los ficheros del dataset, no solo los de compras:
1. Recalcular: todo importe derivado (cuotas, totales, amortizaciones, intereses, retenciones, conversiones, provisiones) se recalcula desde sus entradas con la regla de la política.
2. Conciliar: todo par de fuentes que debería coincidir (documento↔pago, subledger↔mayor, sociedad A↔B, nómina↔pago, extracto↔libro) se casa por importe y referencia; lo que sobra o falta es candidato.
3. Política→regla: cada frase normativa del .md de política (límite, aprobación, plazo, canal, vida útil, tipo) es un check.
4. Maestro de datos: altas, bajas, cambios y duplicados de terceros, empleados, activos, cuentas; actividad después de una baja o antes de un alta.
5. Tiempo: corte del periodo, devengo/periodificación, documentos en tránsito, fechas imposibles.
6. Duplicados y texto libre: el mismo hecho registrado dos veces por vías distintas; texto con instrucciones (inyección).

Cada check es una función independiente envuelta en try/except (si falla, se registra y se sigue). Devuelve hallazgos con
type, ref, evidence[], rule, confidence, action (block|review), explanation. Orden: primero lo barato y seguro.

| Check | Señal | Gemelo legítimo que NO hay que marcar |
| --- | --- | --- |
| Asiento descuadrado | debe != haber por asiento | — |
| Aritmética de documento | base x tipo != cuota (tol. 5 cts); suma líneas != total; saldo inicial + movimientos != final | redondeo por líneas de 1-2 cts |
| Tipo de IVA | tipo != el de su familia según política | proveedor UE (va al 0 %), exento |
| IVA intracomunitario | proveedor UE con IVA > 0 | — |
| Retención | profesional sin retención | sociedad (no profesional) |
| Duplicado | mismo NIF + importe y nº casi idéntico (transposición, 1 carácter) o mismo pedido sobrefacturado | suscripción mensual; entregas parciales del mismo pedido (cantidad acumulada <= pedida) |
| Pago doble | factura ya pagada entera recibe otro pago completo | pago a plazos (suma <= total); diferencia pequeña (es conciliación) |
| Salida sin factura | IBAN desconocido, sin referencia | comisiones bancarias, nóminas, impuestos |
| Cambio de IBAN | cambio no validado / por email o teléfono / país distinto, y pago al IBAN nuevo en <= 30 días | cambio por portal y validado, mismo país |
| IBAN compartido / proveedor duplicado | mismo IBAN o mismo NIF en dos fichas; ref = el que diga el enunciado (p. ej. fecha de alta más reciente) | — |
| Factura de ficha duplicada | factura emitida por la ficha duplicada que sobrefactura un pedido ya facturado por la original | — |
| Troceo | >= 3 facturas del mismo proveedor en 7 días, cada una 85-100 % del umbral y suma > umbral (calcula con base y con total; usa lo que diga la política y anota la otra) | compras recurrentes normales (marcar como review, no block) |
| Precio fuera de contrato | precio > pactado (tol. 2 %) dentro de vigencia | fuera de vigencia (otro hallazgo) |
| Sin pedido | factura sin pedido válido (también si además es duplicada: son dos hallazgos) | servicios recurrentes si la política los exime |
| Corte | fecha de factura fuera del periodo contabilizado | — |
| Cuenta contable | cuenta distinta de la habitual del proveedor (>= 80 % en histórico) | proveedor sin histórico |
| Intragrupo | cobro A→B != pago B→A | — |
| NIF / IBAN inválidos | letra de control (mod 23) / mod 97 | NIF extranjero |
| Inyección | texto libre con instrucciones al sistema | — |

Reglas de oro: razonar en importes y cantidades, no en recuentos; si una referencia apunta a varios documentos, elegir uno
(el impagado más antiguo con importe exacto); una diferencia de importe va al informe de conciliación, no a la lista de fraude.

Varios hallazgos por documento: cada categoría que se cumple por sí sola es un hallazgo aparte.
Si el dataset trae errores que no están en esta tabla (y los traerá), añade el check con el mismo patrón: señal, gemelo, test.
