---
name: classify
description: Escolhe flow full ou quick
runtime: cursor
model: Auto
permission_policy: deny_writes
---

# quick-mode.md

# Quick Mode

**Goal:** Execute small, ad-hoc tasks with the same quality principles but without full pipeline ceremony.

**Trigger:** "Quick fix", "Quick task", "Small change", "Bug fix", "Just do X"

## Approval Gate (MANDATORY)

**Never implement automatically.** Describing a quick task is NOT permission to code.

After the pre-implementation check (step 2), **STOP and wait** for explicit user approval before editing application code or running destructive commands.

Collect approval via [user-input.md](user-input.md) CLI format (see **Approval and confirmation** section).

**Do NOT treat as approval:**

- The user describing the bug or request
- Research, reading files, or locating where code lives
- Presenting the pre-implementation check itself
- Creating or updating `.pulse/specs/` documentation (allowed before approval)
- Silence or the user sending a follow-up question

If the user adjusts scope in their reply, update `.pulse/specs/quick/NNN-slug/TASK.md` and **ask again**.

⚠️ **Do not proceed to Implement without spec files on disk and CLI approval.**

## When to Use

| Use quick mode             | Use full pipeline                   |
| -------------------------- | ----------------------------------- |
| Bug fixes with known cause | New features with multiple stories  |
| Config changes             | Architectural changes               |
| Small UI tweaks            | Features requiring design decisions |
| Adding a field/column      | Multi-component features            |
| One-off scripts            | Anything with unclear scope         |
| Dependency updates         | Features requiring user stories     |

**Rule of thumb:** If you can describe it in one sentence AND it touches ≤3 files, it's a quick task.

## Scope Eligibility (check FIRST)

Before creating `.pulse/specs/quick/` files, verify the request fits Quick mode. If **any** disqualifier applies, **do not** create a quick TASK.md and **do not** proceed as Quick mode.

| Disqualifier | Example |
| --- | --- |
| **>3 files** to touch | Change spans 4+ modules or layers |
| **Not one sentence** | Multiple stories, unclear boundary |
| **Unclear scope** | "Improve the app", "fix auth" without specifics |
| **Design decision required** | Choosing architecture, patterns, or UX approach |
| **New dependency** | Adding a package or external service |
| **>1 hour** estimated | Large refactor disguised as a fix |
| **New feature / multi-story** | Not a fix or small tweak |
| **Architectural change** | New module, layer, or integration pattern |
| **5+ quick tasks** same area | Compounding fixes → treat as a feature |

When disqualified:

1. State **why** it exceeds Quick mode (concrete: file count, ambiguity, etc.)
2. **Do not** create `.pulse/specs/quick/NNN-slug/TASK.md`
3. **Do not** implement application code
4. Ask whether to migrate to the full pipeline via [user-input.md](user-input.md) (see **Pipeline migration**)
5. **Stop** and wait for the user's choice

**Never auto-migrate.** Never start PRD/Techspec/Tasks without explicit user confirmation.

If the user chooses **reduce scope**, re-run eligibility with the narrowed request. Only create quick spec files when the reduced scope passes all checks.

If the user chooses **full pipeline**, begin at [prd.md](prd.md) → `.pulse/specs/features/[feature]/PRD.md` (auto-size Techspec and Tasks per SKILL.md).

## Process

### 1. Describe the Task

User provides a clear, one-sentence description. If vague, stop and collect specifics via [user-input.md](user-input.md) CLI format before creating spec files:

```text
Preciso de algumas informações antes de continuar.

1. O que exatamente está quebrado e qual o comportamento esperado?

A) [Cenário A — descreva]
B) [Cenário B — descreva]
C) Outro (descreva)

Resposta:
```

### 2. Pre-Implementation Check (STOP HERE)

**Prerequisite:** Scope eligibility passed (see above). If not, use **Pipeline migration** — do not create quick spec files.

**MANDATORY: Create spec files BEFORE responding to the user with the plan.**

After research and before the chat reply that presents the plan:

