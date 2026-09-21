# Surface Contracts

Write `.pulse/specs/features/[feature]/surface.md` only when the feature has a **public surface**: CLI, HTTP/API, SDK, or UI. Internal-only work records a one-line "no public surface" note in spec.md Part/Design and skips this file.

Surface freezes WHAT the consumer types and sees **before** internal design. Part of Design serves this file; it does not invent a different API.

## Rules

- As-if-shipped: real names, real values, real output. No `<TBD>`.
- Zero internals: no package names, storage, or framework types.
- Pair every example: input → output (command → stdout, request → response).
- Agents are users too: structured flags (`--json`) and exit codes belong here.
- UI-bearing work includes a surface map of screens, states, and viewports. Named visual references become Visual Contract rows in the owning task (see [review.md](review.md) and Tasks).

## Skeleton

```markdown
# Surface: [Feature]

Public contract. Companion to spec.md. tests.md E2E cases copy these examples verbatim.

## Golden Path

[Shortest real sequence from nothing to the core outcome, as a runnable transcript]

## CLI

### [verb]

Invocation:

Output (human):

Output (`--json`):

Exit code:

Failure:

## HTTP

### [METHOD path]

Request:

Response success:

Response errors:

## UI map (only if UI-bearing)

| ID | Surface | Kind | Change | Stories |
| -- | ------- | ---- | ------ | ------- |
| S1 | [screen] | new/modify | [one line] | [IDs] |

### S1. [Surface]

- Today: [file:line or new]
- Change:
- States: empty, pending, error, permission, scale
- Visual reference: [path or none]

## Out of surface

[What this feature will not expose]
```

If the feature is UI-bearing and names a visual reference, each implementation task that owns that surface carries Visual Contract rows (reference, state, viewport, evidence owner). Ordinary copy tweaks do not acquire reference parity.
