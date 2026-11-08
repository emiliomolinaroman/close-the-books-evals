---
name: generalizar
description: Para que el código funcione en el benchmark oculto y no solo en los datos visibles. Úsalo desde la primera entrega si el reto ejecuta tu programa sobre otros datos, y antes de congelar en cualquier caso.
---
1. Un único punto de entrada: `python3 run.py <datos> <salida>` regenera TODA la entrega desde cero, sin estado previo ni rutas fijas.
   Nada de leer data/work de una ejecución anterior; nada de ids, importes, nombres de terceros ni fechas fijos en el código.
1b. LECTURA: copia `src_base/leer.py` a `src/` y lee TODO con él (leer_tabla, num con detectar_decimal, fecha con detectar_mdy,
   run_protegido). En la ronda 4, 2 de 3 equipos sacaron F1 = 0 en un oculto porque los CSV venían en cp1252 con tabuladores y
   su run.py se cayó al abrirlos. Un fallo de lectura de UN fichero se registra y se sigue con el resto; nunca tumba la entrega.
2. Detección de esquema por contenido, no por posición: busca columnas por sinónimos (fecha/date/data/f_asiento; importe/amount/import;
   debe/cargo/debit; haber/abono/credit; nif/cif/vat/tax_id...) y por forma de los valores (IBAN, NIF, fecha). Detecta separador y
   decimal (`csv.Sniffer`, coma vs punto por patrón). Fechas: prueba ISO, dd/mm/aaaa, mm/dd/aaaa y desempata por valores > 12.
3. POLÍTICA COMPLETA (es donde se pierden los puntos del oculto): por cada frase normativa de la política, implementa la regla
   Y TODAS SUS EXCEPCIONES aunque los datos visibles no las usen (p. ej. "no contabilizar si ya está en pendientes del mes anterior",
   "tolerancia de X €", "salvo aprobación de Y"). Escribe `src/politica_tabla.md`: frase literal → función → excepción → test sintético.
   Un caso que tu código no sabe casar (documento ilegible, plantilla nueva, concepto truncado) NO es un hallazgo: queda "sin casar" con motivo.
3b. Umbrales y reglas: se leen de la política del dataset en cada ejecución (regex sobre el .md); si no se encuentran, valor por defecto
   razonable + aviso en el log, nunca un crash. Imprime al inicio de run.py cada parámetro leído y de qué frase sale.
4. Test de perturbación (además de test-por-mutacion): `src/perturbar.py` crea copias de los datos (en data/work/) con columnas reordenadas,
   otro formato de fecha y decimal, separador de miles, otro separador (incluido tabulador), encoding cp1252 y UTF-8 con BOM, ids renumerados y nombres de terceros cambiados. run.py debe dar los mismos
   hallazgos (módulo los ids renombrados). Si cambia, hay algo atado a la forma y no al contenido.
5. Robustez: cada check en try/except con log; timeout global; si una fuente falta, se sigue con las demás. Mide el tiempo de run.py.
6. Antes de congelar: ejecuta run.py en una carpeta limpia (copia solo run.py + src/ + datos) y valida la salida.