1. Ensure `.pulse/specs/project/STATE.md` exists (create from [state-management.md](state-management.md) template if missing)
2. Pick the next `NNN` by scanning `.pulse/specs/quick/` (001, 002, …)
3. Create `.pulse/specs/quick/NNN-slug/TASK.md` with **Status: Awaiting Approval**
4. Update `STATE.md` → **Current Work:** `Quick NNN-slug` and add a row to Quick Tasks with status ⏳ Awaiting Approval

Only then respond in chat with a brief summary plus the TASK.md path:

```
Quick Task NNN: [description]
Spec: .pulse/specs/quick/NNN-slug/TASK.md
Files: [list ONLY files to touch]
Approach: [one sentence]
Verify: [how to prove it works]
```

Then end the response with approval via [user-input.md](user-input.md):

```text
Preciso de algumas informações antes de continuar.

1. Aprovar quick task NNN e implementar?

A) Sim, aprovar e implementar
B) Não, preciso de ajustes (descreva abaixo)

Resposta:
```

**Wait for user approval.** Do not edit application code until they confirm.

If scope grows during research (>3 files, design fork, new dependency), **stop** quick mode immediately and switch to **Pipeline migration** — do not implement partial work without user choice.

### 3. Implement (only after approval)

Update TASK.md **Status: In Progress**, then implement.

Follow [coding-principles.md](coding-principles.md):

- Simplest code that works
- Touch ONLY listed files
- No scope creep — fix the thing, nothing else

### 4. Verify

Run verification from TASK.md. Mark done only after verification passes.

### 5. Track

1. Update `.pulse/specs/quick/NNN-slug/TASK.md` → **Status: Done**, check verification boxes
2. Create `.pulse/specs/quick/NNN-slug/SUMMARY.md` with what changed and verification result
3. Update `.pulse/specs/project/STATE.md` → Quick Tasks row to ✅ Done

---

## Structure

Quick tasks live separately from planned features:

```
.pulse/specs/
└── quick/
    └── NNN-slug/
        ├── TASK.md       # Description + verification
        └── SUMMARY.md    # What was done
```

**TASK.md template (create at step 2, before chat response):**

```markdown
# Quick Task NNN: [Title]

**Date:** [date]
**Status:** Awaiting Approval | In Progress | Done | Blocked

## Description

[One sentence: what and why]

## Plan

**Approach:** [one sentence]

## Files to Touch

- `src/path/to/file.ts` — [planned change]

## Verification

- [ ] [How to verify it works]
- [ ] [Expected behavior after fix]
```

**SUMMARY.md template (create at step 5, after verification):**

```markdown
# Summary: Quick Task NNN — [Title]

**Completed:** [date]

## What Changed

- `src/path/to/file.ts` — [what changed]

## Verification

[Result: tests run, manual checks, pass/fail]
```

---

## Guardrails

- **Scope check first** — If not eligible for Quick mode, ask pipeline migration; never force-fit
- **Spec files first** — Create `.pulse/specs/quick/NNN-slug/TASK.md` (and update STATE.md) before the chat reply with the plan — **only when eligible**
- **Approval required** — Never edit application code without CLI confirmation after spec files exist
- **Max 3 files** — Exceeding this triggers pipeline migration question, not silent escalation
- **Max 1 hour** — If longer, scope is wrong — offer full pipeline
- **No design decisions** — If choosing between approaches, offer full pipeline
- **No new dependencies** — Adding packages triggers pipeline migration question
- **Track everything** — TASK.md before chat reply; SUMMARY.md after verification
- **No git operations** — Do not commit or suggest commit messages unless the user explicitly asks

---

## Tips

- **Quick ≠ sloppy** — Same coding principles apply, just less ceremony
- **When in doubt, ask migration** — Offer full pipeline; let the user decide
- **Quick tasks compound** — If you're doing 5+ quick tasks for the same area, it's a feature that needs planning
- **Verify before marking done** — The whole point is quality, even for small tasks
- **Research ≠ implement** — Reading code to locate the fix is fine; application edits wait for approval
- **Docs before chat** — The user should always be able to open TASK.md; never present a plan only in chat

# prd.md

# PRD

**Goal**: Capture WHAT to build with testable, traceable requirements.

Read [invariants.md](invariants.md) first. If the feature has ambiguous gray areas, trigger [discuss.md](discuss.md) inside this phase. Write every gray area to the [Ambiguity Ledger](ambiguity.md).

