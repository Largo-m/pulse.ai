---
name: cy-create-tasks
description: Decomposes PRDs and TechSpecs into detailed, independently implementable task files with enrichment from codebase exploration. Use when a PRD or TechSpec exists and needs to be broken down into executable tasks, or when task files need enrichment with implementation context. Do not use for PRD creation, TechSpec generation, or direct task execution.
argument-hint: "[feature-name] [prd-file]"
---

# Create Tasks

Decompose requirements into detailed, actionable task files with codebase-informed enrichment.

**Language:** `references/task-template.md` and `references/task-context-schema.md` may stay in English as structural references. All generated `_tasks.md` content, all prose inside `task_NN.md` files (titles after the H1 prefix, Overview, subtasks, implementation details, tests, success criteria), and user-facing summaries MUST be written in **Portuguese (Brazil)**. Keep identifiers, paths, and code symbols aligned with the repository.

## Required Inputs

- Feature name identifying the `.workflow/tasks/<name>/` directory.
- At minimum, `_prd.md` or `_techspec.md` in that directory.

## Workflow

1. Load context.
   - Read `_prd.md` and `_techspec.md` from `.workflow/tasks/<name>/`.
   - Read existing ADRs from `.workflow/tasks/<name>/adrs/` to understand the decision context behind requirements and design choices.
   - If `_techspec.md` is missing:
     - Warn the user that tasks will be higher-level without TechSpec implementation guidance.
     - Derive tasks from PRD functional requirements and user stories instead of TechSpec implementation sections.
     - During enrichment, rely more heavily on codebase exploration to fill `## Implementation Details`, `### Relevant Files`, and `### Dependent Files`.
     - Mark `<requirements>` with PRD-derived behavioral requirements instead of TechSpec-derived technical requirements.
     - Explicitly call out missing implementation detail gaps in the task body instead of inventing specifics.
   - If both `_prd.md` and `_techspec.md` are missing, stop and ask the user to create at least one first.
   - Spawn an Agent tool call to explore the codebase for files to create or modify, test patterns, and coding conventions.
   - For each task file's YAML frontmatter `type` field, use one of: `frontend`, `backend`, `docs`, `test`, `infra`, `refactor`, `chore`, `bugfix`.

2. Break down into tasks.
   - Decompose implementation sections from the TechSpec into granular, independently implementable tasks.
   - **Each task MUST be independently implementable when all of its declared dependencies are met.** No task may require undeclared work from another task. If two tasks share a tight coupling, either merge them or extract the shared piece into a dependency task.
   - **No circular dependencies.** If task A depends on task B, task B must NOT depend on task A (directly or transitively).
   - Each task must have: title, type, complexity, and dependencies.
   - Assign complexity using these criteria:
     - `low`: Single file change, no new interfaces, no concurrency, straightforward logic.
     - `medium`: 2-4 files, may introduce a new interface or type, limited integration points.
     - `high`: 5+ files, new subsystem or significant refactor, multiple integration points, concurrency involved.
     - `critical`: Cross-cutting change affecting many packages, high risk of regression, requires coordination with other tasks.
   - When a task directly implements or is constrained by a specific ADR, include the ADR reference in the task's "Related ADRs" section under Implementation Details.
   - Embed test requirements in every task. Never create separate tasks dedicated solely to testing.
   - Follow the structure defined in `references/task-template.md`.
   - Refer to `references/task-context-schema.md` for metadata field definitions.

3. Present task breakdown for interactive approval.
   - Show all tasks with: titles, descriptions, complexity ratings, and dependency chains (in Portuguese).
   - Wait for user feedback before proceeding.
   - If the user requests changes, revise the breakdown and present again.
   - Iterate until the user explicitly approves.

4. Generate task files.
   - Write `_tasks.md` as the master task list using this exact markdown table format (column headers stay English to match the table scaffold; cell content in Portuguese):
     ```markdown
     # [Feature Name] — Task List

     ## Tasks

     | # | Title | Status | Complexity | Dependencies |
     |---|-------|--------|------------|--------------|
     | 01 | [Task title] | pending | [low/medium/high/critical] | [task_NN, ... or —] |
     ```
   - Write individual task files as `task_01.md`, `task_02.md`, through `task_N.md`.
   - Task files use the `task_` prefix without a leading underscore.
   - Each file must start with YAML frontmatter containing `status`, `title`, `type`, `complexity`, and `dependencies`. Use `dependencies: []` when there are no dependencies — do not omit the field.
   - Task numbering must be sequential and consistent between `_tasks.md` and individual files.

5. Enrich each task file.
   - For each task file, check whether it already has `## Overview`, `## Deliverables`, and `## Tests` sections. If all three exist, skip enrichment for that file.
   - Map the task to PRD requirements and TechSpec guidance.
   - Spawn an Agent tool call to discover relevant files, dependent files, integration points, and project rules for this specific task.
   - Fill ALL template sections from `references/task-template.md`. Every task file MUST contain each of the following sections — omitting any is a failure:
     - `## Overview`: what the task accomplishes and why, in 2-3 sentences (Portuguese).
     - `<critical>` block: the standard critical reminders block (read PRD/TechSpec, reference TechSpec, focus on WHAT, minimize code, tests required).
     - `<requirements>` block: specific, numbered technical requirements using MUST/SHOULD language (Portuguese).
     - `## Subtasks`: 3-7 checklist items describing WHAT, not HOW (Portuguese).
     - `## Implementation Details`: file paths to create or modify, integration points. Reference TechSpec for patterns (Portuguese).
     - `### Relevant Files`: discovered paths from codebase exploration with brief reasons (Portuguese).
     - `### Dependent Files`: files that will be affected by this task with brief reasons (Portuguese).
     - `### Related ADRs`: links to relevant ADRs if any exist, or omit subsection if no ADRs apply.
     - `## Deliverables`: concrete outputs with mandatory test items and at least 90% coverage target (Portuguese).
     - `## Tests`: specific test cases as checklists, split into unit tests and integration tests categories (Portuguese).
     - `## Success Criteria`: measurable outcomes including "All tests passing" and "Test coverage >=90%" (Portuguese).
   - Reassess complexity based on exploration findings and update if changed.
   - Update the task file in place with enriched content.
   - If enrichment fails for one task, continue to the next and report all failures at the end.

## Anti-Patterns

Do NOT produce tasks with these defects:

- **Mega-tasks.** If a task touches more than 7 files or has more than 7 subtasks, it is too broad. Split it into smaller tasks with explicit dependencies between them.
- **TechSpec duplication.** Do NOT copy interface definitions, code snippets, or architectural diagrams from the TechSpec into task files. Reference the TechSpec section by name (e.g., "See TechSpec 'Interfaces principais' section") instead of reproducing its content.
- **Vague test cases.** Do NOT write test descriptions like "test the happy path" or "verify error handling." Each test case must name the specific input, condition, or behavior being verified (e.g., "POST /job/done with unknown job ID returns 404").

## Error Handling

- If both `_prd.md` and `_techspec.md` are missing, stop and ask the user to create at least one first.
- If the user rejects the task breakdown, incorporate all feedback before presenting again.
- If codebase exploration reveals task boundaries that do not match the TechSpec, note the discrepancy and ask the user how to proceed.
- If the target directory does not exist, create it.
- If a task file already exists and is fully enriched, skip it and move to the next.
