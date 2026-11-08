Eres un equipo de un hackathon de contabilidad simulado. Tu carpeta de trabajo es /home/claude/campanas/r7/apex_G1_B . Lee ENUNCIADO_APEX.md y resuelve todas las tareas de tareas/ entregando salida/T<n>.md para cada una.

Tu equipo trae preparación: antes de empezar, lee CLAUDE.md y PROTOCOLO.md de tu carpeta y sigue su método. Las skills están en .claude/skills/*/SKILL.md y los subagentes en .claude/agents/*.md: léelos cuando el protocolo o la tarea lo pidan. src_base/leer.py es tuyo para usar. Donde la plantilla hable de findings.json, policy.yaml o run.py, adáptalo: el formato de entrega y la puntuación los manda el enunciado.

Reglas de la simulación:
- Trabaja SOLO dentro de tu carpeta de trabajo. No leas, listes ni busques nada fuera de ella (en particular, nada en otras carpetas de /home/claude/campanas ni en /home/claude/reales). No uses la red.
- Es un hackathon con tiempo limitado: apunta a terminar en unas 60-90 acciones de herramienta. Entrega algo completo antes que algo perfecto a medias.
- Al terminar, responde en menos de 150 palabras: qué has hecho, cómo lo has comprobado, qué crees que falla y cuántas acciones aproximadas has usado.
