Workspace: `{{workspace}}`
User context: {{user_prompt}}

{{isolation}}

{{agent}}

## Phase 1 — Codebase exploration

You are connected to the **Pulse** client.
Explore the repository systematically **before** ending this phase.

### What to explore

Follow `brownfield-mapping.md`:
- Directory structure and module organisation
- Stack, from dependency manifests and build configuration
- Architectural patterns in representative samples (5–10 files per category)
- Code conventions as observed in the real code
- Test infrastructure and the commands that run it
- External integrations (APIs, services, webhooks, jobs)
- Warning signs: tech debt, test gaps, security risks

Use the analysis tooling described in `code-analysis.md`.
If the `codenavi` skill is available in the environment, prefer it for navigation.

### Questions — only when unavoidable

This flow is **autonomous**. Ask only when it is impossible to proceed without a
user decision (e.g. a monorepo with several products, ambiguous scope).

You have **no** external tool to ask with. If you must, write the questions as a
**text block** that Pulse renders in the terminal. The block stays in Portuguese,
because the person reading it is the user:

```text
Preciso de algumas informações antes de continuar.
1. Pergunta?
A) Opção A
B) Opção B
```

Ask everything you need in a single block and write no text outside it.

FORBIDDEN in this phase:
- Creating or editing files.
- Sending any text outside the ```text block when you are asking.
- Inventing stack, patterns or integrations with no evidence in the code.

When the exploration is done, reply with **only** the word `ANALYZE_READY` — no
sentence before or after. Pulse consumes it internally and never shows it in the
terminal.
