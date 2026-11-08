# Conclusiones de las simulaciones

(Se van añadiendo ronda a ronda.)

## Antes de las rondas (1-nov, en la nube)
- v1 (reglas directas) frente a v2 (normalización + importes + gemelos legítimos), 10 semillas × 4 modos:
  v1 0,99 / 0,00 / 0,85 / 0,00 · v2 1,00 / 1,00 / 0,99 / 0,99 (limpio / sucio / duro / sucio+duro). La v2 está sobreajustada al generador.
- FinBalance (3 registros reales): balance exacto 2/2 con libro.py, contradicción 1/1, doc_refs exactos 6/16.

## Ronda 1 (1-nov, nube, 12 subagentes en paralelo, semillas 1000-1005, todos modo duro, 4 de 6 disfrazados)
Resultado: empate. A (sin preparación) P 0,96 R 0,98 F1 0,97 · B (plantilla v1) P 0,96 R 0,98 F1 0,97. Auditabilidad 165/165 en ambos.
B gastó ~21 acciones frente a ~15 de A, pero entregó validador y test por mutación (9-45 mutaciones detectadas, 0 FP en gemelos).

Lectura honesta:
- El banco de pruebas tiene techo: el enunciado lista las 19 categorías con la regla del "ref" y el generador planta casi lo mismo en
  cada semilla (INV0152, INV0157... repetidos). Un buen modelo saca 0,97 sin ayuda. Esta ronda no discrimina métodos.
- Los errores fueron los MISMOS en ambos brazos: (1) cambio de IBAN pedido por email pero "validado" → todos lo marcan como fraude
  porque la política exige portal; es un fallo de la clave del generador, no del método. (2) Factura duplicada que además no tiene
  pedido: se emite solo DUPLICATE y se pierde NO_PO. (3) "Acreedor más reciente" en SHARED_IBAN: algunos eligen por indicios en vez del literal.
- Lo que la plantilla v1 estorbó: rutas fijas (out/, data/raw/), policy.yaml con un umbral (5000) que contradice al dataset (trampa),
  CLAUDE.md pide subagentes que no siempre hay, y salidas extra que nadie pidió.
- Lo que ayudó (según los diarios de B): tabla de gemelos legítimos, medir % de casación de uniones, validador de ids (cazó evidencias
  inexistentes tipo INV0127-AJ), test por mutación (cazó 1 FP real en 4 de 6 casos).

Cambios aplicados → plantilla v2 (copia de v1 en plantilla-claude/_versiones/v1/): rutas adaptables, policy.yaml sin valores
(se rellena del dataset con frase literal), regla "un hallazgo por categoría", definición literal ante "más reciente", política
escrita manda sobre "validado" pero con confianza < 0,9, helper blank()/dtype=str, auditor como segundo pase si no hay subagentes,
mutaciones para todas las categorías y sin solaparse, protocolo comprimido si hay poco tiempo.

Siguiente: ronda 2 con datasets escritos por generadores independientes (no conocen el kit), con errores que no están en el catálogo
y con entregables de cierre (asientos de ajuste y balance), que es lo que de verdad puntúa el sábado.

## Ronda 2 (1-nov, nube, 3 retos nuevos escritos por generadores independientes que no vieron el kit, 6 subagentes)
Retos: G1 ventas y tesorería (16 tipos, 27 errores, 12 gemelos, 75 cuentas), G2 nóminas, gastos e inmovilizado (16 tipos, 21 errores,
12 gemelos, 50 cuentas), G3 grupo multidivisa EUR/GBP/USD (15 tipos, 25 errores, 11 gemelos, 91 claves de balance). Todos piden
hallazgos + asientos de ajuste + balance.
Resultado: los 6 brazos sacan F1 1,00 y balance 100 %. A (sin preparación) en 16-18 acciones; B (plantilla v2) en 26-27.

Lectura honesta:
- Un reto limpio y bien especificado, escrito por otro Claude, lo resuelve Claude sin ayuda y al primer intento. Ni la plantilla
  ni las skills mejoran la nota ahí; solo añaden validador, test por mutación, audit_log y documentación (útiles para jueces).
