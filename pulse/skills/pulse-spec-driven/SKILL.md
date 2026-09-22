---
name: pulse-spec-driven
description: Project and feature planning with 4 adaptive phases - Specify, Design, Tasks, Execute. Auto-sizes depth by complexity. EARS requirements, ambiguity ledger, spec-change protocol, independent Verifier (author != verifier), evidence-or-zero, discrimination sensor, review rounds, grounded lessons, and deterministic Python gates. Does not commit or suggest commit messages — the user controls git. Quick mode checks scope eligibility first; if out of scope, asks whether to migrate to full pipeline before creating quick spec files. Requires explicit approval before implementing quick tasks. CLI user-input protocol for all blocking questions. Use when (1) Starting new projects (initialize vision, goals, roadmap), (2) Working with existing codebases (map stack, architecture, conventions), (3) Planning features (requirements, design, task breakdown), (4) Implementing with verification, (5) Quick ad-hoc tasks (bug fixes, config changes), (6) Tracking decisions/blockers/deferred ideas across sessions, (7) Pausing/resuming work. Triggers on "initialize project", "map codebase", "specify feature", "discuss feature", "design", "tasks", "implement", "validate", "verify work", "UAT", "quick fix", "quick task", "pause work", "resume work". Do NOT use for architecture decomposition analysis (use architecture skills) or technical design docs (use create-technical-design-doc).
license: CC-BY-4.0
metadata:
  author: Pulse
  version: 2.1.0
---

# Pulse Spec-Driven Development

Plan and implement projects with precision. Granular tasks. Clear dependencies. Right tools. Zero ceremony.

Read [invariants.md](references/invariants.md) before acting: spec-first, contract precedence, three-layer Definition of Done, blast radius, no fabrication.

```
┌──────────┐   ┌──────────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐
│ SPECIFY  │ → │  DESIGN  │ → │  TASKS  │ → │ EXECUTE │ → │ VERIFY / │
└──────────┘   └──────────┘   └─────────┘   └─────────┘   │ REVIEW*  │
   required      optional*      optional*     required     └──────────┘

* Agent auto-skips when scope doesn't need it. Verifier always runs after the last task (Medium+).
```

## Auto-Sizing: The Core Principle

**The complexity determines the depth, not a fixed pipeline.** Before starting any feature, assess its scope and apply only what's needed:

| Scope       | What                     | Specify                                                 | Design                                          | Tasks                         | Execute                                               |
| ----------- | ------------------------ | ------------------------------------------------------- | ----------------------------------------------- | ----------------------------- | ----------------------------------------------------- |
| **Small**   | ≤3 files, one sentence   | **Quick mode** — skip pipeline entirely                 | -                                               | -                             | -                                                     |
| **Medium**  | Clear feature, <10 tasks | Spec (brief)                                            | Skip — design inline                            | Skip — tasks implicit         | Implement + verify                                    |
| **Large**   | Multi-component feature  | Full spec + requirement IDs                             | Architecture + components                       | Full breakdown + dependencies | Implement + verify per task                           |
| **Complex** | Ambiguity, new domain    | Full spec + [discuss gray areas](references/discuss.md) | [Research](references/design.md) + architecture | Breakdown + parallel plan     | Implement + [interactive UAT](references/validate.md) |

**Rules:**

- **Specify and Execute are always required** — you always need to know WHAT and DO it
- **Design is skipped** when the change is straightforward (no architectural decisions, no new patterns)
- **Tasks is skipped** when there are ≤3 obvious steps (they become implicit in Execute)
- **Discuss is triggered within Specify** only when the agent detects ambiguous gray areas that need user input
- **Interactive UAT is triggered within Execute** only for user-facing features with complex behavior
- **Quick mode** is the express lane — for bug fixes, config changes, and small tweaks
- **Threat model** is written only when a trigger fires (auth, payments, PII, trust boundaries) — see [threat-model.md](references/threat-model.md)
- **Public surface** (`surface.md`) is written only when users or agents type/see a CLI, API, SDK, or UI
- **Verifier** always runs after the last Medium+ task (author ≠ verifier). Review follows when the artifact matrix requires it

**Safety valve:** Even when Tasks is skipped, Execute ALWAYS starts by listing atomic steps inline (see [implement.md](references/implement.md)). If that listing reveals >5 steps or complex dependencies, STOP and create a formal `tasks.md` — the Tasks phase was wrongly skipped.

## Project Structure

