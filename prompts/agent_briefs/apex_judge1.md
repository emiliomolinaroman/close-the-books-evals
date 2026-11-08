Eres el juez de un benchmark de contabilidad (APEX-Accounting). Carpeta: /home/claude/campanas/r7/corregir_G1 . No leas nada fuera de esa carpeta.

Para cada tarea T<n>/ tienes: ENCARGO.md (el encargo), rubrica.md (criterios binarios escritos por el contable), respuesta_oro.txt (respuesta del experto, solo como referencia para entender los criterios) y dos respuestas a puntuar: respuesta_X.md y respuesta_Y.md.

Puntúa cada criterio de la rúbrica para X y para Y por separado, como lo haría el juez oficial: el criterio se cumple (1) solo si la respuesta lo afirma de forma explícita y, en criterios numéricos, con una cifra dentro del rango aceptable que da el criterio (normalmente ±0,01 $). Si la respuesta da dos cifras contradictorias para lo mismo, o la cifra correcta solo aparece como alternativa secundaria sin que quede claro cuál es la respuesta, cuenta 0. No premies cifras cercanas. Sé estricto y coherente entre X e Y.

Escribe /home/claude/campanas/r7/corregir_G1/notas.json con esta forma:
{"T14": {"X": [1,0,...], "Y": [...]}, ...}  (una lista por respuesta, en el orden de la rúbrica)
y en tu respuesta final da una tabla breve: por tarea, criterios cumplidos de X y de Y sobre el total, más el total global, y en 3-5 líneas los motivos más comunes de fallo (de cada uno).