- Por tanto, la ventaja del sábado NO estará en "saber detectar" lo que está bien especificado: estará en lo que el reto real tenga
  de sucio (documentos no estructurados, volumen, formatos de ERP, ambigüedad), en el benchmark oculto (que el código generalice)
  y en lo que puntúan los jueces además de la precisión (autonomía segura, auditabilidad, demo).
- B bloquea casi todo (23 de 27 en G1). Si "autonomía segura" premia automatizar lo seguro, sobrebloquear puede costar: hay que
  mostrar % automático / revisión / bloqueado y justificar cada block.

Siguiente: ronda 3 con retos adversarios (facturas en texto OCR, emails, extracto grande sin ids fiables; o exportación de ERP de
30-60 mil líneas con cabeceras e informe Norma 43) y con benchmark OCULTO: cada equipo entrega run.py y se ejecuta sobre otro dataset.

## Ronda 3 (1-nov, nube, 2 retos difíciles con benchmark oculto, 8 subagentes: 2 sin preparación + 2 con plantilla v3 por reto)
H2 · exportación de ERP de un grupo de 4 sociedades: diario de ~37.300 líneas con cabeceras de informe, subtotales y saltos de página,
borradores y anulados, Norma 43 + CSV + XLSX de tres bancos, política de ~5.000 palabras. 17 tipos, 32 errores, 30 gemelos, 4 neutros.
Oculto: otras sociedades e ids, otros parámetros de política y otro formato (columnas barajadas, ISO, punto decimal, signo detrás, BOM).
→ Los 4 brazos: F1 1,00 y balance 100 % en público Y en oculto. A en 31-38 acciones, B en 26-37.

H1 · cuentas a pagar con documentos: ~119 facturas en texto OCR con 4 plantillas, ~22 emails .eml (uno con instrucciones a la IA),
8 contratos en prosa, ~3.250 movimientos bancarios sin ids fiables, manual antiguo que contradice la política vigente.
Oculto con tipos de error que NO salen en el público y formato distinto.
                público        oculto (run.py sobre datos no vistos)
  A1 (sin prep)  F1 1,00 · 100 %   F1 0,97 · balance 95 %
  A2 (sin prep)  F1 1,00 · 100 %   F1 0,97 · balance 92 %
  B1 (plantilla) F1 1,00 · 100 %   F1 0,95 · balance 92 %
  B2 (plantilla) F1 1,00 · 100 %   F1 0,97 · balance 95 %
Recall 1,00 en todos, incluso en tipos no vistos. Todos los fallos son falsos positivos del oculto, y se repiten entre brazos:
- regla implementada sin su excepción porque el público no la usaba: "factura no contabilizada" que ya estaba en pendientes a 30/09 (A2, B1);
- tolerancia fija o mal leída (0,02 en vez de 0,10 de la política) en pagos agrupados (B1, B2);
- documento de una plantilla nueva que el parser no casa → se trata como "no contabilizado" o "importe distinto" (A1, B2).

## CONCLUSIÓN GENERAL (26 equipos simulados en 6 retos distintos, más 5 generadores independientes)
1. La precisión sobre lo visible está saturada: Claude solo, leyendo con cuidado, saca el 100 % y cuadra el balance en 16-40 acciones
   (1-2 horas reales). La plantilla y las skills no suben esa nota y cuestan ~30-50 % más acciones.
2. Donde se pierde (3-5 puntos de F1 y 5-8 de balance): el benchmark oculto. Las tres causas son siempre las mismas y son de método,
   no de conocimiento contable: excepciones no implementadas, parámetros fijos, "no casa" tratado como error.
3. Lo que hay que llevar preparado: un CLAUDE.md corto de principios + 4 skills (contrato-de-salida, generalizar con "política completa",
   cierre-balance, test de perturbación/mutación) + el protocolo ligero. El resto de skills sirve de consulta, no de guion.
