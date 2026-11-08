---
name: normativa
description: Convierte políticas, manuales y circulares en parámetros y reglas que el código aplica, de forma que aguante cambios de redacción, circulares nuevas, retroactividad, ámbitos por sociedad y excepciones de excepciones. Úsalo siempre que haya un documento normativo en prosa.
---
Lección de las simulaciones: un equipo perdió 14 hallazgos del oculto porque su código buscaba la frase "donde dice … debe decir"
y la circular nueva decía "se da nueva redacción … sustituyéndose «X» por «Y»". Otro perdió 4 por fijar la tolerancia del público.

1. Parámetros por estructura, no por frase:
   - Tabla de parámetros si existe (| nombre | valor |): fuente principal.
   - Enmiendas: extrae pares de valores citados («…» o "…") dentro de una cláusula que menciona un apartado (\d+(\.\d+)+);
     el primero es el viejo y el último el nuevo, sea cual sea el verbo (modifica, sustituye, nueva redacción, debe decir, queda redactado).
   - Importes con cualquier formato (500,00 euros / 500 € / EUR 500) y porcentajes; normaliza antes de comparar con el viejo.
   - Enmiendas SIN comillas ("el umbral del apartado 5.5.1 pasa a ser de 600 euros", "se eleva a 750 € el importe fijado en 3.1.3"):
     para cada cláusula que cite un apartado, toma TODOS los importes/porcentajes de la cláusula; el que coincide con el valor
     vigente de ese apartado es el viejo, el otro es el nuevo. Si solo hay uno, es el nuevo.
   - Tablas en circulares o anexos (Antes | Ahora, "Cuadro de parámetros"): parsea cualquier tabla markdown; una fila con un nombre
     de parámetro y dos importes es una enmienda; un cuadro completo sustituye a la tabla del manual (los valores repetidos no cambian nada).
   - Fe de erratas: corrige el valor desde el origen (como si siempre hubiera dicho eso), no desde su fecha.
   - Vigencia que no está en el documento ("desde su publicación en el registro"): búscala en cualquier CSV de registro de normativa.
     Vigencia futura (efectos posteriores al cierre): la circular existe pero no aplica al periodo.
   - Circulares que cambian DEFINICIONES del glosario (qué es "suministro", "proveedor recurrente"...) cambian funciones, no umbrales:
     cada definición del glosario debe ser una función parametrizable por fecha.
2. Jerarquía en un solo algoritmo (src/normativa.py), probado con casos sintéticos:
   vigencia (fecha de efectos, "al día siguiente", retroactiva) → ámbito (todas o una sociedad) → anulada (ex tunc: como si nunca
   existió) o derogada (ex nunc: deja de aplicar desde su fecha) → especial prevalece sobre general SALVO cláusula expresa
   ("con independencia de lo dispuesto en …", "también se aplica a …") → posterior prevalece sobre anterior.
   El resultado es una tabla parámetro × sociedad × fecha que el resto del código consulta con (parámetro, sociedad, fecha del hecho).
3. Glosario: las definiciones (p. ej. "proveedor recurrente", "día hábil", "importe" con o sin IVA) son funciones, no texto.
4. Prelación entre categorías: si la política dice "solo se reporta la primera", aplícalo al final, sobre todos los hallazgos de un documento.
5. Detector de lo no entendido (OBLIGATORIO, con test): al final del parseo, cuenta los importes y porcentajes de cada circular
   que no se han convertido en parámetro; si hay alguno, run.py lo imprime en grande y lo escribe en data/work/. En la ronda 5,
   el mejor equipo seguía perdiendo 13+10 hallazgos por enmiendas con fórmulas nuevas que su parser ignoró sin avisar.
   Detector de lo no entendido: toda cláusula normativa con un número, un importe o un valor citado que ningún parser haya consumido
   va a `data/work/normativa_no_entendida.txt` y al log de run.py. Si el fichero no está vacío, revisarlo antes de entregar.
   En el benchmark oculto, una circular no entendida debe hacer que los hallazgos afectados vayan a review, no desaparecer.
6. Si el reto permite llamar a un modelo dentro de run.py (pregúntalo), usa el modelo SOLO para convertir la normativa en el JSON de
   la tabla del paso 2, valídalo con esquema y contrástalo con el parser determinista; si discrepan, gana el más conservador y se avisa.
7. Antes de congelar: escribe 3 circulares sintéticas con redacciones distintas (otra fórmula de enmienda, ámbito específico con
   cláusula expresa, derogación) y comprueba que la tabla cambia como debe.
