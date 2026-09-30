Workspace: `{{workspace}}`
Original task: {{user_prompt}}

<!-- include: isolation -->

<!-- include: handoff -->

## Techspec phase — define HOW to build it (do NOT implement)

Read the feature's `PRD.md` (and `context.md` if it exists).
Write `TECHSPEC.md` next to them, per the `techspec.md` playbook above.
Read rules/conventions from disk only when they bear on an architecture decision.

The **implicit-requirement sweep** belongs to this phase (PRD only covers
product): input validation, partial failure, idempotency/retry, auth boundaries
and rate limits, concurrency/ordering, data lifecycle, observability,
external-dependency failure and state-transition integrity.
Each dimension becomes a `decided` or `n/a` Ambiguity Ledger row — `assumed` does
not exist. When the choice is a real trade-off with no obvious answer in the code,
ask the technical owner instead of deciding alone. Technical vocabulary is welcome
here.

Present a summary: the feature path, the architecture, the components, and what
existing code gets reused.

<!-- include: approval -->

<!-- include: output-language -->