4. Lo que se crea en el momento: el modelo canónico, los checks concretos, la tabla política → regla → excepción, y la demo.
5. Lo que decide entre equipos que aciertan igual: autonomía segura (no bloquearlo todo: % auto / revisión / bloqueado), rastro de
   auditoría, informe de cierre y una demo clara. Ahí hay que meter las horas que sobran tras la primera solución.
6. Limitación honesta: los retos los escribió Claude; el real lo escriben contables (Talky con la UCppM) y puede ser más ambiguo,
   con etiquetas discutibles. Contra eso solo vale: leer la política literal, explicar cada duda en `explanation` y bajar la confianza.

## Ronda 4 · retos "cojoneros" (1-nov, 5 retos diseñados para romper el sistema, 15 equipos: A1 sin preparación, B1 y B2 con plantilla v4)
                                   público F1/balance        oculto F1/balance (A1 | B1 | B2)
  K1 inyecciones y manipulación    1,00 / 91 % los tres      1,00 todos, seguridad 1 todos · balance 71 | 84 | 84 %
  K2 reglas del histórico (18k)    1,00 / 100 % los tres     0,99 / 100 % los tres (el único FP es un artefacto del generador)
  K3 400k movimientos, solapes     1,00 / 100 % los tres     1,00 / 100 % los tres (run.py en 11 s)
  K4 PDFs feos + 10 imágenes       1,00 / 100 % los tres     0,95 | 1,00 | 1,00 (A1 fijó la tolerancia del público: 1 % en vez de 0,5 %)
  K5 manual + circulares           1,00 / 100 % los tres     0,91 | 0,92 | 0,94 · balance 100 | 97 | 97 %

Lo que aprendimos:
- Claude aguanta muy bien volumen (400k filas), formatos nuevos, PDFs multipágina, imágenes (las marca como no legibles sin inventar)
  y 11 inyecciones distintas (ninguna obedecida, seguridad 1 en todos). No hace falta preparación específica para eso.
- Primera diferencia medible a favor de la plantilla: "parámetros siempre de la política" (K4). Sin ella, 4 errores perdidos.
- Fallo que nadie evitó (K5): el oculto trae una circular con otra fórmula de enmienda ("se da nueva redacción… sustituyéndose «X» por
  «Y»" en vez de "donde dice… debe decir") y una cláusula expresa que hace prevalecer una general sobre una específica. Los parsers
  por frase no la ven → 14 hallazgos perdidos. B1 pasaba 21/21 tests propios de circulares: los tests solo cubrían redacciones conocidas.
  → skill nueva `normativa`: parámetros por estructura (pares de valores citados), algoritmo único de jerarquía, detector de cláusulas
  no entendidas, y circulares sintéticas con redacciones distintas antes de congelar.
- K1: los tres equipos perdieron balance igual porque no reclasificaron a 555 los pagos a IBAN no verificado (el enunciado no lo decía;
  es la convención del PGC). → chuleta de tratamientos PGC en `cierre-balance`. Además, varios equipos escribieron en /tmp para
  probar: en un reto que mide seguridad eso puntúa como violación → regla: pruebas solo dentro del proyecto.

## Ronda 5 (plantilla v5: skill normativa, lector robusto src_base/leer.py, chuleta PGC; 5 equipos)
K5 normativa. "oculto2" es un segundo oculto escrito DESPUÉS de la v5 por un generador que no la conocía: 5 fórmulas de enmienda
nuevas (sin comillas, tabla Antes|Ahora, anexo con cuadro, fe de erratas), vigencia en un CSV de registro, vigencia futura, circular
que cambia una definición del glosario, y CSV en cp1252 con tabuladores y separador de miles.
                         oculto        oculto2 (justo)
  A1, A2 (sin prep)      0,91 / 0,93   0,00 / 0,00  (run.py se cae al abrir el CSV en cp1252)
  B1, B2 (v4)            0,92 / 0,94   0,77 / 0,00
  B3, B4 (v5)            0,98 / 0,98   0,84 / 0,84  (balance 85 %)
H1 facturas OCR (oculto de la ronda 3): B3, B4 (v5) → 1,00 y balance 100 % los dos (en la ronda 3: 0,95-0,97 y 92-95 %).

Lectura:
- La caída a 0 es el riesgo nº 1 de un benchmark oculto: un fichero que no se puede abrir tumba toda la entrega. El lector robusto
  (encoding con alternativas, separador detectado, números y fechas de cualquier formato, run_protegido) lo elimina.
- Con v5, lo que queda en oculto2 son enmiendas con fórmulas nuevas que el parser ignoró SIN AVISAR → v6: enmiendas por apartado
  + importes (sin depender de comillas ni verbos), tablas y cuadros, erratas, vigencia en registro, glosario como funciones, y un
  detector obligatorio de importes no consumidos.
- Matiz importante para el sábado: en un hackathon real el oculto suele ser la MISMA empresa y la MISMA normativa con otras
  transacciones. Cambiar la redacción de la normativa entre visible y oculto es el peor caso. Prepararse para él no cuesta tiempo
  extra si el método ya está en la plantilla.

## Ronda 6 (plantilla v6; K5 con un TERCER oculto escrito después de la v6: 7 fórmulas de enmienda nuevas, suspensión temporal de
una circular, "instrucción" de dirección que no es norma, CSV con | y columnas nuevas)
  equipo              oculto   oculto2   oculto3 (justo para todos)
  A1, A2 (sin prep)   0,91/0,93  0 / 0     0 / 0        (se caen: encoding en oculto2, nombre de columna en oculto3)
  B1 (v4)             0,92     0,77      0,72
  B2 (v4)             0,94     0         0            (se cae)
  B3, B4 (v5)         0,98     0,84      0,73 / 0,74
  B5, B6 (v6)         0,98     0,87/0,84 0,76 / 0,74
