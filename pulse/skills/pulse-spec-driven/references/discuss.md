# PRD: Discuss Gray Areas

**Goal:** Capture HOW the user envisions the feature when the spec has ambiguous areas. This is NOT a separate phase — it's triggered within PRD when the agent detects gray areas that need user input.

**Trigger:** Automatically when gray areas are detected during spec creation, or explicitly via "discuss feature", "how should this work?", "capture context"

**When to trigger (auto-detect):** The spec contains user-facing behavior that could go multiple ways AND the user hasn't expressed a preference. If the spec is clear and unambiguous, skip this entirely.

**When NOT to trigger:** Infrastructure work, CRUD operations, well-defined API contracts, anything where the "how" is obvious from the "what".

Technical dimensions (persistence, external calls, auth, concurrency, state transitions) do **not** trigger discuss — Techspec owns them ([techspec.md](techspec.md)). What triggers discuss is their product-visible face: not "do we retry the payment", but "what does the person see when the payment does not go through".

Every gray area is written to the Ambiguity Ledger in PRD.md and leaves as `decided` or `n/a` — never `assumed`, never dropped. See [ambiguity.md](ambiguity.md) for pace (Quick / Guided / Detailed) and ledger statuses.

**You are talking to the product team.** Every question here must be answerable by someone who has never opened the codebase. The banned-vocabulary list in [prd.md](prd.md) (**Product language only**) applies to every question in this file.

## Why This Phase Exists

Specifications capture WHAT to build. Techspec captures the architecture. But neither captures the user's vision for ambiguous areas — layout preferences, interaction patterns, error handling style, content tone. Without this, the agent guesses. With this, the agent builds what the user actually imagined.

The output — `context.md` — feeds directly into Techspec and Tasks:

- **Techspec reads it** to know what decisions are locked vs. flexible
- **Tasks reads it** to include specific behaviors in task definitions

## Process

### 1. Analyze the Feature

Read `.pulse/specs/features/[feature]/PRD.md` and identify the domain:

| Domain                         | Gray areas to explore                                         |
| ------------------------------ | ------------------------------------------------------------- |
| Something users **SEE**        | Layout, density, interactions, empty states, visual hierarchy |
| Something users **CALL** (API) | Response format, errors, auth, versioning, rate limiting      |
| Something users **RUN** (CLI)  | Output format, flags, modes, error handling, verbosity        |
| Something users **READ**       | Structure, tone, depth, flow, navigation                      |
| Something being **ORGANIZED**  | Grouping criteria, naming, duplicates, exceptions             |

Generate 3-4 **feature-specific** gray areas. Not generic categories, but concrete decisions for THIS feature.

### 2. Present Gray Areas

Analyze PRD.md and identify gray areas autonomously. When user input is required to choose areas or resolve ambiguity, follow [user-input.md](user-input.md) — present the feature boundary and all pending area/decision questions in one CLI batch at the end of the response.

Do NOT include a "skip all" option when the user explicitly invoked discuss.

### 3. Choose pace once, then deep-dive

Recommend **Guided**. Honor mid-discussion switches ("go faster", "just decide").

For each selected area, resolve decisions through CLI batches per [user-input.md](user-input.md) and [ambiguity.md](ambiguity.md):

1. Lead with a recommended option and one-line rationale
2. Guided: at most 2 independent questions per batch; dependent questions one at a time. Never dump 3+ product questions in one batch
3. After answers, update the Ambiguity Ledger (`decided`) and continue until the next blocking decision
4. Keep looping until no area is unresolved. There is no round limit and no "we can settle this later" — an unanswered area means another batch next turn
5. When all areas are resolved, write `context.md` (decisions only — not a questionnaire)

**Question design** (when forming CLI batches — see [user-input.md](user-input.md)):

- Options should be concrete ("Card layout" not "Option A")
- Each answer should inform the next question
- Include "You decide" as an option when reasonable — captures agent discretion

### 4. Scope Guardrail (CRITICAL)

The feature boundary from PRD.md is **fixed**. Discussion clarifies HOW to implement, never WHETHER to add new capabilities.

**Allowed:** "How should posts be displayed?" (clarifying ambiguity)
**Not allowed:** "Should we also add comments?" (new capability)

When user suggests scope creep: "That sounds like a separate feature. I'll note it in Deferred Ideas. Back to [current area]."

### 5. Write context.md

---

## Template: `.pulse/specs/features/[feature]/context.md`

```markdown
# [Feature] Context

**Gathered:** [date]
**Spec:** `.pulse/specs/features/[feature]/PRD.md`
**Status:** Ready for design

---

## Feature Boundary

[Clear statement of what this feature delivers — the scope anchor from PRD.md]

---

## Implementation Decisions

### [Area 1 that was discussed]

- [Specific decision made]
- [Another decision if applicable]

### [Area 2 that was discussed]

- [Specific decision made]

### [Area 3 that was discussed]

- [Specific decision made]

### Agent's Discretion

[Areas where user explicitly said "you decide" — agent has flexibility here during design/implementation]

---

## Specific References

[Any "I want it like X" moments, product references, specific behaviors, interaction patterns mentioned during discussion]

[If none: "No specific requirements — open to standard approaches"]

---

## Deferred Ideas

[Ideas that came up during discussion but belong in other features/phases. Captured here so they're not lost, but explicitly out of scope]

[If none: "None — discussion stayed within feature scope"]
```

---

## Tips

- **Decisions, not vision** — "Card-based layout with subtle shadows" is a decision. "Should feel modern" is not.
- **Scope is sacred** — Deferred Ideas captures scope creep without losing ideas
- **User = visionary, Agent = builder** — Ask about how they imagine it, not about technical implementation
- **Don't ask about:** Technical architecture, performance, implementation details — that's Techspec's job
- **Confirm before Techspec** — User approves context.md via CLI confirmation per [user-input.md](user-input.md) before moving to design phase
