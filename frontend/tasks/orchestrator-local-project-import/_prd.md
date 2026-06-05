# PRD: Local Project Import and Recent Projects Sidebar

## Overview

Pulse.AI is an agentic orchestration environment for desktop. Today, the orchestrator initializes in a standby empty state with no connection to the user's real codebases. Tech leads and architects who manage multiple team repositories need a fast way to register local project folders and switch context between them before any LLM-powered agents can operate on files.

This feature introduces **local folder import** and a **Recent Projects** sidebar on the orchestrator screen. Users pick a directory from the local filesystem; the product remembers it across sessions, surfaces up to ten recent projects, and highlights which project is currently selected. It deliberately stops short of opening a workspace, running agents, or integrating with Git remotes.

**Primary persona:** Tech lead / architect alternating between multiple team repositories.

**Why now:** The imported folder path is the foundation for a future phase where agents read, modify, and create files via LLM APIs. Without persisted project registration and visible recent context, that phase cannot ship safely.

## Goals

1. Enable tech leads to register a local project folder in under one minute from first launch.
2. Persist imported projects so the recent list survives application restarts.
3. Provide at-a-glance awareness of which project is **active** (selected) when switching between up to ten recent entries.
4. Preserve the existing empty-state experience until the user imports at least one project.
5. Establish a stable project identity (path + display name) for downstream agent capabilities without implementing agents in this release.

**Target outcome for MVP:** A tech lead can import two different local repos, see both in the sidebar, select either to mark it active, quit and relaunch the app, and still see the same list with correct ordering.

## User Stories

### Primary — Tech lead / architect

- As a **tech lead**, I want to **import a local project folder** so that **Pulse.AI knows which codebase I intend to orchestrate agents against in a future release**.
- As a **tech lead**, I want to **see my recently imported projects in a sidebar** so that **I can quickly tell which repos I have already registered without browsing the filesystem again**.
- As a **tech lead**, I want **the project I click in the sidebar to appear as active** so that **I always know which repository context I am focused on when juggling multiple team repos**.
- As a **tech lead**, I want **re-importing the same folder to refresh its position** so that **frequently used repos stay at the top of my recent list**.
- As a **tech lead**, I want **my recent projects to remain after I close the app** so that **I do not re-import the same folders every session**.

### Secondary — First-time user

- As a **new user**, I want **the orchestrator to look the same as today when I have no projects** so that **I am not distracted by empty navigation chrome before I understand the product**.

### Edge cases

- As a **user**, I want **canceling the folder picker to leave me on the current screen without an error message** so that **accidental cancellation is not treated as a failure**.
- As a **user**, I want **a clear message if folder selection fails** (permissions, system error) so that **I know what went wrong and can retry**.

## Core Features

### F1 — Local folder import

**What:** User selects a single directory from the native filesystem picker.

**Why:** Registers the project root that future agents will use.

**Behavior:**

- Import can be started from:
  - **Import project** in the top bar (existing navigation to source selection, then local path), and
  - **Select local** on the import source-selection screen.
- Only **directories** are valid selections (not individual files).
- On success:
  - Display name = folder name (last segment of the path).
  - Store absolute path for future file access.
  - Assign stable identity per folder path (same path = same project, not a duplicate row).
  - Re-importing an existing path moves that project to the top of the recent list and updates its recency.
  - Navigate user back to the main orchestrator view.
- On cancel: no toast or error; user stays on the current screen.
- On failure: user-visible message in Brazilian Portuguese (product language).

**Out of scope:** Git clone, cloud drives, zip extraction, multi-folder batch import.

### F2 — Recent Projects sidebar

**What:** Left sidebar on the orchestrator screen listing imported projects.

**Why:** Supports multi-repo tech leads who need persistent, visible context.

**Behavior:**

- Sidebar is **hidden** when zero projects exist (full-width empty state unchanged).
- Sidebar is **always visible** when one or more projects exist.
- Section title: **Projetos recentes** (PT-BR, centralized copy).
- Show **up to 10** projects, most recent first.
- Each row shows the project **display name**; long names truncate with ellipsis; full path available on hover/tooltip where the design system allows.
- Clicking a row sets that project as **active** (distinct visual state).
- Clicking does **not** open a file tree, editor, or agent session in MVP.

**Out of scope:** Remove/pin/favorite actions, search/filter, drag-and-drop reorder.

### F3 — Session persistence

**What:** Recent projects and active selection survive app restart.

**Why:** Tech leads should not re-register repos daily.

**Behavior:**

- Recent list restored on launch (respecting 10-item cap and sort order).
- Active project: restore last selected project if still in the list; otherwise no active highlight until user selects one.

**Out of scope:** Sync across devices, team-shared project lists, cloud backup.

## User Experience

### Primary flow — First import

