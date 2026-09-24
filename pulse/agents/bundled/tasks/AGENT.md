---
name: tasks
description: Escreve tasks.md
runtime: cursor
model: Auto
permission_policy: deny_writes
---

# tasks.md

# Tasks

**Goal**: Break into GRANULAR, ATOMIC tasks. Clear dependencies. Right tools. Parallel execution plan.

**Skip this phase when:** There are ≤3 obvious steps. In that case, tasks are implicit — go straight to Execute and list them inline in your implementation plan.

## Why Granular Tasks?

| Vague Task (BAD) | Granular Tasks (GOOD)             |
| ---------------- | --------------------------------- |
| "Create form"    | T1: Create email input component  |
|                  | T2: Add email validation function |
|                  | T3: Create submit button          |
|                  | T4: Add form state management     |
|                  | T5: Connect form to API           |
| "Implement auth" | T1: Create login form             |
|                  | T2: Create register form          |
|                  | T3: Add token storage utility     |
|                  | T4: Create auth API service       |
|                  | T5: Add route protection          |

**Benefits of granular:**

- **Agents don't err** - Single focus, no ambiguity
- **Easy to test** - Each task = one verifiable outcome
- **Parallelizable** - Independent tasks run simultaneously
- **Errors isolated** - One failure doesn't block everything

**Unit of work:** a task is one **shippable outcome** with a verify path. File count does not decide the cut.

**Substeps** (inline under the task) are allowed when a single outcome still needs more than one file. Split into another task only when:

- A different test ID owner appears
- A different actor/surface appears
- Context would blow the worker budget

Do **not** split "one function / one file" as a law — that explodes ceremony. Do **not** hide an unverified mountain in one task.

Slice 1 is the task (or consecutive tasks) that delivers the spec's Motivating Problem.

---

## Process

### 1. Review Design

Read `.pulse/specs/[feature]/design.md` before creating tasks.

### 1.5. Load Test Coverage Matrix

Read `.pulse/specs/codebase/TESTING.md` (if it exists) before creating tasks. The Test Coverage Matrix
and Parallelism Assessment drive two critical decisions:

**Co-located tests:** Every task that creates or modifies a code layer with a required test type
MUST include writing/updating those tests in the same task. Tests are NOT separate tasks.

| Task creates...                           | Done When must include...                   |
| ----------------------------------------- | ------------------------------------------- |
| Code layer with "unit" requirement        | Unit test written + quick gate passes       |
| Code layer with "e2e" requirement         | E2E test written + full gate passes         |
| Code layer with "integration" requirement | Integration test written + full gate passes |
| Code layer with "none" requirement        | Gate check at appropriate level             |

**Parallelism flags:** Cross-reference the Parallelism Assessment when marking tasks `[P]`:

- If a task's required test type is marked "Parallel-Safe: No" → strip `[P]` flag
- If a task's required test type is marked "Parallel-Safe: Yes" → `[P]` is allowed
- If a task has no tests → `[P]` depends only on code dependencies

Co-locate tests with the code task. Tests are not a separate task. Assign every live `tests.md` ID to exactly one task.

If TESTING.md does not exist (greenfield project), ask the user what test types and commands
the project will use before creating tasks. Infer commands from the repo when they exist — do not invent ecosystems.

### 2. Break Into Atomic Tasks

**Task = ONE verifiable outcome**. Examples:

- ✅ "User can log in with email and get a session cookie" (demo-able; may touch a few files)
- ✅ "Create UserService interface" when that *is* the outcome (foundation named with its consumer)
- ❌ "Implement user management" (multiple outcomes, no single verify path)

### 3. Define Dependencies

What MUST be done before this task can start?

### 4. Create Execution Plan

Group tasks into phases. Identify what can run in parallel.

### 5. Validate Before Presenting (MANDATORY)

Before showing tasks to the user, run ALL three pre-approval checks. These are NOT optional — they are gates. If any check fails, restructure the tasks and re-run until all pass.

**Check 1: Task Granularity** — verify each task is atomic (see Granularity Check section).

**Check 2: Diagram-Definition Cross-Check** — verify the execution diagram **and** the Task Graph YAML match every task's `Depends on` field.

**Check 3: Test Co-location Validation** — verify every task's `Tests` field matches the TESTING.md coverage matrix (see Test Co-location Validation section). Build the validation table and include it in the output.

**Output both tables with the tasks** so the user can see the validation results. Any ❌ means you MUST restructure before presenting — do not show failing tasks to the user and ask them to approve.

### 6. Tools

Assign MCPs/skills yourself from the repo and the task's File References. Ask the user only when two tools would produce different public behavior. Do not run a per-task tools questionnaire.

### 7. Closure gate

Run `python3 <skill-dir>/scripts/validate_tasks.py <feature>` before presenting tasks ([gates.md](gates.md)). Non-zero exit → restructure, do not ask the user to approve a failing graph.

---

## Template: `.pulse/specs/[feature]/tasks.md`

