Workspace: `{{workspace}}`
Feature: `{{feature_slug}}`
Original task: {{user_prompt}}

{{isolation}}

{{agent}}

{{workflow_state}}

## Tasks phase — break into atomic tasks (do NOT implement)

Read `{{feature_dir}}/PRD.md`
Read `{{feature_dir}}/TECHSPEC.md` if it exists
Write `{{feature_dir}}/tasks.md` with one heading per task (`### T1: …`, `### T2: …`).
Do not end this phase without that file. A clarifying question does not approve the phase.
ACP already loads the workspace rules/skills; do not re-read the whole set by habit.
Update `{{workflow_path}}`:
   - `phases.tasks.status: awaiting_approval`
   - `current_phase: tasks`
   - Fill `tasks` with `[{id: T1, title: ...}, ...]` in execution order

No task carries `Tests: integration` or `Tests: e2e` — the implementation writes
unit tests only. A layer that would need integration/e2e becomes a row in the
**Deferred test coverage** section of `tasks.md`, with ID, type, what it covers
and which boundary is crossed. The gap stays visible and traceable, not silent.

Run the 3 mandatory checks from `tasks.md` before presenting.
Present a summary: task count, execution phases, critical dependencies, and what
ended up in Deferred test coverage.

{{approval}}

{{output_language}}