**Audience: the product team.** You are talking to whoever owns the product, not
to an engineer. Every question you ask in this phase must be answerable by
someone who has never opened the codebase. Technical decisions belong to Techspec
— see **Product language only** below.

**No open question survives this phase.** There is no "I assumed X". While any
gray area, doubt, or open question remains, you ask — and you keep asking, one
CLI batch per turn, until the ledger is clean. See **Clarify loop** below.

## Process

### 1. Load confirmed lessons

Read STATE.md Lessons Learned with `Status: confirmed` that match this feature's area. Skip `candidate` and `quarantined`. See [lessons.md](lessons.md).

### 2. Clarify Requirements

Thinking partner, not interviewer. Read `.pulse/specs/`, codebase, user message. Draft from what is known.

Facts you look up (Knowledge Verification Chain). Decisions you ask via [user-input.md](user-input.md).

**Must resolve before writing PRD.md:**

- **Motivating Problem** — concrete pain and the simplest end-to-end observable outcome that solves it. Slice 1 of Tasks delivers this outcome.
- Who it is for
- What success looks like
- Constraints
- Explicit out of scope

Do not park a wanted capability in Out of Scope to fit a slice budget — that needs a follow-up spec or a recorded user decision.

### 3. User Stories (P1 = MVP)

P1 is a **vertical slice**: demo-able, not backend-only. Each story independently testable.

### 4. Acceptance Criteria (EARS)

Every AC uses **EARS** and contains SHALL. One behavior per criterion. Concrete values, not "gracefully".

| Pattern | Template |
| ------- | -------- |
| Ubiquitous | The [system] SHALL [response] |
| Event-driven | WHEN [trigger] THEN the [system] SHALL [response] |
| State-driven | WHILE [state] the [system] SHALL [response] |
| Optional-feature | WHERE [feature is present] the [system] SHALL [response] |
| Unwanted-behavior | IF [undesired condition] THEN the [system] SHALL [response] |
| Complex | WHILE [state], WHEN [trigger] the [system] SHALL [response] |

If you cannot write it as a test, rewrite it.

### 5. Gray-area sweep + ledger

Follow [ambiguity.md](ambiguity.md). Sweep the feature for behavior the product
team still has to choose. Every gray area becomes a ledger row, and every row
leaves this phase as `decided` (the product team chose) or `n/a` (the dimension
does not apply to this feature). Nothing else is a valid closing status.

The implicit-requirement sweep — idempotency, concurrency, retry, rate limits,
observability, data lifecycle, external-dependency failure, state-transition
integrity — does **not** run here. Techspec owns it ([techspec.md](techspec.md)). Do
not ask the product team about those dimensions.

What you do sweep here is the product-visible side of the same feature: what the
person using it sees, chooses, and is promised. If a technical dimension turns
out to have a user-visible consequence, ask about the consequence in product
words, never about the mechanism.

### 6. Surface and tests (conditional)

If there is a public surface, write [surface.md](surface.md) before internal design. Write [tests.md](tests-catalog.md) for Large/Complex (and Medium with a public surface).

If a [threat-model.md](threat-model.md) trigger is present, note it here; the model itself is written in Techspec.

### 7. Closure gate

Before presenting the spec:

1. Every AC has one interpretation and a precise expected outcome
2. Ledger has no `open` rows **and no `assumed` rows** — every row is `decided` or `n/a`
3. Motivating Problem is stated; P1 delivers it
4. `python3 <skill-dir>/scripts/validate_prd.py <feature>` exits 0 ([gates.md](gates.md))

Fail any of these and you are still in the **Clarify loop** — ask, do not present.

Then confirm with the user via CLI. Do not start implementation because the spec file exists.

Changing an approved spec later uses [spec-change.md](spec-change.md).

---

## Clarify loop (mandatory)

The phase runs as a loop, not a single pass. Each turn:

1. Do every bit of autonomous work you can — read the codebase, read
   `.pulse/specs/`, draft the spec, fill what the answers already settle
2. List what is still undecided
3. If **anything** is undecided, end the turn with one CLI clarify batch
   ([user-input.md](user-input.md)) and stop. No approval block this turn.
4. When the answers arrive, fold them into `PRD.md` and the ledger, then go
   back to step 1