```markdown
# [Feature] Tasks

**Design**: `.pulse/specs/[feature]/design.md`
**Status**: Draft | Approved | In Progress | Done

---

## Task Graph

Parseable dependency data. `from` must finish before `to`. Must match every task's `Depends on`.

```yaml
nodes:
  - id: T1
  - id: T2
  - id: T3
edges:
  - { from: T1, to: T2 }
  - { from: T1, to: T3 }
```

## Test Coverage Matrix

[From TESTING.md / repo sampling — see tests-catalog.md]

## Gate Check Commands

[From the repo]

## Execution Plan

### Phase 1: Foundation (Sequential)

Tasks that must be done first, in order.
```

T1 → T2 → T3

```

### Phase 2: Core Implementation (Parallel OK)
After foundation, these can run in parallel.

```

     ┌→ T4 ─┐

T3 ──┼→ T5 ─┼──→ T8
└→ T6 ─┘
T7 ──────→

```

### Phase 3: Integration (Sequential)
Bringing it all together.

```

T8 → T9

---

## Task Breakdown

### T1: [Create X Interface]

**What**: [One sentence: exact deliverable]
**Where**: `src/path/to/file.ts`
**Depends on**: None
**Reuses**: `src/existing/BaseInterface.ts`
**Requirement**: [FEAT]-01
**Slice**: 1 (Motivating Problem) | later

**File References**:

- `path/to/file:start-end` — [why]

**Done when**:

- [ ] Interface defined with all methods from design
- [ ] Types exported correctly
- [ ] No TypeScript errors

**Tests**: UT-001, UT-002
**Gate**: [quick/full/build — from gate check commands]

---

### T2: [Implement Y Service] [P]

**What**: [Exact deliverable]
**Where**: `src/services/YService.ts`
**Depends on**: T1
**Reuses**: `src/services/BaseService.ts` patterns

**Tools**:

- MCP: `filesystem`, `context7`
- Skill: NONE

**Done when**:

- [ ] Implements interface from T1
- [ ] Handles error cases from design
- [ ] Gate check passes: `[quick gate command from TESTING.md]`
- [ ] Test count: [N] tests pass (no silent deletions)

**Tests**: unit
**Gate**: quick

---

### T3: [Create Z Component] [P]

**What**: [Exact deliverable]
**Where**: `src/components/ZComponent.tsx`
**Depends on**: T1
**Reuses**: `src/components/BaseComponent.tsx`

**Tools**:

- MCP: `filesystem`
- Skill: NONE

**Done when**:

- [ ] Component renders correctly
- [ ] Handles props from interface
- [ ] Follows existing component patterns
- [ ] Gate check passes: `[quick gate command from TESTING.md]`
- [ ] Test count: [N] tests pass (no silent deletions)

**Tests**: unit
**Gate**: quick

---

### T4: [Add A Feature to Y]

**What**: [Exact deliverable]
**Where**: `src/services/YService.ts` (modify)
**Depends on**: T2, T3
**Reuses**: Existing service patterns

**Tools**:

- MCP: `filesystem`, `github`
- Skill: `api-design`

**Done when**:

- [ ] Feature works per acceptance criteria
- [ ] Gate check passes: `[full gate command from TESTING.md]`
- [ ] Test count: [N] tests pass (no silent deletions)

**Tests**: integration
**Gate**: full

---

## Parallel Execution Map

Visual representation of what can run simultaneously:

```

Phase 1 (Sequential):
  T1 ──→ T2 ──→ T3

Phase 2 (Parallel):
  T3 complete, then:
    ├── T4 [P]
    ├── T5 [P]  } Can run simultaneously
    └── T6 [P]

Phase 3 (Sequential):
  T4, T5, T6 complete, then:
    T7 ──→ T8

```

**Parallelism constraint:** A task marked `[P]` must have ALL of these:

- No unfinished dependencies
- Required test type is parallel-safe (per TESTING.md Parallelism Assessment)
- No shared mutable state with other `[P]` tasks in the same phase

If a task's tests are NOT parallel-safe, it MUST run sequentially even if its
implementation code has no dependencies. The test execution is the bottleneck.

**How parallel execution works:**

Tasks marked `[P]` are executed via sub-agents — one sub-agent per task, launched concurrently.
Each sub-agent receives only its task definition and relevant project context (see Sub-Agent
Delegation in SKILL.md). The orchestrating agent waits for all sub-agents in a phase to complete
before advancing to the next phase.

Sequential tasks (no `[P]`) are also delegated to sub-agents, but one at a time. This keeps
implementation artifacts (file reads, test output, gate check logs) out of the main context.

**The orchestrating agent's role during Execute:**
1. Pick the next task(s) to execute
2. Provide each sub-agent with its task definition + context
3. Monitor sub-agent completion
4. Update tasks.md with results
5. Decide whether to proceed, fix, or escalate

---

## Task Granularity Check

Before approving tasks, verify they are granular enough:

