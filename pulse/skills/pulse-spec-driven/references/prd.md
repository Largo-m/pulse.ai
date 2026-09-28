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