You leave the loop only when the closure gate passes. Then, and only then, the
turn ends with the approval block instead of a clarify batch.

**A clarify batch and an approval block never appear in the same turn.** Asking
and asking-for-approval are different states; mixing them lets a doubt slip
through as approved.

**Forbidden in this loop:**

- Writing `assumed` in the ledger. An agent-chosen default is exactly the doubt
  this phase exists to remove. If you would have assumed it, ask it.
- Writing `open` and presenting anyway ("we can decide later", "TBD",
  "to be confirmed during implementation").
- Presenting the spec while a question is pending.
- Silently narrowing scope to avoid a question.
- Answering your own question with "the codebase already does X" — the codebase
  shows what *is*, not what the product team wants.

**Batch shape:** follow [user-input.md](user-input.md). At most 2 independent
questions per batch; dependent questions one at a time. Lead each question with
a recommended option and a one-line rationale in product terms, so the product
team can accept it in one keystroke.

There is no cap on the number of rounds. A sixth round of clarification is
cheaper than a feature built on a guess.

---

## Product language only

Every question in this phase is about the product: what the person using it
wants, sees, chooses, or is promised. If answering requires knowing the stack,
it is a Techspec question.

| Ask here (product)                                         | Never ask here (Techspec owns it)              |
| ---------------------------------------------------------- | -------------------------------------------- |
| "What should the person see when the payment fails?"        | "Do we retry with exponential backoff?"       |
| "Can two people edit the same order at once?"               | "Do we use optimistic locking or a mutex?"    |
| "For how long must a cancelled order stay visible?"         | "What TTL do we set on the cache?"            |
| "Who is allowed to approve a refund?"                       | "Do we check the role in the middleware?"     |
| "How fast does this have to feel to be usable?"             | "What is the p95 latency budget per service?" |
| "What happens to the person mid-flow if the provider is down?" | "Do we add a circuit breaker?"             |

**Banned from the wording of any question in this phase:** API, endpoint,
schema, migration, index, query, cache, TTL, queue, worker, retry, backoff,
idempotency, race condition, lock, transaction, rate limit, webhook, token,
middleware, deploy, latency budget, framework and library names, file paths,
class and function names.

The rule is about the **question**, not about your thinking. You still read the
code to know what is possible and what a change would cost — you just never make
the product team answer for it.

If a technical constraint genuinely limits the product, state it as a
consequence and let the product team choose: "Keeping the history for 5 years
would make the search noticeably slower for everyone. Keep 5 years, or 12
months?"

---

## Template: `.pulse/specs/features/[feature]/PRD.md`

```markdown
# [Feature Name] Specification

## Motivating Problem

[Pain in 1-2 sentences.] **Slice 1 outcome:** [observable end-to-end behavior a user can see.]

## Problem Statement

[Why now. Who it is for.]

## Goals

- [ ] [Observable outcome]
- [ ] [Observable outcome]

## Out of Scope

| Feature     | Reason         |
| ----------- | -------------- |
| [Feature X] | [Why excluded] |

## Ambiguity Ledger

| ID | Topic | Status | Resolution | Rationale |
| -- | ----- | ------ | ---------- | --------- |
| AL-01 | [gray area] | decided | [what] | [why — quote the product team's answer] |
| AL-02 | [dimension that does not apply] | n/a | — | [why it does not apply] |

Open questions: none — every row is `decided` by the product team or `n/a`.

## User Stories

### P1: [Story Title] — MVP (delivers Motivating Problem)

**User Story**: As a [role], I want [capability] so that [benefit].

**Why P1**: Slice 1 — [how this is the end-to-end outcome]

**Acceptance Criteria**:

1. WHEN [trigger] THEN the system SHALL [precise outcome]
2. IF [invalid input] THEN the system SHALL [precise error]
3. The system SHALL [invariant]

**Independent Test**: [How to demo this story alone]

## Edge Cases

- IF [error] THEN the system SHALL [handling]
- WHEN [boundary] THEN the system SHALL [behavior]

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| [FEAT]-01      | P1    | Techspec | Pending |

**ID format:** `[CATEGORY]-[NUMBER]`
**Status:** Pending → In Techspec → In Tasks → Implementing → Verified

## Spec Changes

[Append SC-NNN records here. Empty until the first change.]

## File References

Read-first index for implementers (path + why). Copy a subset into each task.

### Repo Files

- `path/to/file:start-end` — [why]

## Success Criteria

- [ ] [Measurable outcome]
```

