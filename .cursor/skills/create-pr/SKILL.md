---
name: create-pr
description: Opens a PR from the current branch to main using the GitHub MCP, following references/pull-request-template.md and, if present, .github/pull_request_template.md. PR body and user-facing text are in PT-BR; the PR title follows Conventional Commits in English. On-demand only. Use only when the user explicitly asks to create a PR, open a pull request, or prepare a PR to main. Never run automatically.
readonly: false
---

# Create PR Workflow (GitHub MCP)

## Goal

Create a PR from the current branch to `main` via **GitHub MCP** (server `user-github`, tool `create_pull_request`), following the reference model [references/pull-request-template.md](references/pull-request-template.md); if the repository has one, also align with [.github/pull_request_template.md](.github/pull_request_template.md) (**repository template takes precedence**).

**Output language:** the PR **title** is in **English** (Conventional Commits, step 2). The PR **body** (`body`), any manual-creation fallback, and the user summary (step 5) must be in **Brazilian Portuguese (pt-BR)** — even if the reference template is in English, **translate or adapt** section headings, labels, and prose to pt-BR when filling; keep technical names (classes, APIs, flags) as they appear in code when those are the canonical identifiers.

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

### 2. Generate the PR title

Use the format:

```
<type>(<scope>): <subject>
```

Use Conventional Commits: feat, fix, docs, style, refactor, test, chore, etc.
The title should summarize the PR concisely (e.g. `feat(hourly-rate): add get and upsert endpoints`).

### 3. Fill the PR body

Use [references/pull-request-template.md](references/pull-request-template.md) (market-style structure; section headings in the file may be English). Fill each section from commits and code.

**Required:** the final Markdown `body` must be **fully in pt-BR** (`##` headings, paragraphs, lists, checklists). Do not send an English PR description to GitHub unless the repository’s official template is fixed in English **and** the user explicitly requests another language.

If [.github/pull_request_template.md](.github/pull_request_template.md) exists, follow its section order and checklist items while keeping filled content in **pt-BR** unless the user overrides.

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
- **Title:** English, Conventional Commits (step 2)
- **PR body, manual fallback, and user summary:** **pt-BR** (mandatory); the English text in the reference file is only a structural skeleton
- Follow the template’s structure (section order and types); the language of filled content is **pt-BR**
