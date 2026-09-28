# Invariants

Always-on rules. Auto-sizing changes which artifacts exist; it does not waive these.

## Core

1. Spec-first: know WHAT before writing application code (Quick mode uses `TASK.md` as the spec).
2. Do not fabricate contracts, APIs, or behavior. Follow the Knowledge Verification Chain. Uncertainty beats invention.
3. Facts come from code and artifacts; decisions come from the user. Never ask what the code already answers.
4. One unit of work at a time. No drive-by changes. Capture extras as Deferred Ideas.
5. Done requires evidence, not narrative. Status in a markdown file is not proof.
6. Blast radius: approving a spec or task authorizes local edits only. Push, deploy, production DB, and other remote/destructive actions need an explicit go-ahead.
7. Git belongs to the user. Do not commit or suggest commit messages unless asked.
8. Do not silently rewrite a spec to fit an implementation.

## Contract precedence

When sources disagree, resolve in this order. Record the resolution in the Ambiguity Ledger or an AD-NNN.

1. Current explicit user decision (this session, written to ledger / STATE)
2. Approved `PRD.md` (and `surface.md` / `tests.md` when they exist)
3. Approved `context.md` decisions
4. Active AD-NNN in STATE.md
5. `TECHSPEC.md` / `tasks.md`
6. Current code and tests
7. Workflow memory (STATE.md notes, handoff, lessons)

A lower source never overrides a higher one. If code contradicts the spec, fix the code or open a [spec change](spec-change.md) — do not quietly edit the spec to match the code.

## Definition of Done (layers)

A layer is done only when its evidence exists. Do not claim a higher layer from a lower one.

| Layer | Evidence | Owner |
| ----- | -------- | ----- |
| **Task** | Assigned "Done when" + assigned test IDs pass; gate command exit 0; no weakened/skipped tests | Implementer |
| **Feature** | Independent Verifier PASS in `validation.md` (evidence-or-zero per AC); sensor killed mutants or recorded an honest fallback | Verifier ≠ author |
| **Merge** | Review round has no open critical/high issues (or user accepted residual risk); project CI/policy if the user asked to publish | Reviewer, then user |

Quick mode: Task layer = `TASK.md` verify + `SUMMARY.md`. Feature/Merge layers are N/A unless the change later migrates to the full pipeline.

## Artifact matrix (sizing)

Create a file only when the cell requires it. Absence means the phase was skipped — never scaffold empty files.

| Artifact | Quick | Medium | Large | Complex |
| -------- | ----- | ------ | ----- | ------- |
| `TASK.md` / `SUMMARY.md` | required | — | — | — |
| `PRD.md` | — | brief | full | full + discuss |
| Ambiguity Ledger | — | section in spec | section in spec | section in spec |
| `surface.md` | — | if public surface | if public surface | if public surface |
| `tests.md` | — | IDs in spec or brief catalog | catalog | catalog |
| `TECHSPEC.md` | — | skip (inline) | required | required + research |
| `threat-model.md` | — | if trigger | if trigger | if trigger |
| `tasks.md` + graph | — | skip (inline) | required | required |
| `validation.md` | SUMMARY | author report | Verifier | Verifier + UAT |
| `reviews-NNN/` | — | if security/UI risk | after Verifier | after Verifier |

Public surface = CLI, HTTP/API, SDK, or UI that a user or agent types/sees.

Threat-model trigger: [threat-model.md](threat-model.md). Spec change: [spec-change.md](spec-change.md).