```
.pulse/specs/
├── project/
│   ├── PROJECT.md      # Vision & goals
│   ├── ROADMAP.md      # Features & milestones
│   ├── STATE.md        # Memory: decisions, blockers, lessons, todos, deferred ideas
│   └── METRICS.md      # SDD signals (created on first feature completion)
├── codebase/           # Brownfield analysis (existing projects)
│   ├── STACK.md
│   ├── ARCHITECTURE.md
│   ├── CONVENTIONS.md
│   ├── STRUCTURE.md
│   ├── TESTING.md
│   ├── INTEGRATIONS.md
│   └── CONCERNS.md
├── features/           # Feature specifications
│   └── [feature]/
│       ├── spec.md         # Requirements, EARS ACs, ledger, traceability
│       ├── context.md      # User decisions for gray areas (only when discuss is triggered)
│       ├── surface.md      # Public CLI/API/UI contract (only if public surface)
│       ├── tests.md        # Test catalog with stable IDs (Large/Complex)
│       ├── design.md       # Architecture & components (only for Large/Complex)
│       ├── threat-model.md # Only when a security trigger fires
│       ├── tasks.md        # Outcomes + parseable graph (only for Large/Complex)
│       ├── validation.md   # Verifier report (Feature Done)
│       └── reviews-NNN/    # Code review issues (Merge layer, when required)
└── quick/              # Ad-hoc tasks (quick mode)
    └── NNN-slug/
        ├── TASK.md
        └── SUMMARY.md
```

## Workflow

**New project:**

1. Initialize project → PROJECT.md + ROADMAP.md
2. For each feature → Specify → (Design) → (Tasks) → Execute → Verifier → (Review)

**Existing codebase:**

1. Map codebase → 7 brownfield docs
2. Initialize project → PROJECT.md + ROADMAP.md
3. For each feature → same adaptive workflow

**Quick mode:** Describe → Plan → **Spec files** → **Approve** → Implement → Verify → Track

## Quick Mode Approval

**Never implement a quick task automatically.** The user must approve the plan first.

**Scope gate:** If the request does not fit Quick mode (see [quick-mode.md](references/quick-mode.md) **Scope Eligibility**), **ask** whether to migrate to the full pipeline — do not create quick spec files or implement until the user chooses.

1. Check scope eligibility (research and read files is OK)
2. If out of scope → explain why → **Pipeline migration** CLI question → stop
3. If in scope → **create spec files before responding:** `.pulse/specs/quick/NNN-slug/TASK.md` + update `STATE.md`
4. Present pre-implementation check in chat (reference the TASK.md path) and **stop**
5. Collect approval via [user-input.md](references/user-input.md) CLI format — wait for explicit confirmation before any **application code** changes
6. Only then: Implement → Verify → Track (SUMMARY.md)

Creating `.pulse/specs/` quick files is required and allowed before approval when eligible. Editing application source is not. Full pipeline starts only after explicit user confirmation.

See [quick-mode.md](references/quick-mode.md) for the full process and approval anti-patterns.

## Git Policy

**The user controls git.** The agent does not commit and does not suggest commit messages.

- Do not run `git commit`, `git add` + `git commit`, or equivalent unless the user explicitly asks
- Do not suggest commit messages, Conventional Commits formats, or "ready to commit" prompts after tasks
- After verification, mark the task done and update tracking docs — leave git entirely to the user
- Session handoff may note uncommitted files; that is informational only
- Approving a spec authorizes **local** edits only. Push, deploy, and production DB changes need an explicit go-ahead

## Deterministic Gates

Scripts live under this skill's `scripts/` directory. Resolve `<skill-dir>` from this `SKILL.md`. See [gates.md](references/gates.md).

- Before confirming a spec: `python3 <skill-dir>/scripts/validate_spec.py <feature>`
- Before presenting tasks: `python3 <skill-dir>/scripts/validate_tasks.py <feature>`
- Before Feature Done: `python3 <skill-dir>/scripts/validate_validation.py <feature>`
- After Feature Done / spec change: `python3 <skill-dir>/scripts/validate_metrics.py <feature>`

Non-zero exit = STOP. Skip only when no code-execution tool exists; then read the artifact and apply the same checks.

## User Input (CLI)

Whenever this skill needs information from the user, follow [user-input.md](references/user-input.md). **No exceptions.**

### Pre-send checklist (run before every response that asks questions)

If ANY check fails, rewrite the block — do not send.

