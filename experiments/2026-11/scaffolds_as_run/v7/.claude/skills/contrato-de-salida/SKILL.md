---
name: contrato-de-salida
description: Fija el formato de entrega exacto, crea un validador y hace una primera entrega trivial válida. Úsalo en la primera hora, antes de construir reglas.
---
1. Copia literalmente la especificación de entrega de la organización a `CONTRATO.md` (nombres de fichero, campos, tipos,
   valores permitidos, categorías). Si algo es ambiguo, apúntalo como pregunta y elige la lectura más probable.
2. Escribe `src/validate.py`: comprueba esquema, tipos, categorías permitidas, que todo id citado exista en los datos,
   que no haya duplicados (tipo, ref), y que cada fila tenga regla, evidencia y explicación. Sale con código 1 si falla.
3. Genera una entrega trivial válida (por ejemplo, lista vacía o un hallazgo seguro) y súbela para confirmar el formato.
4. Desde aquí, ninguna entrega sin pasar `validate.py` (el hook lo impide).
