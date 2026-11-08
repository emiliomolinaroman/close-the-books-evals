---
name: mapa-canonico
description: Convierte cualquier esquema de entrada a un modelo canónico normalizado (sociedades, proveedores, facturas, pedidos, contratos, banco, diario, cambios de maestro, intragrupo, histórico). Úsalo después de explorar-datos.
---
1. Escribe `src/mapping.yaml`: para cada concepto canónico, fichero y columna de origen (sale de PERFIL.md).
2. Escribe `src/load.py`, que devuelve DataFrames canónicos con (lee con `dtype=str, keep_default_na=False` y define `blank(x)` para vacíos/NaN):
   - importes en céntimos (int), aceptando 1.234,56 / 1234.56 / € / espacios; signo unificado (salida de banco < 0);
   - fechas como date, aceptando ISO y dd/mm/aaaa;
   - IBAN sin espacios en mayúsculas; NIF en mayúsculas; números de factura normalizados (solo [0-9A-Z], sin ceros a la izquierda) en una columna aparte;
   - JSON anidado aplanado (líneas de factura, bloques de IVA y retención);
   - umbrales y reglas de la política cargados desde lo que diga el dataset (nunca fijos en el código).
3. Test: `load.py` imprime filas por tabla y % de uniones que casan; compáralo con PERFIL.md. Si una unión baja, revisa la normalización antes de seguir.
4. Las reglas trabajan SOLO sobre el modelo canónico. Así, si cambia el dataset, solo cambia mapping.yaml.