- [ ] Every question starts with `1.`, `2.`, `3.` … on its own line
- [ ] Blank line between question text and first option
- [ ] Each option is alone on one line: `A) …`, then newline, then `B) …`, etc.
- [ ] **No line contains both `A)` and `B)`** (or any two option letters)
- [ ] Blank line between question blocks
- [ ] Last line is exactly `Resposta:`
- [ ] Entire block wrapped in a ` ```text ` code fence (preserves line breaks in chat)

### Canonical template (copy structure — replace placeholders only)

````text
Preciso de algumas informações antes de continuar.

1. O que você está construindo?

A) Plataforma de simulação de trading (paper trading)
B) Sistema de gestão de portfólio pessoal com saldo virtual
C) Projeto full-stack de estudo/portfólio
D) Plataforma completa pronta para produção
E) Outro (descreva)

2. Quem é o público-alvo e qual problema resolve?

A) Investidores iniciantes
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
````

**Hard rule:** One option = one line. Never concatenate `A) … B) … C) …` on a single line.

### Protocol summary

- Never create question files, UI, menus, or intermediate artifacts to collect answers
- Work until blocked, then present all pending questions at the **end** in the template above
- End the response immediately after the closing ` ``` ` of the question block — wait for terminal input
- Never invent or assume mandatory answers
- Resume from the exact interruption point after the user replies

All phase references (project-init, specify, discuss, tasks, validate, quick-mode, etc.) defer to this protocol.

## Context Loading Strategy

**Base load (~15k tokens):**

- PROJECT.md (if exists)
- ROADMAP.md (when planning/working on features)
- STATE.md (persistent memory)

**On-demand load:**

- Codebase docs (when working in existing project)
- CONCERNS.md (when planning features that touch flagged areas, estimating risk, or modifying fragile components)
- TESTING.md (when creating tasks or executing — drives test type assignment and gate checks)
- spec.md (when working on specific feature)
- context.md (when designing or implementing from user decisions)
- surface.md / tests.md / threat-model.md (when those files exist)
- design.md (when implementing from design)
- tasks.md (when executing tasks)
- validation.md (when resuming after Execute)
- confirmed lessons in STATE.md (Specify and Design)

**Never load simultaneously:**

- Multiple feature specs
- Multiple architecture docs
- Archived documents

**Target:** <40k tokens total context
**Reserve:** 160k+ tokens for work, reasoning, outputs
**Monitoring:** Display status when >40k (see [context-limits.md](references/context-limits.md))

## Sub-Agent Delegation

Use sub-agents (the Task tool or equivalent) to keep the main context window lean and enable
parallel execution. The orchestrating agent plans and coordinates; sub-agents do the heavy lifting.

**When to delegate to a sub-agent:**

| Activity | Delegate? | Why |
|---|---|---|
| Research (design phase, brownfield mapping) | Yes | Research output is large; only the summary matters to the main context |
| Implementing a task | Yes | File reads, edits, test output consume context; only the result matters |
| Parallel `[P]` tasks | Yes (one per task) | The only way to actually run tasks in parallel |
| Sequential tasks with no `[P]` | Yes | Keeps implementation artifacts out of the main context |
| Planning, task creation | No | These require the full accumulated context to be coherent |
| Feature-level Verifier | Yes — **fresh** agent | Author ≠ verifier; do not reuse the implementer's session |
| Review round | Yes — **fresh** agent | Separate from implementer and Verifier |
| Quick mode tasks | No | Too small to justify the overhead; **never auto-implement** — create spec files, present plan, wait for user approval via CLI |

**Context each sub-agent receives:**

The orchestrating agent MUST provide each sub-agent with:
- The specific task definition from tasks.md (What, Where, Depends on, Reuses, Done when, Tests, Gate)
- Relevant coding principles and conventions (coding-principles.md, CONVENTIONS.md)
- TESTING.md, if it exists (for gate check commands and test patterns)
- Any spec/design context the task references

The sub-agent does NOT receive: other tasks' definitions, accumulated chat history, validation reports
from other tasks, or STATE.md (unless the task explicitly references a decision/blocker).

**What sub-agents return:**

Each sub-agent reports back:
- Status: Complete | Blocked | Partial
- Files changed: [list]
- Gate check result: [pass/fail + test counts]
- SPEC_DEVIATION markers (if any)
- Issues encountered (if any)

The orchestrating agent uses this to update tasks.md status, traceability, and decide next steps.

## Commands

**User input (all phases):** Follow [user-input.md](references/user-input.md) whenever information from the user is required.

