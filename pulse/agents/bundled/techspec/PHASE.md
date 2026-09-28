Workspace: `{{workspace}}`
Feature: `{{feature_slug}}`
Original task: {{user_prompt}}

{{isolation}}

{{agent}}

{{workflow_state}}

## Techspec phase — define HOW to build it (do NOT implement)

Read `{{feature_dir}}/PRD.md` (and `context.md` if it exists).
Write `{{feature_dir}}/TECHSPEC.md` per `techspec.md`.
Read rules/conventions from disk only when they bear on an architecture decision.

The **implicit-requirement sweep** belongs to this phase (PRD only covers
product): input validation, partial failure, idempotency/retry, auth boundaries
and rate limits, concurrency/ordering, data lifecycle, observability,
external-dependency failure and state-transition integrity.
Each dimension becomes a `decided` or `n/a` Ambiguity Ledger row — `assumed` does
not exist. When the choice is a real trade-off with no obvious answer in the code,
ask the technical owner instead of deciding alone. Technical vocabulary is welcome
here.
Update `{{workflow_path}}`:
   - `phases.techspec.status: awaiting_approval`
   - `current_phase: techspec`

Present a summary: architecture, components, reuse of existing code.

{{approval}}

{{output_language}}
