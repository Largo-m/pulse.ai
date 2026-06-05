# PRD: Local Branch Loading in Initialize Agent Modal

## Overview

When creating a new agent in Pulse, users select a recent local project and a Git branch. Today the branch dropdown shows placeholder values (`main`, `staging`, `feature/agent-init`) that do not reflect the user's repository. This feature replaces that placeholder with **all local branches** from the selected project's Git repository, so users can accurately record which branch the agent should be associated with.

The feature is for developers and operators using the orchestrator on desktop who work with locally imported project folders. Branch selection is **metadata for the agent record only** in MVP—no checkout or working-tree changes.

## Goals

- Eliminate mismatch between displayed branches and the user's actual local repository.
- Reduce agent misconfiguration caused by picking a non-existent or wrong branch name.
- Provide predictable UI feedback when Git is unavailable, loading, or failing.
- Enable a future phase where agent runtime honors the recorded branch without redesigning the modal flow.

**Target:** MVP in the next orchestrator increment after TechSpec approval.

## User Stories

### Primary — Orchestrator user

- As an orchestrator user, I want to see **local branches from my selected project** when I open "Novo agente", so that I can associate the agent with a branch that actually exists.
- As an orchestrator user, I want the **currently checked-out branch** pre-selected when I open the modal or switch projects, so that I do not have to hunt for my active branch.
- As an orchestrator user, I want the branch list to **update automatically when I change the project**, so that I never submit an agent tied to another project's branches.
- As an orchestrator user, I want a **clear loading state** while branches load, so that I know the app is working and not broken.
- As an orchestrator user, I want a **clear message when my folder is not a Git repo**, so that I understand why I cannot pick a branch.

### Secondary — Edge cases

- As an orchestrator user, when branch loading fails, I want a **disabled field with an error explanation**, so that I can switch project or cancel without guessing.
- As an orchestrator user with **no local projects**, I want the existing empty-project behavior unchanged.

## Core Features

### F1 — Dynamic local branch list (P0)

- **Trigger:** Modal opens with an initial project; user changes project in the dropdown.
- **Behavior:** Load and display **local branches only** (repository heads under the project path). Exclude remote-tracking refs, tags, and detached-HEAD pseudo-entries unless they appear as normal local branch names.
- **Default selection:** After a successful load, select the **current HEAD / checked-out branch**.
- **Persistence scope:** Selected branch is captured as part of agent initialization metadata when the user submits (submission wiring may be a separate task; this PRD requires the UI to expose the correct value).

### F2 — Loading state (P0)

- While branches are loading for the active project, the branch dropdown is **disabled** and shows a **loading indicator** (spinner or equivalent per design system).
- Project dropdown may remain enabled so the user can switch away during a slow load.

### F3 — Non-Git project handling (P0)

- If the selected project path is not a Git repository, the branch field is **disabled** with copy explaining that no Git repository was found (PT-BR, centralized in orchestrator strings).
- Submit behavior for non-Git projects: follow existing modal rules; branch field does not offer fake placeholder branches.

### F4 — Load failure handling (P0)

- If branch enumeration fails (permissions, corrupt repo, I/O error), the branch field is **disabled** with a **specific error message** (user-safe, no raw system details).
- User can change project or cancel the modal.

### F5 — Remove placeholder branches (P0)

- Hardcoded branch values (`main`, `staging`, `feature/agent-init`) are removed from the modal.

## User Experience

### Primary flow

1. User clicks "Novo agente" from the sidebar (recent projects visible).
2. Modal opens; project defaults to active recent project (existing behavior).
3. Branch field shows loading; local branches load for that project's path.
4. Loading completes; dropdown lists local branches; HEAD branch is selected.
5. User optionally changes project → branch field enters loading again → new list + new HEAD default.
6. User fills agent name/description, confirms branch, taps **Salvar** (branch value available for downstream agent creation).

### UX copy considerations (PT-BR)

- Loading: e.g. "Carregando branches…"
- Non-Git: e.g. "Este projeto não é um repositório Git."
- Generic load failure: e.g. "Não foi possível carregar as branches deste projeto."
- Optional helper (non-blocking): clarify that choosing a branch **does not alter** the repository in this version—only records intent for the agent.

### Accessibility

- Disabled states must expose semantics labels for screen readers (loading, error, empty).
- Loading indicator must not rely on color alone.

## High-Level Technical Constraints

- Branch data must be derived from the **same absolute path** stored on `LocalProjectEntity` for the selected project id.
- Operation is **local-only**; no network calls to Git hosting providers in MVP.
- Must work for projects imported via the existing local directory picker (any folder path; Git validation happens at branch-load time, not at import time).
- UI strings remain in orchestrator feature strings files (PT-BR); no inline literals in widgets.
- Desktop targets supported by the app (macOS, Windows, Linux) must behave consistently from the user's perspective.

## Non-Goals (Out of Scope)

- Checking out or switching branches in the repository.
- Fetching remote branches not present as local refs.
- Persisting "last branch per project" across modal sessions (Phase 2 candidate).
- Searching, filtering, or grouping branches (e.g. hide `copilot/*` worktrees).
- Validating that the project is a Git repo at import time.
- Cloned/remote repository flows (separate import-remote feature).
- Widget-level automated UI tests (project policy).

## Phased Rollout Plan

### MVP (Phase 1)

- F1–F5 as defined above.
- Reactive reload on project change.
- **Exit criteria:** Manual QA on at least one Git repo with multiple local branches; non-Git folder; simulated permission failure; HEAD default verified on project switch.

### Phase 2

- Remember last branch selected per project id when reopening the modal (override HEAD default when history exists).
- Optional branch search for repos with many local branches.

### Phase 3

- Agent runtime uses recorded branch to align execution context (checkout or worktree strategy defined in a future TechSpec).
- Remote branch awareness if product requires cloud-first workflows.

## Success Metrics

- **Accuracy:** 100% of branch options shown in QA scenarios exist in the selected repo's local heads (manual audit sample).
- **Default correctness:** HEAD branch pre-selected in ≥95% of successful loads in QA matrix.
- **Error clarity:** Users in moderated testing correctly interpret non-Git and failure states without support prompts.
- **Regression:** Zero placeholder branch names remain in the modal after release.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Users assume branch selection checks out code | In-modal helper text; TechSpec/agent docs reinforce metadata-only MVP |
| Slow load on large repos frustrates users | Loading state (F2); consider Phase 2 search/virtualization if reported |
| Non-Git projects are common | Clear disabled state (F3); import flow unchanged |
| Confusion when submit does not yet persist branch | Coordinate with agent-creation backlog; document in Open Questions |

## Architecture Decision Records

- [ADR-001: Reactive Local Branch Loading per Project](adrs/adr-001.md) — MVP uses automatic reload per project, local branches only, HEAD default, metadata-only scope.

## Open Questions

- Should **Salvar** be blocked when the branch field is disabled (non-Git / error), or allowed with branch omitted/null?
- Alphabetical vs Git's default ordering for branch names in the dropdown?
- Should the modal show branch count (e.g. "12 branches") for discoverability?
- Which downstream task owns **persisting** the selected branch on agent creation once submit is implemented?
