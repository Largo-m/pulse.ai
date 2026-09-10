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

**Never auto-migrate.** Never start Specify/Design/Tasks without explicit user confirmation.

If the user chooses **reduce scope**, re-run eligibility with the narrowed request. Only create quick spec files when the reduced scope passes all checks.

If the user chooses **full pipeline**, begin at [specify.md](specify.md) → `.pulse/specs/features/[feature]/spec.md` (auto-size Design and Tasks per SKILL.md).

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
