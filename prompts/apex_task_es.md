# Reto APEX: encargos de cierre escritos por contables

Hackathon simulado. Los encargos, los datos y las respuestas correctas los han escrito contables de verdad
(benchmark APEX-Accounting de Mercor y Ramp). Empresa: Sterling, Marsh & Associates LLP, bufete de Filadelfia,
cierre de diciembre de 2024.

- `mundo/`: los ficheros compartidos de la empresa (exportaciones de QuickBooks, Gusto, Clio, extractos
  bancarios en PDF, papeles de trabajo en Excel...). `mundo/quickbooks_app/` son los datos de la aplicación
  QuickBooks (diario de asientos, plan de cuentas, maestro de proveedores, transacciones bancarias).
- `tareas/T<n>/ENCARGO.md`: el encargo, en inglés. `tareas/T<n>/archivos/`: ficheros propios de ese encargo
  (memorandos, notas de revisión, borradores).

Entrega: para cada tarea, `salida/T<n>.md` con tu respuesta final, en inglés, como la escribirías en el mensaje
final a quien te hizo el encargo: las cifras pedidas con dos decimales y $, cada partida con su causa, y los
asientos propuestos con cuenta, importe y lado cuando se pidan.

Puntuación: cada tarea tiene una rúbrica oculta de criterios binarios escrita por el contable (cifras exactas
±0,01 $ y explicaciones). Se puntúa el % de criterios cumplidos, leyendo SOLO tu fichero de salida.
No hay red. Puedes usar Python (pandas, openpyxl, pdfplumber/pypdf si están instalados; si no, pdftotext).
