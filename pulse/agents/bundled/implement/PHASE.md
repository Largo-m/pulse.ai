Workspace: `{{workspace}}`
Feature: `{{feature_slug}}`
Original task: {{user_prompt}}
Current task: **{{wave_label}}**
Task: {{task_ids}}

{{isolation}}

{{agent}}

## Execute phase — implement the task

Read `{{feature_dir}}/PRD.md`
{{#if techspec_line}}{{techspec_line}}
{{/if}}Read `{{feature_dir}}/tasks.md` — implement **only** this task:

{{task_list}}

Plan → implement → verify the task's Done when.
Tick the task off in `tasks.md` once verification passes.

Update `{{workflow_path}}`:
   - `current_task_id`: this task
   - Do **not** set `status: done` on tasks — Pulse validates the gates and marks
     them done afterwards

**Unit tests only in this phase.** Do not write integration or end-to-end tests:
those belong to a later step. If the task cannot be proven by unit tests alone,
implement it anyway and record the gap in the **Deferred test coverage** section
of `tasks.md`, with the reason (which boundary is crossed: process, network,
browser, database, external service).

Follow `implement.md` for this task.
Do not implement other tasks.
Do not run git operations.

{{output_language}}