Lectura: la plantilla evita el desastre (0 → 0,74) y gana entre 4 y 6 puntos cuando la normativa cambia de redacción. Pasada la v5,
las mejoras son de 1-2 puntos: el código determinista ha tocado techo frente a redacciones que nunca ha visto. Lo que falta
solo se cierra con un modelo dentro de run.py que lea la normativa (si la organización lo permite) o porque el oculto real
comparta la normativa con el visible, que es lo más probable. Paramos de iterar aquí: más rondas sobre este eje ya no compensan.

## CONCLUSIÓN FINAL (6 rondas, 52 equipos simulados, 15 retos, 3 ocultos extra)
1. Lo visible no diferencia: Claude solo lo resuelve. Los puntos están en el oculto y en lo que juzgan las personas.
2. Lo que sí marca diferencia medida, por orden de impacto:
   a) Que run.py NUNCA se caiga: lector robusto (encodings, separadores, columnas por sinónimos, números y fechas) + run_protegido.
      Sin él, 4 de 6 equipos sacaron 0 en algún oculto.
   b) Parámetros siempre de la política, leídos en cada ejecución (K4: 4 errores perdidos al fijar una tolerancia).
   c) Política completa con sus excepciones aunque los datos visibles no las usen (H1: de 0,95-0,97 a 1,00).
   d) Normativa por estructura y con jerarquía (vigencia, ámbito, anulación/derogación, cláusula expresa) + detector de lo no entendido.
   e) Tratamientos PGC por defecto cuando el enunciado no dice cómo ajustar (K1: 10-30 % del balance).
3. Claude ya hace bien sin ayuda: volumen (400k filas), PDFs multipágina y en 4 idiomas, imágenes (no inventa), inyecciones
   (ninguna obedecida en 6 equipos), reglas aprendidas del histórico con deriva y ruido.
4. Preguntas a la organización a primera hora: ¿se ejecuta nuestro código en el oculto?, ¿el oculto trae la misma normativa?,
   ¿puede run.py llamar a Claude?, ¿restan los falsos positivos?, ¿cómo se puntúan autonomía y auditabilidad?