1. User lands on orchestrator empty state (no sidebar).
2. User taps **Import project** → source selection → **Select local**.
3. Native folder picker opens.
4. User chooses a repository folder and confirms.
5. User returns to orchestrator; sidebar appears with one project; that project is **active**.
6. Main content area remains the existing empty/welcome body (no workspace UI yet).

### Primary flow — Switch active project

1. User has two or more projects in the sidebar.
2. User clicks another project name.
3. Active highlight moves to the clicked project; no navigation away from orchestrator.

### Primary flow — Re-import same folder

1. User imports a project already in the list via either entry point.
2. Existing entry moves to top; recency updates; no duplicate row.

### Primary flow — Return visit

1. User reopens Pulse.AI.
2. Sidebar shows previous projects (≤10).
3. Last active project is highlighted if still present.

### Discoverability

- Import remains available from the top bar even when the sidebar is visible.
- Remote/Git import options remain visible but marked or behaving as **coming soon** (unchanged from today).

### Accessibility

- Sidebar items must be keyboard-focusable and activatable.
- Active state must not rely on color alone (weight, border, or icon in addition to color per design system patterns).

## High-Level Technical Constraints

- **Platform:** Desktop only for folder picker in MVP (macOS, Windows, Linux) — consistent with Pulse.AI desktop positioning.
- **Language:** All user-facing strings in **Brazilian Portuguese**; centralized in feature string files (existing project rule).
- **Privacy:** Project paths stay on the user's machine; no upload or telemetry of folder contents in this release.
- **Performance:** Recent list should render instantly on orchestrator load for ≤10 items (user-perceived, no loading spinner required).
- **Future compatibility:** Each stored project must retain **absolute path** and **display name** so a later agent phase can bind tools to the project root without data migration.

## Non-Goals (Out of Scope)

| Item | Notes |
|------|--------|
| LLM / agent execution | No API calls, prompts, or autonomous file edits |
| Workspace UI | No file tree, editor, or diff view |
| Git / remote clone | Placeholder only; no clone or auth |
| File read/write | No scanning or indexing of repository contents |
| Project removal / favorites | Deferred; cap handles list size |
| Multi-root workspace | One folder = one project in MVP |
| Mobile / web folder picker | Desktop only |
| Sharing recent lists across users or machines | Local persistence only |

## Phased Rollout Plan

### MVP (Phase 1) — This PRD

**Includes:** F1, F2, F3 as specified; dual import entry points; active selection; 10-project cap; contextual sidebar.

**Success criteria to proceed to Phase 2:**

- ≥80% of internal dogfood users complete import + see sidebar without support docs.
- Zero data loss of recent list across restart in QA matrix (three desktop OSes).
- No P0/P1 bugs on import cancel, duplicate path, or active-state persistence.

### Phase 2 — Workspace shell

- Open selected project: file tree or project dashboard bound to active project root.
- Optional: remove from recents, pin favorite.
- Clearer copy distinguishing "registered" vs "opened."

### Phase 3 — Agentic orchestration

- LLM agents with read/write/create scoped to active project's absolute path.
- Permissions model (read-only vs read-write) per project.
- Per-project instructions / conventions (similar to folder-scoped rules in coding assistants).

## Success Metrics

| Metric | Target (MVP) | Measurement |
|--------|----------------|-------------|
| Import completion rate | ≥90% of attempts that open the picker result in a saved project | In-app funnel (picker opened → saved) |
| Time to first import | Median &lt;60s from orchestrator landing | Session timing |
| Return-user recognition | ≥70% of week-2 users have ≥2 projects in recents OR re-import same path | Persisted project count |
| Active-selection usage | ≥50% of multi-project users change active project ≥1× per session | Selection events |
| Support burden | 0 doc articles required for "where did my project go" in dogfood | Support tickets |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Users expect clicking a project to "open" code | PRD and in-product copy frame sidebar as **context selection** until Phase 2; no faux loading states |
| Ten-project cap frustrates power users | Monitor metrics; Phase 2 add pin/remove or expanded list |
| Path invalid after folder moved/deleted on disk | MVP: show name anyway; Phase 2 validate path on select and surface "folder not found" |
| Confusion between Import (top bar) and active project | Keep import always available; active state only affects highlight |
| Low adoption if remote import looks equally prominent | Maintain "coming soon" on remote card; dogfood focuses on local path |

## Architecture Decision Records

- [ADR-001: Contextual Recent Projects Sidebar with Active Selection](adrs/adr-001.md) — Sidebar appears only when projects exist; up to 10 recents; active highlight on click; re-import dedupes by path and promotes to top.

## Open Questions

1. Should the top-bar **Import project** button skip the source-selection screen and open the folder picker directly when the user has already imported at least once? (Deferred — current decision keeps both paths through source selection for B entry point consistency.)
2. What exact visual treatment denotes **active** vs hover? (Design / TechSpec — must meet non-color-only accessibility.)
3. When the active project's folder is missing on disk, should MVP block selection or allow selection with a warning? (Recommend warning in Phase 2; MVP silent.)