# user-input.md

# User Input (CLI)

**Applies to:** Every phase of this skill. All reference docs defer here when user input is required.

## Rules (mandatory)

1. **No intermediate artifacts for questions** — Never create question files, screens, menus, UI components, JSON, Markdown drafts, or any other mechanism to collect answers. The terminal (chat) is the only interaction channel.
2. **Work first, ask last** — Continue executing until it is impossible to proceed without a user decision. Do as much autonomous work as allowed (codebase analysis, drafting, validation) before stopping.
3. **Batch pending questions** — When blocked, present **all** pending questions together at the **end** of the response.
4. **Stop after questions** — End the response immediately after the questions. Do not continue the workflow, create deliverables that depend on answers, or add closing commentary.
5. **Never invent mandatory answers** — Do not assume defaults or fabricate values when information is required. Infer only from explicit user input or verifiable project artifacts (code, `.pulse/specs/`, docs).
6. **Resume from interruption** — After the user replies (e.g. `A`, `B`, `1`, `Sim`, or free text), continue exactly from where execution stopped.

## Format

Use plain text suitable for a terminal. Always end with `Resposta:` on its own line.

**Delivery:** Wrap the **entire** question block in a ` ```text ` fenced code block so chat does not collapse line breaks. No markdown lists, bullets, or tables inside the block.

**English equivalent header:** `I need some information before continuing.`

### Pre-send checklist (mandatory)

Before sending, verify ALL of these. If any fails, rewrite — do not send.

| Check | Pass condition |
| ----- | -------------- |
| Numbered questions | Every question line starts with `N.` |
| Options separated | No single line contains `A)` and `B)` (or any two option letters) |
| One option per line | Count of lines matching `^[A-Z]\)` equals total options |
| Blank lines | Empty line after question text; empty line between question blocks |
| Footer | `Resposta:` alone on the last line inside the fence |
| Fence | Whole block inside ` ```text ` … ` ``` ` |

**Detection regex (mental check):** if you see ` B)` or ` C)` or ` D)` anywhere except at the start of a line (after newline), the output is **invalid**.

### Layout rules (strict — violations break readability)

Every CLI question block MUST follow this structure exactly:

1. **Header** — one line, then blank line
2. **Each question** — numbered (`1.`, `2.`, …), question text on its own line, blank line, then options
3. **Each option** — exactly one option per line, format `A) texto` (letter + `)` + space + text)
4. **Between questions** — blank line after the last option of the previous question
5. **Footer** — blank line, then `Resposta:` alone on the last line

**NEVER:**

- Put multiple options on the same line
- Omit question numbers
- Put option text on the same line as the question (without a blank line before options)
- Use markdown lists (`-`, `*`), bullets, tables, or headings inside the question block
- Wrap options in parentheses blocks on one line

**BAD (do not output like this — options collapsed on one line):**

```text
Preciso de algumas informações antes de continuar.

O que você está construindo?
A) Opção A B) Opção B C) Opção C D) Outro

Quem é o público-alvo?
A) Iniciantes B) Experts C) Outro

Resposta:
```

**GOOD (always output like this — inside ```text fence):**

```text
Preciso de algumas informações antes de continuar.

1. O que você está construindo?

A) Plataforma de paper trading
B) Sistema de gestão de portfólio
C) API de negociação
D) Plataforma completa
E) Outro (descreva)

2. Quem é o público-alvo?

A) Investidores iniciantes
B) Traders experientes
C) Ambos
D) Outro (descreva)

Resposta:
```

### Full multi-question example (project-init — use this structure)