**Project-level:**
| Trigger Pattern | Reference |
|----------------|-----------|
| Initialize project, setup project | [project-init.md](references/project-init.md) |
| Create roadmap, plan features | [roadmap.md](references/roadmap.md) |
| Map codebase, analyze existing code | [brownfield-mapping.md](references/brownfield-mapping.md) |
| Document concerns, find tech debt, what's risky | [concerns.md](references/concerns.md) |
| Record decision, log blocker, add todo | [state-management.md](references/state-management.md) |
| Pause work, end session | [session-handoff.md](references/session-handoff.md) |
| Resume work, continue | [session-handoff.md](references/session-handoff.md) |

**Feature-level (auto-sized):**
| Trigger Pattern | Reference |
|----------------|-----------|
| Specify feature, define requirements | [specify.md](references/specify.md) |
| Discuss feature, capture context, how should this work | [discuss.md](references/discuss.md) |
| Change the spec, invalidate tasks | [spec-change.md](references/spec-change.md) |
| Design feature, architecture | [design.md](references/design.md) |
| Break into tasks, create tasks | [tasks.md](references/tasks.md) |
| Implement task, build, execute | [implement.md](references/implement.md) |
| Validate, verify, test, UAT, walk me through it | [validate.md](references/validate.md) |
| Review code, review round | [review.md](references/review.md) |
| Quick fix, quick task, small change, bug fix | [quick-mode.md](references/quick-mode.md) |

**Always-on contracts:** [invariants.md](references/invariants.md) · [ambiguity.md](references/ambiguity.md) · [gates.md](references/gates.md) · [lessons.md](references/lessons.md) · [metrics.md](references/metrics.md) · [architecture.md](references/architecture.md)

## Skill Integrations

This skill coexists with other skills. Before specific tasks, check if complementary skills are installed and prefer them when available.

### Diagrams → mermaid-studio

Whenever the workflow requires creating or updating a diagram (architecture overviews, data flows, component diagrams, sequence diagrams, etc.), **always** check if the `mermaid-studio` skill is installed in the user's environment before proceeding. If it is installed, delegate all diagram creation and rendering to it. If it is not installed, proceed with inline mermaid code blocks as usual and recommend the user install `mermaid-studio` for richer diagram capabilities (rendering to SVG/PNG, validation, theming, etc.). Display this recommendation at most once per session.

### Code Exploration → codenavi

Whenever the workflow requires exploring or discovering things in an existing repository (brownfield mapping, code reuse analysis, pattern identification, dependency tracing, etc.), **always** check if the `codenavi` skill is installed in the user's environment before proceeding. If it is installed, delegate code exploration and navigation tasks to it. If it is not installed, fall back to the built-in code analysis tools (see [code-analysis.md](references/code-analysis.md)) and recommend the user install `codenavi` for more effective codebase exploration. Display this recommendation at most once per session.

## Knowledge Verification Chain

When researching, designing, or making any technical decision, follow this chain in strict order. Never skip steps.

```
Step 1: Codebase → check existing code, conventions, and patterns already in use
Step 2: Project docs → README, docs/, inline comments, .pulse/specs/codebase/
Step 3: Context7 MCP → resolve library ID, then query for current API/patterns
Step 4: Web search → official docs, reputable sources, community patterns
Step 5: Flag as uncertain → "I'm not certain about X — here's my reasoning, but verify"
```

**Rules:**

- Never skip to Step 5 if Steps 1-4 are available
- Step 5 is ALWAYS flagged as uncertain — never presented as fact
- **NEVER assume or fabricate.** If you cannot find an answer, say "I don't know" or "I couldn't find documentation for this". Inventing APIs, patterns, or behaviors causes cascading failures across design → tasks → implementation. Uncertainty is always preferable to fabrication.

## Output Behavior

**Model guidance:** After completing lightweight tasks (validation, state updates, session handoff), naturally mention once that such tasks work well with faster/cheaper models. Track in STATE.md under `Preferences` to avoid repeating. For heavy tasks (brownfield mapping, complex design), briefly note the reasoning requirements before starting.

Be conversational in completed work summaries, not when collecting input — pending questions always use the CLI format from [user-input.md](references/user-input.md). Don't interrupt workflow with model tips when blocked on user input. Skip model guidance if user seems experienced or has already acknowledged the tip.

## Code Analysis

Use available tools with graceful degradation. See [code-analysis.md](references/code-analysis.md).
