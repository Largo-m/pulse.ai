---
name: quick-plan
description: Plano do quick mode
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

# state-management.md

# State Management

**Purpose:** Persistent memory across sessions - decisions, blockers, learnings.

## Structure

**Output:** `.pulse/specs/project/STATE.md`

```markdown
# State

**Last Updated:** [ISO timestamp]
**Current Work:** [Feature name] - [Task identifier]

---

## Recent Decisions (Last 60 days)

### AD-[NNN]: [Decision title] ([date])

**Decision:** [What was decided]
**Reason:** [Why this choice]
**Trade-off:** [What was sacrificed]
**Impact:** [How this affects implementation]

### AD-[NNN]: [Decision title] ([date])

[Same structure]

---

## Active Blockers

### B-[NNN]: [Blocker description]

**Discovered:** [Date]
**Impact:** [Severity and scope]
**Workaround:** [Temporary solution if available]
**Resolution:** [Path to permanent fix]

---

## Lessons Learned

### L-[NNN]: [Learning description]

**Signal:** ac_gap | surviving_mutant | spec_precision_gap | spec_deviation | gate_fail | review_valid
**Source:** [file:line or AC id]
**Feature:** [slug]
**Status:** candidate | confirmed | quarantined
**Context:** [Situation that occurred]
**Problem:** [What went wrong]
**Solution:** [How it was resolved]
**Prevents:** [What this knowledge prevents in future]

---

## Quick Tasks

| #   | Description              | Date   | Spec                         | Status                |
| --- | ------------------------ | ------ | ---------------------------- | --------------------- |
| 001 | [Quick task description] | [date] | `.pulse/specs/quick/001-slug/`     | ⏳ Awaiting Approval  |
| 002 | [Quick task description] | [date] | `.pulse/specs/quick/002-slug/`     | ✅ Done               |

---

## Deferred Ideas

Ideas captured during work that belong in future features or phases. Prevents scope creep while preserving good ideas.

- [ ] [Idea description] — Captured during: [feature/phase]
- [ ] [Idea description] — Captured during: [feature/phase]

---

## Todos

Capture in-progress thoughts and action items that don't fit in active tasks.

- [ ] [TODO: action item]
- [ ] [TODO: action item]
```

## When to Update

| Event                            | Action                                 |
| -------------------------------- | -------------------------------------- |
| Significant architectural choice | Add AD-[NNN]                           |
| Implementation blocked           | Add B-[NNN]                            |
| Important discovery/learning     | Add L-[NNN] with **Signal** + **Source** ([lessons.md](lessons.md)) |
| Quick task started (plan ready)  | Create `.pulse/specs/quick/NNN-slug/TASK.md`, update Current Work, add Quick Tasks row ⏳ |
| Quick task completed             | Update TASK.md, create SUMMARY.md, set Quick Tasks row ✅ Done          |
| Scope creep captured             | Add to Deferred Ideas                  |
| In-progress thought              | Add to Todos                           |
| Session end                      | Update "Last Updated" + "Current Work" |

## Size Management (Hybrid Strategy)

**Zones:**

- 🟢 <7k tokens: No action
- 🟡 7-10k tokens: Footer note "STATE.md at [X]k. Cleanup recommended."
- 🔴 >10k tokens: Active prompt "STATE.md critical ([X]k). Cleanup now?"

**Cleanup process:**

- Move decisions >60 days to STATE-ARCHIVE.md
- Keep only active blockers
- Preserve recent learnings (<60 days)

**Validation:**

- Decisions have clear rationale?
- Blockers include resolution path?
- Learnings are actionable?

---

## Preferences

Track user-facing behavioral state in STATE.md:

```markdown
## Preferences

**Model Guidance Shown:** [ISO date or "never"]
```

**Update when:**

| Event                       | Action                   |
| --------------------------- | ------------------------ |
| First model tip given       | Set date                 |
| User acknowledges/dismisses | Keep date (don't repeat) |

This prevents repetitive suggestions while maintaining natural, helpful behavior.

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