| Task                            | Scope         | Status       |
| ------------------------------- | ------------- | ------------ |
| T1: Create email input          | 1 component   | ✅ Granular  |
| T2: Add validation function     | 1 function    | ✅ Granular  |
| T3: Create form with all fields | 5+ components | ❌ Split it! |
| T4: Connect to API              | 1 function    | ✅ Granular  |

**Granularity check**:

- ✅ One verifiable outcome; files listed; tests assigned
- ⚠️ Several files OK if one outcome and one test owner
- ❌ Multiple unrelated outcomes or unassigned test IDs = split

---

## Diagram-Definition Cross-Check

Before approving tasks, verify the execution diagram is consistent with the task definitions. These are independent artifacts that can drift — the diagram is drawn for visual clarity while task bodies are written for precision. Both must agree.

For each task, check:

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T[N] | [deps from body] | [deps from diagram arrows] | ✅ Match or ❌ Mismatch |

**Rules:**

- Every `Depends on` in a task body must have a corresponding arrow in the diagram.
- Every arrow in the diagram must correspond to a `Depends on` in the target task's body.
- Tasks shown as parallel (`[P]`) in the diagram must not depend on each other.
- If a task depends on another task in the same parallel phase, they are NOT parallel — fix the diagram or remove the `[P]` flag.

---

## Test Co-location Validation

Before approving tasks, verify EVERY task's `Tests` field is consistent with the TESTING.md Test Coverage Matrix. This is a hard gate — tasks that fail this check MUST be fixed.

For each task, check: does the task create or modify a code layer that has a required test type in the coverage matrix? If yes, the task's `Tests` field MUST match.

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T[N]: [name] | [layer from coverage matrix] | [test type] | [task's Tests field] | ✅ OK or ❌ VIOLATION |

**Rules:**

- "Tested in another task" is NOT a valid justification for `Tests: none`. That is test deferral — the exact anti-pattern this validation prevents.
- `Tests: none` is only valid when the coverage matrix says "none" for that code layer.
- If a task creates MULTIPLE code layers (e.g., service + controller), use the HIGHEST test type required by any of them.
- Any ❌ VIOLATION → restructure the task to include its required tests before proceeding.

**Resolving compilation dependencies:**

When a task creates code that can't be tested until a later task completes (e.g., a controller that needs module wiring before its e2e tests can run), do NOT defer the tests to a separate task. Instead, restructure:

1. **Merge forward:** Move the untestable task's tests into the earliest task where they become runnable (e.g., the wiring task includes wiring + e2e tests for the controller it enables).
2. **Merge backward:** Absorb the blocking dependency into the current task so it becomes self-testable (e.g., controller task includes its own module registration).

Pick whichever option keeps tasks atomic and cohesive. The goal: no task produces unverified code. If code can't be tested in the task that creates it, the task boundaries are wrong.

---

## Tips

- **[P] = Parallel OK** — Mark tasks that can run simultaneously
- **Reuses = Token saver** — Always reference existing code
- **Tools per task** — MCPs and Skills prevent wrong approaches
- **Dependencies are gates** — Clear what blocks what
- **Done when = Testable** — If you can't verify it, rewrite it
- **Requirement ID = Traceable** — Every task traces back to a spec requirement

---

## Task Verification Standards

Every task MUST include:

**Done when checklist:**

- Specific, testable outcomes
- Pass/fail criteria
- The specific test command from the Gate Check Commands table
- Expected pass count (prevents silent test deletion)

**Verify section:**

- Commands to prove functionality
- Expected outputs
- Success indicators

**Structure:**

```markdown
### T1: [Task name]

**What:** [Deliverable]
**Where:** [File path]
**Tests**: [unit/e2e/integration/none]
**Gate**: [quick/full/build]

**Done when:**

- [ ] [Specific outcome]
- [ ] [Specific outcome]
- [ ] Gate check passes: `[command from Gate Check Commands]`
- [ ] Test count: [N] tests pass (no silent deletions)

**Verify:**
[Command to prove it works]
[Expected output/behavior]
```

**Quality check:**

- Can task be verified without human judgment?
- Is success criteria binary (pass/fail)?
- Can verification be automated?

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
- `.pulse/specs/features/[feature]/spec.md`, `context.md`, `design.md`, `tasks.md`
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

A) Migrar para o pipeline completo (Specify → Design → Tasks → Execute, conforme escopo)
B) Quick fix: [recorte pré-definido 1 — uma linha, ≤3 arquivos]
C) Quick fix: [recorte pré-definido 2 — uma linha, ≤3 arquivos]
D) Cancelar

Resposta:
```

- **A)** Start [specify.md](specify.md) for the feature — do not keep a quick TASK.md
- **B/C…)** Re-assess eligibility with that predefined narrowed scope; if it passes, continue Quick mode
- **Last option (Cancelar)** Stop; no spec files unless the user reopens the request

**Closed choices only:** Do not use "descreva" or free-text options in this block. Do not include "Outro" — Pulse suppresses it for migration gates. List concrete quick-fix alternatives derived from your codebase analysis.

**Never** auto-start Specify, Design, or Tasks without the user selecting **A**.

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
