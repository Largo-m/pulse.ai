### Approval block — {{step_label}} (mandatory format)

Only when there is something to correct — a review with nothing left closes the
loop with the outcome block above instead. You have **no** external tool to ask
with. End your reply with a **text block** that Pulse renders in the terminal,
exactly in this format — the block itself
stays in Portuguese, because the person reading it is the user:

```text
Preciso de algumas informações antes de continuar.
1. Aprovar {{step_label}} e avançar?
A) Sim, aprovar e continuar
B) Não, preciso de ajustes (descreva)
C) Pular — seguir sem corrigir as findings agora
D) Cancelar workflow
```

Option C is this phase's exit, and it is a legitimate answer: what you wrote
stays on disk, nothing gets fixed in this run, and the pipeline moves on. Say so
in one line right before the block, so the choice is made with open eyes. Do not
argue for it or against it — the decision is the user's.

FORBIDDEN in this phase:
- Editing application code (only `.pulse/specs/` and `.pulse/reviews/` files are
  allowed).
- Sending any text outside the ```text block when asking or requesting approval.
- Moving to the next phase without explicit approval.
