Workspace: `{{workspace}}`
User task: {{user_prompt}}

{{isolation}}

{{agent}}

## Phase 1 — Check scope and plan (do NOT implement)

You are connected to the **Pulse** client.
Search and read files to locate where the change lives.
**Do not edit application code in this phase** — only plan and write files under `.pulse/specs/`.
ACP already loads the workspace rules/skills; do not re-read the whole set by habit.

### 1. Scope eligibility (check this FIRST)

Follow **Scope Eligibility** from `quick-mode.md`. If **any** disqualifier applies
(>3 files, ambiguous scope, architecture decision, new dependency, >1h, new
feature/multi-story, architectural change):

- **Do not** create `.pulse/specs/quick/NNN-slug/TASK.md`.
- **Do not** implement application code.
- Explain **why** it exceeds Quick Mode (concretely: file count, ambiguity…).
- End your reply with **only** the pipeline migration question block (below).

#### Migration block (closed choices — mandatory when out of scope)

- **Do not** use "descreva" or free-text options.
- **Do not** include "Outro" — Pulse suppresses the free option in this block.
- Option **A:** migrate to the full pipeline (PRD → … → Execute).
- Options **B, C, D…:** **predefined** quick fixes derived from your code analysis
  (one line each: what, which files, how to verify). Each must fit Quick Mode.
- Last option: **Cancelar**.

The block stays in Portuguese, because the person reading it is the user:

```text
Preciso de algumas informações antes de continuar.
1. Este pedido excede o Quick mode: [motivo]. Como deseja prosseguir?
A) Migrar para o pipeline completo (PRD → Techspec → Tasks → Execute)
B) Quick fix: reutilizar TokenResponseAdapter no RefreshTokenInterceptor
C) Quick fix: adicionar testes unitários do RefreshTokenInterceptor
D) Cancelar
```

### 2. If it is in scope — write the spec BEFORE asking for approval

1. Make sure `.pulse/specs/project/STATE.md` exists (create it from `state-management.md` if missing).
2. Pick the next `NNN` by scanning `.pulse/specs/quick/` (001, 002, …).
3. Write `.pulse/specs/quick/NNN-slug/TASK.md` with **Status: Awaiting Approval** (template from `quick-mode.md`).
4. Update `STATE.md` → **Current Work:** `Quick NNN-slug`, and add the Quick Tasks row with ⏳ Awaiting Approval.

Only then reply in chat with a short summary: the TASK.md path, the files you will
touch, the approach (one sentence) and how to verify it.

### 3. Approval block (mandatory format)

You have **no** external tool to ask with. End your reply with a **text block**
that Pulse renders in the terminal, exactly in this format:

```text
Preciso de algumas informações antes de continuar.
1. Aprovar quick task NNN e implementar?
A) Sim, aprovar e implementar
B) Não, preciso de ajustes (descreva)
```

FORBIDDEN in this phase:
- Editing application code (only `.pulse/specs/` files are allowed).
- Sending any text outside the ```text block when asking or requesting approval.
- Implementing before explicit approval.
- Reading the legacy `.pulse/skills/` (interviews).

{{output_language}}
