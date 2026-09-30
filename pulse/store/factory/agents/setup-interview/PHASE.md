Workspace: `{{workspace}}`
User context: {{user_prompt}}

<!-- include: isolation -->

## Phase 1 — Analysis and questionnaire

You are connected to the **Pulse** client.
Analyse the workspace and the existing artefacts **before** asking anything.

Check whether there is **explicit** information about vision, target audience, v1
focus and constraints (in `.pulse/specs/project/PROJECT.md`, README or docs).

### Questions — as a structured text block

You have **no** external tool to ask the user with. When you need information,
write the questions as a **text block** in the exact format below. Pulse detects
that block, renders an interactive questionnaire in the terminal and hands the
answers back to you.

The questions are written in Portuguese — the person reading them is the user.

- Open a ```text fence and use exactly this as the first line:
  `Preciso de algumas informações antes de continuar.`
- Number every question (`1.`, `2.`, …), one per line.
- Every option gets an uppercase letter (`A)`, `B)`, …); Pulse adds **Outro** itself.
- Ask **all** the questions you need in a **single** block.
- Cover the topics from the `project-init.md` playbook above (vision, audience,
  v1 scope, constraints).

Example:
```text
Preciso de algumas informações antes de continuar.
1. Qual é a visão do produto?
A) Plataforma de paper trading para estudo
B) Ferramenta de análise para investidores reais
2. Quem é o público-alvo?
A) Investidores iniciantes
B) Desenvolvedores estudando arquitetura
```

FORBIDDEN in this phase:
- Creating or editing files.
- Sending any text outside the ```text block when you are asking.
- Running shell/python to simulate questions.
- Closing this phase while a mandatory field is still undocumented.

### Closing the phase

When nothing is left to ask, present what you gathered — vision, audience, v1
scope, constraints — so the next step can write the artefacts from it, and close
the phase.

Do **not** ask for approval to move on: this loop runs end to end. The questions
above are the only thing you ask the user. Closing your turn is what hands what
you gathered to the artefacts step.
