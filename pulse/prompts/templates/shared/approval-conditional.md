### Approval block — {{phase_label}} (mandatory format)

Use this block **only when {{condition}}**. Until that holds, your reply ends
with the clarify question block — never with the approval one.

Pulse renders it in the terminal, exactly in this format. The block itself stays
in Portuguese, because the person reading it is the user:

```text
Preciso de algumas informações antes de continuar.
1. Aprovar {{phase_label}} ({{artifact_path}}) e avançar?
A) Sim, aprovar e continuar
B) Não, preciso de ajustes (descreva)
C) Cancelar workflow
```

FORBIDDEN in this phase:
- Editing application code (only `.pulse/specs/` files are allowed).
- Sending any text outside the ```text block when asking or requesting approval.
- Moving to the next phase without explicit approval.
