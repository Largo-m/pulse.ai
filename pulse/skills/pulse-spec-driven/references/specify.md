# Specify

**Goal**: Capture WHAT to build with testable, traceable requirements.

Read [invariants.md](invariants.md) first. If the feature has ambiguous gray areas, trigger [discuss.md](discuss.md) inside this phase. Write every unresolved item to the [Ambiguity Ledger](ambiguity.md).

## Process

### 1. Load confirmed lessons

Read STATE.md Lessons Learned with `Status: confirmed` that match this feature's area. Skip `candidate` and `quarantined`. See [lessons.md](lessons.md).

### 2. Clarify Requirements

Thinking partner, not interviewer. Read `.pulse/specs/`, codebase, user message. Draft from what is known.

Facts you look up (Knowledge Verification Chain). Decisions you ask via [user-input.md](user-input.md).

**Must resolve before writing spec.md:**

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

### 5. Implicit-requirement sweep + ledger

Follow [ambiguity.md](ambiguity.md). Large/Complex: every dimension. Medium: obvious dimensions only.

### 6. Surface and tests (conditional)

If there is a public surface, write [surface.md](surface.md) before internal design. Write [tests.md](tests-catalog.md) for Large/Complex (and Medium with a public surface).

If a [threat-model.md](threat-model.md) trigger is present, note it here; the model itself is written in Design.

### 7. Closure gate

Before presenting the spec:

1. Every AC has one interpretation and a precise expected outcome
2. Ledger has no `open` rows
3. Motivating Problem is stated; P1 delivers it
4. `python3 <skill-dir>/scripts/validate_spec.py <feature>` exits 0 ([gates.md](gates.md))

Then confirm with the user via CLI. Do not start implementation because the spec file exists.

Changing an approved spec later uses [spec-change.md](spec-change.md).

---

## Template: `.pulse/specs/features/[feature]/spec.md`

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
| AL-01 | [gray area] | decided | [what] | [why] |

Open questions: none — all resolved or assumed.

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
| [FEAT]-01      | P1    | Design | Pending |

**ID format:** `[CATEGORY]-[NUMBER]`
**Status:** Pending → In Design → In Tasks → Implementing → Verified

## Spec Changes

[Append SC-NNN records here. Empty until the first change.]

## File References

Read-first index for implementers (path + why). Copy a subset into each task.

### Repo Files

- `path/to/file:start-end` — [why]

## Success Criteria

- [ ] [Measurable outcome]
```
