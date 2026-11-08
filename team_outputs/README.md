# Team outputs

Everything the agents delivered, unedited. Agents worked in Spanish, so notes are in Spanish.

| Folder | What | Produced by |
|---|---|---|
| `finbalance/<team>/run.py` | The program each team shipped; `ctb reproduce` re-executes it on the hidden splits | one Claude Code agent per team |
| `finbalance/<team>/public_predictions.json` | The team's answers for the 60 public packets (original FinBalance ids) | same |
| `finbalance/<team>/NOTES_es.md` | The team's own ten-line notes | same |
| `finbalance/direct/sample40_trial1/` | Direct answers, 40 packets, first trial | 8 agents, 5 packets each |
| `finbalance/direct/sample40_trial2/` | Same 40 packets, second trial | 8 fresh agents |
| `finbalance/direct/rest103/` | Direct answers for the other 103 hidden-A packets (same prompt as trial 2) | 15 agents, 7 packets each |
| `finbalance/direct/sample40_trial3/` | Follow-up control (6 November): the 40 packets, trial-2 brief naming the five files | 8 fresh agents, Claude Opus 5.5 |
| `finbalance/direct/sample40_examples3/` | Follow-up: the same brief plus three solved examples | 8 fresh agents, Claude Opus 5.5 |
| `finbalance/direct/sample40_sonnet_control/`, `sample40_sonnet_examples3/` | The same two arms, launched on Claude Sonnet 5.5 by mistake; reported apart | 16 agents |
| `finbalance/direct/sample40_cli_control/` | Second follow-up (8 November), control: the 1b brief | 8 `claude -p` sessions, Claude Opus 5.5 |
| `finbalance/direct/sample40_cli_puntuacion/` | Second follow-up: control plus the scoring section of the code teams' brief | 8 sessions |
| `finbalance/direct/sample40_cli_ejemplos3/` | Second follow-up: the 1b examples arm repeated | 8 sessions |
| `finbalance/direct/sample40_cli_skill/` | Second follow-up: control plus Anthropic's `journal-entry-prep` skill | 8 sessions |
| `finbalance/direct/sample40_cli_memoria_a/`, `sample40_cli_memoria_b/` | Second follow-up: control plus the agent's own notes from 8 checked practice packets (two chains) | 8 sessions each |
| `apex/<group>_<arm>/T<n>.md` | Final answers to each APEX request | one agent per group and arm |

Teams: A1 to A4 no preparation; B1, B2 scaffold v6; C1, C2 scaffold v7. APEX arm A is no
preparation, arm B scaffold v6. The briefs each agent received are in `prompts/agent_briefs/`.