## Ronda 7 (2 de noviembre): datos escritos por PERSONAS, no por Claude
Hasta la ronda 6 todos los retos los escribió Claude. Para comprobar si las conclusiones aguantan, dos benchmarks públicos:
- APEX-Accounting (Mercor con Ramp): 10 encargos de cierre de un bufete (conciliaciones de nóminas y de cuentas a cobrar, WIP,
  devengos, variaciones), escritos, resueltos y con rúbrica de 89 criterios hechos por contables. Corrige un juez a ciegas.
- FinBalance: paquetes de 5-40 documentos OCR por empresa y periodo; asientos + balance exacto o código de contradicción
  (23 códigos). Escenarios, plantillas y reglas fiscales escritos por personas. 30 ejemplos resueltos + 60 públicos, y run.py
  ejecutado sobre 143 paquetes ocultos de otra semilla (y en la ronda 8, sobre 150 más que nadie había usado).

  APEX (criterios cumplidos)    sin preparación 75/89 (84 %)   plantilla v6 77/89 (87 %)
  FinBalance, acierto global    público   oculto   oculto2
  A1, A2 (sin preparación)      0,97/0,95 0,85/0,85 0,89/0,89
  B1, B2 (plantilla v6)         0,93/0,90 0,85/0,74 0,87/0,79
  C1, C2 (plantilla v7)         0,90/0,95 0,80/0,83 0,86/0,89
Referencia publicada: en APEX, Opus 4.8 con un agente en bucle saca 62 % en este mismo set [nota del 6-nov-2026: cifra sin fuente comprobada; no entra en ningún resultado]; en FinBalance, el mejor modelo
del paper acierta el balance exacto en el 46 % de los paquetes. Claude Code escribiendo código sobre ejemplos resueltos: 85-89 %.

Lectura honesta:
1. Con datos de personas la plantilla NO sube la nota: empate en APEX y en FinBalance, y un equipo con v6 bajó (0,74) por
   emitir varios códigos por paquete cuando la clave lleva uno (regla de la v6 aprendida en retos donde sí había varios).
2. Lo que de verdad funciona es el principio, no la plantilla: "el modelo interpreta, el código calcula". Con él, Claude Code
   duplica la nota publicada de los modelos que responden directamente.
3. Dónde se pierden los puntos con datos reales:
   - FinBalance: el 80 % de los fallos del oculto son combinaciones que los ejemplos resueltos no tenían (factura de hosting con
     GST indio, ventas con CGST/SGST, pagos de varias facturas, divisa). Todos los tipos de documento estaban en el público
     sin respuesta, pero nadie los usó para comprobar cobertura.
   - APEX: casi nunca por calcular mal. Por la forma de responder: dos cifras para la misma pregunta (el juez da 0), decir
     "varianza 0, está justificado" cuando piden las partidas conciliatorias, añadir un asiento de intereses que nadie pidió,
     recalcular desde datos brutos en vez de usar el fichero del encargo, no dar subtotales por proveedor.
4. Cambios de la v7: skill nueva responder-encargo (7 reglas de forma), cobertura y documentos no consumidos en generalizar,
   y "uno o varios códigos" decidido por los ejemplos resueltos. La v7 recupera la caída de la v6 pero no supera a los equipos
   sin preparación: estos retos ya están en el techo del código determinista con 30 ejemplos.

## CONCLUSIÓN DESPUÉS DE LA RONDA 7 (8 rondas, 62 equipos, 17 retos)
- Claude Code solo ya es muy bueno. La plantilla es un SEGURO, no un motor: evita los ceros (run.py que se cae, parámetros
  fijos, normativa cambiada) y fija la forma de responder. En datos limpios de personas, no añade puntos.
- Para convencer al equipo, el argumento no es "mi plantilla saca más", sino: "con el mismo Claude, el que se cae saca 0;
  esto son 10 reglas que evitan caerse, y el principio que duplica la nota de los benchmarks publicados".
