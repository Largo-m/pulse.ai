Workspace: `{{workspace}}`
Feature: `{{feature_slug}}`
Original task: {{user_prompt}}

{{isolation}}

{{agent}}

## Execute phase — implementation (implicit tasks)

Read `{{feature_dir}}/PRD.md`
Read `{{feature_dir}}/TECHSPEC.md` if it exists

The Tasks phase was skipped — list atomic steps inline, per `implement.md`, before
writing any code. If that comes to more than 5 steps, stop and record that a
`tasks.md` is needed.

Update `{{workflow_path}}`:
   - `phases.execute.status: done` when you finish

**Unit tests only in this phase.** Do not write integration or end-to-end tests:
those belong to a later step. If a step cannot be proven by unit tests alone,
implement it anyway and record the gap, naming the boundary being crossed
(process, network, browser, database, external service).

Implement, verify and update STATE.md.
Do not run git operations.

{{output_language}}
