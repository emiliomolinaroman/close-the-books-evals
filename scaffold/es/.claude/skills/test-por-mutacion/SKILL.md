---
name: test-por-mutacion
description: Crea tu propio test etiquetado sin tener la clave: copia los datos reales, inyecta errores conocidos y mide qué detecta tu pipeline. Úsalo en cuanto el pipeline produzca salida, y antes de cada envío.
---
0. Escríbelo junto con load.py: comparten utilidades.
1. `src/mutate.py <data_canonico> <salida> --seed N`: copia el modelo canónico e inyecta, guardando la clave en `mutations.json`:
   - duplicar una factura con el número reformateado (y otra con dos dígitos transpuestos);
   - repetir un pago completo 2 días después;
   - cambiar la cuota de IVA de una factura (+/- 2-40 €) y el tipo de otra;
   - añadir un cambio de IBAN por email sin validar y un pago al IBAN nuevo 3 días después;
   - descuadrar un asiento; mover una factura al mes siguiente; desajustar un saldo intragrupo;
   - una mutación por CADA categoría que cubra tu pipeline (también maestro: IBAN compartido, ficha duplicada, NIF inválido; troceo; precio de contrato; inyección);
   - planifica las mutaciones para que no se pisen: cada una en un documento distinto y sin pagos previos;
   - Y SUS GEMELOS LEGÍTIMOS (cambio de IBAN por portal y validado, NIF extranjero, suscripción mensual): un pago en dos plazos, una entrega parcial, una comisión bancaria, un redondeo de 2 cts.
2. Ejecuta el pipeline sobre la copia mutada y puntúa: recall sobre las mutaciones y falsos positivos sobre los gemelos.
3. Repite con 3 semillas. Una regla solo sube a la entrega si mejora aquí, no solo en el leaderboard.
