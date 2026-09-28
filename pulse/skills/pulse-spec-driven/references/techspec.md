# Techspec

**Goal**: Define HOW to build it. Architecture, components, what to reuse.

**Skip this phase when:** The change is straightforward — no architectural decisions, no new patterns, no component interactions to plan. For simple features, design happens inline during Execute.

## Process

### 1. Load Context

Read `.pulse/specs/features/[feature]/PRD.md` before designing. If `.pulse/specs/features/[feature]/context.md` exists, load it too — it contains implementation decisions that constrain the design (layout choices, behavior preferences, interaction patterns). Decisions marked as "Agent's Discretion" are yours to decide.

Read STATE.md active AD-NNN entries and **confirmed** lessons. Conform or supersede (new AD-NNN). Silently ignoring an active decision is not allowed.

If `surface.md` exists, Techspec serves that frozen surface — do not invent a different public API.

If a [threat-model.md](threat-model.md) trigger is present, write `threat-model.md` in this phase and map each TM-ID to a spec SHALL or an explicit deferral.

### 1.5. Research (Optional but Recommended)

If the feature involves unfamiliar technology, patterns, or integrations, research before designing. Document findings briefly in the design doc or as inline notes. This prevents incorrect assumptions from propagating into tasks.

Follow the **Knowledge Verification Chain** (see SKILL.md) in strict order:

```
Codebase → Project docs → Context7 MCP → Web search → Flag as uncertain
```

**CRITICAL: NEVER assume or fabricate information.** If you cannot find an answer through the chain, explicitly say "I don't know" or "I couldn't find documentation for this". Inventing an API, a pattern, or a behavior that doesn't exist is far worse than admitting uncertainty. Wrong assumptions propagate through design → tasks → implementation and cause cascading failures.

Good triggers for research: new libraries, unfamiliar APIs, performance-sensitive features, security-sensitive features, patterns you haven't used in this codebase before.

### 1.8. Implicit-requirement sweep (Techspec owns this)

PRD captured what the product team wants. This sweep captures what the system must guarantee to deliver it — the dimensions that have no product-team answer because they are mechanisms, not outcomes.

Bound the sweep to this feature; never invent requirements outside the spec boundary.

| Dimension | What to cover |
| --------- | ------------- |
| Input validation & bounds | Limits, formats, sanitization |
| Failure / partial-failure | Timeouts, partial saves, rollbacks |
| Idempotency / retry / dedup | Safe retries, duplicate keys |
| Auth boundaries & rate limits | Who can call what, throttle rules |
| Concurrency / ordering | Races, ordering guarantees |
| Data lifecycle / expiry | TTL, archival, deletion |
| Observability | Logs, metrics, tracing hooks |
| External-dependency failure | Fallbacks, timeouts |
| State-transition integrity | Valid transitions, guards |

**Sizing:**

- **Complex / Large:** every dimension → `decided` or `n/a because …`. No blanks.
- **Medium:** only dimensions obviously present; collapse the rest to one `n/a` row.
- **Small / Quick:** skip the sweep.

Each dimension lands in the Ambiguity Ledger ([ambiguity.md](ambiguity.md)) as a `decided` or `n/a` row. `assumed` does not exist: when the choice is a real trade-off with no obvious answer in the codebase, ask the technical owner via [user-input.md](user-input.md) instead of picking for them. Here the question may — and should — use technical vocabulary: this is the phase where that vocabulary belongs.

When a dimension's choice is forced by something the product team already decided, say so in the rationale and cite the PRD row: `AL-04 decided (follows AL-02: cancelled orders stay visible for 12 months)`.

### 2. Define Architecture

Overview of how components interact. Use mermaid diagrams when helpful. Before creating any diagrams, check if the `mermaid-studio` skill is available (see Skill Integrations in SKILL.md).

### 3. Identify Code Reuse

**CRITICAL**: What existing code can we leverage? This saves tokens and reduces errors.

If `.pulse/specs/codebase/CONCERNS.md` exists, check it before designing. Any component flagged as fragile, carrying tech debt, or having test coverage gaps requires extra care in the design — document how the design mitigates those concerns.

### 4. Define Components and Interfaces

Each component: Purpose, Location, Interfaces, Dependencies, What it reuses.

### 5. Define Data Models

If the feature involves data, define models before implementation.

---

## Template: `.pulse/specs/[feature]/TECHSPEC.md`

````markdown
# [Feature] Techspec

**Spec**: `.pulse/specs/[feature]/PRD.md`
**Status**: Draft | Approved

---

## Architecture Overview

[Brief description of the architecture approach]

```mermaid
graph TD
    A[User Action] --> B[Component A]
    B --> C[Service Layer]
    C --> D[Data Store]
    B --> E[Component B]
```
````

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component            | Location            | How to Use                |
| -------------------- | ------------------- | ------------------------- |
| [Existing Component] | `src/path/to/file`  | [Extend/Import/Reference] |
| [Existing Utility]   | `src/utils/file`    | [How it helps]            |
| [Existing Pattern]   | `src/patterns/file` | [Apply same pattern]      |

### Integration Points

| System         | Integration Method                      |
| -------------- | --------------------------------------- |
| [Existing API] | [How new feature connects]              |
| [Database]     | [How data connects to existing schemas] |

---

## Components

### [Component Name]

- **Purpose**: [What this component does - one sentence]
- **Location**: `src/path/to/component/`
- **Interfaces**:
  - `methodName(param: Type): ReturnType` - [description]
  - `methodName(param: Type): ReturnType` - [description]
- **Dependencies**: [What it needs to function]
- **Reuses**: [Existing code this builds upon]

### [Component Name]

- **Purpose**: [What this component does]
- **Location**: `src/path/to/component/`
- **Interfaces**:
  - `methodName(param: Type): ReturnType`
- **Dependencies**: [Dependencies]
- **Reuses**: [Existing code]

---

## Data Models (if applicable)

### [Model Name]

```typescript
interface ModelName {
  id: string
  field1: string
  field2: number
  createdAt: Date
}
```

**Relationships**: [How this relates to other models]

### [Model Name]

```typescript
interface AnotherModel {
  id: string
  // ...
}
```

---

## Error Handling Strategy

| Error Scenario | Handling      | User Impact      |
| -------------- | ------------- | ---------------- |
| [Scenario 1]   | [How handled] | [What user sees] |
| [Scenario 2]   | [How handled] | [What user sees] |

---

## Tech Decisions (only non-obvious ones)

| Decision          | Choice          | Rationale     |
| ----------------- | --------------- | ------------- |
| [What we decided] | [What we chose] | [Why - brief] |

Record a STATE.md AD-NNN only when the choice is hard to reverse, surprising without context, and the product of a real trade-off. Feature-local obvious choices stay in this table.

## File References

Copy the spec index subset this design depends on (`path:line` + why). Tasks copy their slice from here.

## Threat Model

If no trigger: `N/A because [reason]`. If trigger: link `threat-model.md`.

---

## Tips

- **Load context first** — If context.md exists, decisions there are locked
- **Research when uncertain** — 5 minutes of research prevents hours of rework
- **Reuse is king** — Every component should reference existing patterns
- **Interfaces first** — Define contracts before implementation
- **Keep it visual** — Diagrams save 1000 words (check mermaid-studio skill in Skill Integrations)
- **Small components** — If component does 3+ things, split it
- **Check CONCERNS.md** — If it exists, flag fragile areas the design must address
- **Confirm before Tasks** — User approves design via [user-input.md](user-input.md) before breaking into tasks
