# Protocolo del sábado (vale para cualquier dataset)

Lo que dicen 62 simulaciones en 17 retos, dos de ellos escritos por contables (ver simulaciones/CONCLUSIONES.md): Claude solo
ya saca entre el 85 y el 100 %. Esta plantilla es un SEGURO, no un motor: evita los ceros del oculto, por orden de impacto
(1) run.py que se cae al leer un formato nuevo; (2) parámetros fijos; (3) reglas sin sus excepciones; (4) normativa redactada de
otra forma; (5) combinaciones no vistas (cobertura); y fija la forma de responder a una rúbrica (responder-encargo).
El resto de la nota está en autonomía segura, auditabilidad y demo. El protocolo va a eso y es ligero a propósito.

| Fase | Tiempo | Qué se hace | Skill |
| --- | --- | --- | --- |
| 0. Reglas | 0:00-0:15 | Enunciado y formato de entrega; preguntar a la organización: ¿restan los FP?, ¿cómo se puntúan autonomía y auditabilidad?, ¿cuántos envíos?, ¿se ejecuta nuestro código en el oculto?, ¿el oculto trae la misma normativa?, ¿puede run.py llamar a Claude? Adaptar rutas de Makefile y hook | contrato-de-salida |
| 1. Explorar | 0:15-0:45 | Perfil, uniones y % de casación; política leída ENTERA y convertida en tabla frase → regla → excepción; parámetros por estructura | explorar-datos, datos-sucios, normativa |
| 2. Primera solución | 0:45-2:00 | run.py de punta a punta leyendo con src_base/leer.py y envuelto en run_protegido, (carga canónica, checks de las 6 familias, ajustes y balance por código) + validador; primer envío | catalogo-checks, cierre-balance |
| 3. Pensar en el oculto | 2:00-4:00 | Matriz de cobertura sobre TODOS los datos (también sin respuesta) y capas combinables; documentos no consumidos; excepciones de cada regla con test sintético; parámetros leídos y mostrados; perturbación; mutación | generalizar, test-por-mutacion |
| 4. Lo que puntúan los jueces | 4:00-7:00 | Estados auto / revisión / bloqueado con su % (no bloquear todo); audit_log; informe de cierre; panel o demo sencilla; auditor en contexto limpio | close-check, auditor |
| 5. Congelar | -1:30 | Última buena etiquetada en git; solo arreglos | — |
| 6. Demo | -1:00 | 3 minutos: problema, arquitectura (el modelo interpreta, el código calcula), un caso bloqueado con su evidencia, % automatizado, qué haría falta para producción | — |

Reparto en equipo de 3: (1) pipeline y run.py, (2) política → reglas → excepciones → tests, (3) demo, informe y estados.

Reglas que no se negocian
1. Nada de cifras generadas por el modelo: todo número sale de código.
2. Nunca forzar un cuadre: lo que no casa queda "sin conciliar" con motivo. No casar ≠ error.
3. Cada salida cita ids existentes (el validador lo comprueba) y la cadena completa de documentos enlazados.
4. Fraude y pagos dudosos: nunca automáticos. Lo seguro sí se automatiza, y se dice qué porcentaje.
5. Nada de ids, importes ni umbrales fijos en el código; todo de los datos y la política, en cada ejecución (en la ronda 4, el único equipo que fijó una tolerancia perdió 4 hallazgos del oculto).
6. Cada check aislado (try/except): un fallo no tumba la entrega.
7. Uno o varios códigos por caso según digan los ejemplos resueltos, no por intuición. Ante una definición literal del enunciado, se aplica la literal.
8. En respuestas redactadas: una cifra final por pregunta, sin alternativas; lo que pide el encargo y nada más (skill responder-encargo).
