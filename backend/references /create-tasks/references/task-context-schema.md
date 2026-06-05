# Task Frontmatter Schema

Task metadata lives in YAML frontmatter at the top of each `task_NN.md` file.

## Required Fields

- `status`: Task lifecycle state.
- `title`: Human-readable task title. It must match the first H1 in the task body.
- `type`: Work category. One of: `frontend`, `backend`, `docs`, `test`, `infra`, `refactor`, `chore`, `bugfix`.
- `complexity`: Difficulty rating. Must be one of: `low`, `medium`, `high`, `critical`.
- `dependencies`: YAML list of task file names that must be completed before this task. Use `[]` when there are no dependencies.

## Status Values

Valid `status` values:

- `pending` — task has not been started.
- `in_progress` — task is currently being worked on.
- `completed` — task is finished and verified.
- `done` — treated as completed.
- `finished` — treated as completed.

## File Naming

Task files use the pattern `task_NN.md` with zero-padded numbers:

- `task_01.md`, `task_02.md`, `task_10.md`, `task_99.md`

The leading underscore prefix is reserved for meta documents:

- `_prd.md` — Product Requirements Document
- `_techspec.md` — Technical Specification
- `_tasks.md` — Master task list

Each task file MUST start with YAML frontmatter before the Markdown body.
