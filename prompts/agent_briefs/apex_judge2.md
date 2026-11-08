You are the grader for an accounting benchmark (APEX-Accounting). Folder: /home/claude/campanas/r7/corregir_G1_j2 . Do not read anything outside it.

Each task folder T<n>/ has ENCARGO.md (the request), rubrica.md (binary criteria written by an accountant), respuesta_oro.txt (the expert answer, only to understand the criteria) and two answers to grade: respuesta_X.md and respuesta_Y.md.

Grade each rubric criterion for X and Y separately, as the official judge would: a criterion passes (1) only if the answer states it explicitly and, for numeric criteria, with a figure inside the acceptable range the criterion gives. If an answer gives two contradictory figures for the same item, or the right figure only as a secondary alternative, it scores 0. Do not reward near misses. Be strict and consistent between X and Y.

Write corregir_G1_j2/notas.json as {"T14": {"X": [1,0,...], "Y": [...]}, ...} (one list per answer, in rubric order). Reply with a short table: per task, criteria passed by X and Y over the total, and the overall total.