```text
Preciso de algumas informações antes de continuar.

1. O que você está construindo?

A) Plataforma de simulação de trading (paper trading)
B) Sistema de gestão de portfólio pessoal com saldo virtual
C) Projeto full-stack de estudo/portfólio
D) Plataforma completa pronta para produção
E) Outro (descreva)

2. Quem é o público-alvo e qual problema resolve?

A) Investidores iniciantes aprendendo a operar
B) Desenvolvedores estudando arquitetura
C) Uso pessoal para simular investimentos
D) Público geral — trading sem risco
E) Outro (descreva)

3. Qual é o foco da v1 neste momento?

A) Consolidar o que existe — gaps, testes, estabilidade
B) Completar features pendentes
C) Preparar para deploy
D) Adicionar novas features (descreva)
E) Outro (descreva escopo e exclusões)

4. Há restrições críticas?

A) Sem prazo — evolução contínua local
B) Prazo curto (descreva)
C) Apenas ambiente local
D) Preparar para produção em breve
E) Outro (descreva)

Resposta:
```

Keep option text short (one line each). If an option needs a sub-prompt (e.g. "descreva"), put it in parentheses at the end of that option line — never merge options to save space.

## Question design

- Options must be **concrete** (`Card layout` not `Option A` as label text — use letters only as selectors).
- Prefer **3–6 options** plus an **Other (describe)** escape when the set is not exhaustive.
- Use **free-text questions** (no alternatives) when the answer is open-ended.
- Group related decisions into one numbered question when possible; do not split into multiple round-trips unless answers depend on each other.
- For yes/no decisions, use `A) Sim` / `B) Não` or `1) Yes` / `2) No`.
- For multi-select, state it explicitly: `(escolha uma ou mais: A, C)`.

## What is NOT a question artifact

These are **deliverables**, not question mechanisms — still create them after answers are received:

- `.pulse/specs/project/PROJECT.md`, `ROADMAP.md`, `STATE.md`
- `.pulse/specs/features/[feature]/PRD.md`, `context.md`, `TECHSPEC.md`, `tasks.md`
- `.pulse/specs/quick/NNN-slug/TASK.md`, `SUMMARY.md`
- `.pulse/specs/codebase/*` brownfield docs
- Validation reports, fix plans, task summaries

`context.md` stores **decisions already made** — never use it (or any file) as a questionnaire or pending-questions log.

## Approval and confirmation

When a phase requires user approval (design, tasks, quick-task pre-check, fix plans), create spec deliverables first when applicable (e.g. `.pulse/specs/quick/NNN-slug/TASK.md`), present the summary, then blocking questions in CLI format:

```
Preciso de algumas informações antes de continuar.

1. Aprovar [artefato] e prosseguir?

A) Sim, aprovar e continuar
B) Não, preciso de ajustes (descreva abaixo)

Resposta:
```

If the user chooses adjustments, wait for their description before revising.

## Pipeline migration (Quick mode → full spec)

When a request triggered as Quick mode but fails **Scope Eligibility** in [quick-mode.md](quick-mode.md), present:

```text
Preciso de algumas informações antes de continuar.

1. Este pedido excede o escopo do Quick mode: [motivo concreto — ex.: 5 arquivos, decisão de arquitetura, escopo vago]. Como deseja prosseguir?

A) Migrar para o pipeline completo (PRD → Techspec → Tasks → Execute, conforme escopo)
B) Quick fix: [recorte pré-definido 1 — uma linha, ≤3 arquivos]
C) Quick fix: [recorte pré-definido 2 — uma linha, ≤3 arquivos]
D) Cancelar

Resposta:
```

- **A)** Start [prd.md](prd.md) for the feature — do not keep a quick TASK.md
- **B/C…)** Re-assess eligibility with that predefined narrowed scope; if it passes, continue Quick mode
- **Last option (Cancelar)** Stop; no spec files unless the user reopens the request

**Closed choices only:** Do not use "descreva" or free-text options in this block. Do not include "Outro" — Pulse suppresses it for migration gates. List concrete quick-fix alternatives derived from your codebase analysis.

**Never** auto-start PRD, Techspec, or Tasks without the user selecting **A**.

## UAT and verification

Interactive UAT follows the same strict layout — one option per line, numbered question, blank lines between sections:

```
Preciso de algumas informações antes de continuar.

1. Teste: [Nome do teste]

Esperado: [comportamento observável]

A) Funciona como esperado
B) Não funciona (descreva o que vê)
C) Pular / não aplicável

Resposta:
```

Infer severity from free-text descriptions per [validate.md](validate.md). Never ask the user to rate severity.
