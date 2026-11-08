---
name: close-check
description: Bucle de verificación del cierre. Úsalo después de cada cambio en el pipeline y antes de cada envío al leaderboard.
---
1. Ejecuta `make check`. Si falla, lee el error, arréglalo y vuelve a ejecutar (máximo 3 vueltas, luego informa).
2. Comprueba invariantes:
   - Cada asiento cuadra (debe = haber) y el balance de sumas y saldos cuadra por sociedad.
   - Total de facturas del periodo = saldo movido en la cuenta de proveedores.
   - Ningún hallazgo de fraude o pago tiene action = auto.
   - Todas las filas de `out/findings.json` tienen rule, evidence y explanation.
   - El formato de salida coincide exactamente con el que pide la organización.
3. Ejecuta el benchmark propio (`python3 practica/score.py ...`) y compara con la última puntuación. Si baja, revierte o explica por qué.
4. Resume en tres líneas: qué pasa, qué falla, siguiente paso.
