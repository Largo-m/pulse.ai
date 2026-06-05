---
name: create-pr
description: Opens a PR from the current branch to main using the GitHub MCP. PR body follows the monorepo template at <git-root>/.github/pull_request_template.md (fallback references/pull-request-template.md). PR body and user-facing text are in PT-BR; the PR title follows Conventional Commits in English with monorepo area scope (backend, frontend, or backend,frontend). On-demand only. Use only when the user explicitly asks to create a PR, open a pull request, or prepare a PR to main. Never run automatically.
readonly: false
---

# Create PR Workflow (GitHub MCP)

## Goal

Create a PR from the current branch to `main` via **GitHub MCP** (server `user-github`, tool `create_pull_request`), using the PR body template resolved from the **monorepo git root** (not `backend/` or `frontend/` alone).

**Template resolution (precedence):**

1. `<git-root>/.github/pull_request_template.md` — official GitHub template at the repository root (`pulse.ai/.github/…`)
2. [references/pull-request-template.md](references/pull-request-template.md) — skill fallback if (1) is missing

Resolve `<git-root>` with `git rev-parse --show-toplevel` (run from any subdirectory).

**Output language:** the PR **title** is in **English** (Conventional Commits, step 2). The PR **body** (`body`), any manual-creation fallback, and the user summary (step 5) must be in **Brazilian Portuguese (pt-BR)**; keep technical names (classes, APIs, flags) as they appear in code when those are the canonical identifiers.

## Workflow

### 1. Analyze branch and changes

Run to gather context:

```bash
git branch --show-current
git log main..HEAD --oneline
git diff main..HEAD --stat
git remote get-url origin
```

Extract `owner` and `repo` from the remote.
Read changed files to understand what was done.

**Monorepo areas:** classify changed paths into `backend/` (Python API/services) and `frontend/` (Flutter app). A PR may touch one area or both.

```bash
git diff main..HEAD --name-only
```

### 2. Generate the PR title

Use Conventional Commits in English:

```
<type>(<area>[/<feature>]): <subject>
```

- **`<type>`:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, etc.
- **`<area>`:** where the change lands in the monorepo — required:
  - `backend` — only `backend/` changed
  - `frontend` — only `frontend/` changed
  - `backend,frontend` — both areas changed (cross-cutting feature or integration)
- **`<feature>`:** optional domain/module when it clarifies the PR (e.g. `orchestrator`, `hourly-rate`, `auth`). Omit when the subject alone is clear.
- **`<subject>`:** imperative, lowercase, no trailing period; describe the user-visible or architectural outcome, not file names.

**Choosing `<area>`:**

| Changed paths | `<area>` |
|---------------|----------|
| `backend/**` only | `backend` |
| `frontend/**` only | `frontend` |
| both | `backend,frontend` |
| repo root / shared config only (`.github/`, `.cursor/`, root docs) | infer from intent; default `chore` without area or use the area most affected |

**Examples:**

| Scenario | Title |
|----------|-------|
| New API endpoints | `feat(backend/hourly-rate): add get and upsert endpoints` |
| Flutter screen only | `feat(frontend/orchestrator): add PRD session restore UI` |
| API + UI wiring | `feat(backend,frontend/orchestrator): wire PRD run status reconciliation` |
| Backend bugfix | `fix(backend/auth): validate token expiry on refresh` |
| CI in both stacks | `chore(backend,frontend): align PR templates and CI checks` |
| Docs at repo root | `docs: document monorepo setup and local dev` |

**Anti-patterns (avoid):**

- Scope by file or layer alone: `feat(api):`, `feat(ui):` — use `backend` / `frontend` instead.
- Generic scope when area is known: `feat(app):` or `feat(pulse):`.
- Subject that hides cross-area work: if both stacks change, use `backend,frontend`, not a single-area scope.

### 3. Fill the PR body

Read the template using template resolution above. Fill each section from commits and code.

```bash
git rev-parse --show-toplevel
# then read: <git-root>/.github/pull_request_template.md
```

**Required:** the final Markdown `body` must be **fully in pt-BR** (`##` headings, paragraphs, lists, checklists). Follow the template’s **section order and checklist items** exactly. Do not send an English PR description unless the user explicitly requests another language.

### 4. Create the PR via GitHub MCP

Call the MCP tool `create_pull_request`:

- **Server**: `user-github` (or `github`, depending on setup)
- **Tool**: `create_pull_request`
- **Arguments**:
  - `owner`: from git remote
  - `repo`: from git remote
  - `head`: current branch
  - `base`: `main`
  - `title`: title from step 2
  - `body`: full body as Markdown

Ensure the `head` branch is pushed to the remote before creating the PR.

### 5. Final output

On success, return to the user **in pt-BR**:

1. URL of the created PR
2. Title and a short summary of changes

If the MCP call fails (auth, permissions, etc.), provide a ready-to-paste title and body for manual creation on GitHub (**body in pt-BR**).

## Rules

- Run only on explicit user request
- Prefer GitHub MCP over the `gh` CLI
- Screenshots and evidence are optional
- Always inspect commits and code before writing
- **Title:** English, Conventional Commits with monorepo `<area>` (`backend`, `frontend`, or `backend,frontend`) — step 2
- **PR body, manual fallback, and user summary:** **pt-BR** (mandatory)
- **Template path:** `<git-root>/.github/pull_request_template.md` at monorepo root; never `backend/.github/` or `frontend/.github/`
- Follow the resolved template’s section order and checklist items
