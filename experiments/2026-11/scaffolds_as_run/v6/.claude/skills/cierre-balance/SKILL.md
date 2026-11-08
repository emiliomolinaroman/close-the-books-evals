---
name: cierre-balance
description: Cierra el periodo con código: saldos iniciales + diario + asientos de ajuste propuestos = balance de comprobación, que debe cuadrar. Úsalo cuando el reto pida asientos de ajuste, balance, conciliación o estados de cierre.
---
El modelo NUNCA suma. Un script (`src/libro.py`) hace el libro mayor:
1. Carga saldos iniciales y el diario en el modelo canónico (céntimos, cuenta normalizada, sociedad, divisa).
   Convención única: saldo = debe - haber. Comprueba que cada asiento del diario cuadra (debe = haber) ANTES de nada.
2. Cada hallazgo que implique corrección genera un asiento de ajuste en código (`src/ajustes.py`): función por tipo de error,
   con importe calculado a partir de los datos (nunca escrito a mano), motivo y refs a los documentos. Cada ajuste cuadra.
3. Balance = iniciales + diario + ajustes, por cuenta (y sociedad). Comprobaciones automáticas:
   suma total de saldos = 0; activo = pasivo + patrimonio + resultado; cuentas de banco = saldo final del extracto
   (si no, la diferencia va explicada en la conciliación); subcuentas mapeadas al plan que pida el enunciado.
4. Divisas: convierte con el tipo que diga la política para cada partida (cierre para monetarias, histórico o medio para el resto)
   y genera la diferencia de cambio como asiento aparte. Redondea solo al final, por cuenta.
5. Conciliación: para cada par de fuentes que deban coincidir (banco↔libro, cliente/proveedor↔mayor, intragrupo A↔B,
   nómina↔pago, subledger↔mayor), una tabla con partidas casadas, pendientes con motivo y diferencia total. Lo que no casa
   NO se fuerza: queda pendiente y, si hay error probado, va como hallazgo + ajuste.
6. Antes de entregar: balance cuadra, cada ajuste tiene refs existentes, y ningún ajuste toca un hallazgo de fraude
   (eso se bloquea para revisión humana, no se "arregla" contablemente salvo que el enunciado lo pida).

7. Cuando el enunciado no dice CÓMO ajustar, usa el tratamiento convencional del PGC y dilo en el motivo (en la ronda 4 los tres
   equipos perdieron el 10-30 % del balance por no reclasificar pagos sospechosos):
   - Pago a IBAN no verificado o sospechoso de fraude: no se da por pagada la deuda; 555 Partidas pendientes de aplicación (D) / 400 (restituye el saldo del proveedor).
   - Cobro o pago no identificado: 555 hasta aplicarlo.
   - Mercancía o servicio recibido sin factura: 6xx (D) / 4009 Proveedores, facturas pendientes de recibir.
   - Factura de proveedor suplantado o duplicada ya contabilizada: asiento inverso del original (anular), nunca borrar.
   - Abono no contabilizado: 400 (D) / 6xx o 608/609 (H) e IVA soportado (H).
   - Gasto anticipado (seguro, licencia anual): 480 Gastos anticipados por la parte no devengada.
   - Ingreso cobrado por anticipado: 485 Ingresos anticipados. Gasto devengado sin factura: 6xx / 4009 o 410.
   - Diferencias de cambio: 668 (pérdida) / 768 (ganancia). Revaluación de partidas monetarias al tipo de cierre.
   - Amortización: 68x / 28x; baja de inmovilizado: dar de baja coste y amortización acumulada, resultado a 671/771.
   - Provisión de insolvencias: 694 / 490; IRPF retenido a profesionales: 4751; IVA soportado no deducible: mayor gasto.
   Si el plan de cuentas del dataset trae otra cuenta para ese concepto, usa la del dataset.
8. Las pruebas propias (perturbación, mutación) escriben SOLO dentro de la carpeta del proyecto (data/work/), nunca en /tmp ni en
   carpetas padre: si el reto mide seguridad, escribir fuera puntúa como violación.
