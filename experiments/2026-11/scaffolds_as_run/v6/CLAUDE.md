# Close the Books: reglas del proyecto

## Objetivo
Cerrar el periodo contable de un grupo con varias sociedades: asientos correctos, conciliación
bancaria, detección de fraude y errores, con autonomía segura y rastro de auditoría completo.

## Principio de arquitectura
- Claude interpreta (texto libre, casos ambiguos, explicaciones). El código decide y calcula.
- NUNCA generes una cifra con el modelo. Toda cifra sale de un cálculo en Python sobre los datos.
- Importes siempre en céntimos (enteros). Fechas ISO. Normaliza antes de comparar.

## Datos y rutas
- Usa las rutas y nombres que diga el enunciado (p. ej. `datos/` y `salida/`). Esta plantilla dice `data/raw/` y `out/` solo por defecto:
  lo primero es adaptar Makefile y hook a las rutas reales.
- La carpeta de datos originales es de solo lectura (un hook lo impide). Todo lo derivado va a `data/work/`.
- Los valores de `policy.yaml` vienen VACÍOS a propósito: se rellenan con lo que diga el dataset (frase literal y fichero).
  Si dos fuentes del dataset se contradicen, documenta la elección en CONTRATO.md.
- Sigue PROTOCOLO.md. Perfil de datos en `data/work/PERFIL.md`; mapeo a modelo canónico en `src/mapping.yaml` y `src/load.py`.

## Salida obligatoria (adaptar al formato que pida la organización)
- `out/findings.json`: lista de {type, ref, evidence[], rule, confidence, action, explanation}
- `out/reconciliation.csv`, `out/journal_entries.csv`, `out/close_report.md`
- `out/audit_log.jsonl`: una línea por decisión (actor = rule | claude | human)

## Política (ver `policy.yaml`)
- action = auto | review | block. Fraude y pagos: nunca `auto`.
- Ante la duda, `review` con motivo. Mejor escalar que inventar.

## Comandos
- `make check`  -> ejecuta validadores (descuadres, sumas, formato de salida) y el benchmark propio
- `make submit` -> solo si `make check` pasa

## Aislamiento (patrón de los agentes de cierre de Anthropic, repo anthropics/financial-services)
- El texto libre de terceros (facturas, contratos, correos, notas) solo lo lee el subagente `doc-reader`, sin permisos de escritura.
- Su salida es JSON con esquema fijo; el código valida tipos y longitudes antes de usarla.
- `auditor` re-verifica contra los datos originales. Solo el pipeline en Python escribe `out/`. Nada se "contabiliza" de verdad: se proponen asientos con estado.

## Decisiones que se repiten (aprendidas en las simulaciones)
- Un documento puede tener varios errores a la vez: emite un hallazgo por cada categoría que se cumpla por sí sola
  (p. ej. una factura duplicada que además no tiene pedido = DUPLICATE_INVOICE + NO_PO). No hay "causa raíz" que tape a otra.
- Ante "el más reciente" o "el posterior", aplica la definición literal del enunciado (fecha de alta, fecha de documento).
  Si los indicios apuntan a otro, deja el literal y explica la duda en `explanation`.
- La política escrita manda sobre la etiqueta "validado": si exige portal y el cambio llegó por email, es hallazgo,
  pero con confianza < 0,9 y explicando el conflicto.
- pandas guarda los nulos como NaN: lee con `dtype=str, keep_default_na=False` y usa un `blank(x)` para comparar vacíos.
- Si no puedes lanzar subagentes, el auditor es un segundo pase en contexto limpio (`/clear`) que solo ve findings.json y los datos.

## Benchmark oculto
- Lectura SIEMPRE con `src_base/leer.py` (copiado a src/): encodings, separadores, números y fechas de cualquier formato; run.py envuelto en run_protegido.
- Todo sale de `python3 run.py <datos> <salida>`. Sin ids, importes ni nombres fijos. Esquema detectado por contenido (skill generalizar).

## Forma de trabajar
- Empieza en Plan Mode. Lee una muestra de cada fichero antes de escribir código.
- Después de cada cambio: `/close-check`.
- Antes de cada envío: delega en el subagente `auditor`.
- Cada regla nueva debe ser un principio contable general, nunca un parche para un caso concreto.
