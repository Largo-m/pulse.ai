# PRD: Cursor PRD Specialist Agent

## Overview

Pulse.AI is an agentic orchestration desktop application for tech leads and engineering managers who coordinate AI-assisted delivery across local Git workspaces. The orchestrator UI already surfaces workflow phases (PRD, TechSpec, Tasks, QA, Review), but **PRD creation is not yet executable** from Pulse—users must leave the app to draft requirements elsewhere.

This initiative delivers **Cursor integration for the PRD phase only**: a requirements specialist agent runs inside Pulse, streams progress live, produces a draft PRD stored **inside Pulse** (not in the imported repository), and requires **explicit user approval** before the workflow is considered ready for downstream phases (TechSpec and beyond—out of scope here).

**Primary persona:** Tech lead / engineering manager who drafts and approves requirements before the team proceeds.

**Secondary persona:** Senior developer initiating a feature workflow on an imported local project.

## Goals

1. Enable a tech lead to **create and approve a PRD** from Pulse using a Cursor specialist agent, without switching tools for this phase.
2. Provide **live visibility** into PRD agent execution inside Pulse.
3. Persist approved PRD content and related ADRs **in Pulse storage**, keyed by **mapped project** and **workflow slug**.
4. Reduce **time from feature idea to approved PRD** versus the current manual baseline.

## Core Concepts

### Mapped project

An imported local project registered in Pulse with a **stable internal project identity**. All workflows and artifacts for that codebase are grouped under this project, independent of display name or path changes on disk.

### Workflow slug

A user-chosen identifier for one feature or initiative within a mapped project (e.g. `cursor-workflow-agents`). Together with the project id, it uniquely identifies a workflow’s artifact bundle inside Pulse.

### Pulse artifact store

Pulse-owned storage holding all workflow outputs. Layout is logically:

- **Project** → **Slug** → artifacts (`prd.md`, `adrs/`, run history, approval state).

Users never need to open the filesystem to find draft or approved PRDs for orchestration work.

## User Stories

### Tech lead / EM (primary)

- As a tech lead, I want to **start a PRD workflow** on a mapped project and branch so that requirements work is anchored to the correct codebase context.
- As a tech lead, I want to **provide an initial feature idea or directive** so that the PRD agent has enough context to draft requirements.
- As a tech lead, I want to **run the PRD specialist agent** from Pulse so that a draft PRD is generated and saved **inside Pulse** under the right project and slug.
- As a tech lead, I want to **watch a live stream** of the agent run so that I can spot misalignment early.
- As a tech lead, I want to **review the draft PRD in Pulse** and **approve or reject with feedback** so that only agreed requirements are marked final.
- As a tech lead, I want to **re-run the PRD agent** after rejection so that the artifact improves before I approve.
- As a tech lead, I want to **switch between mapped projects** and see only the workflows and PRDs belonging to each project.

### Senior developer (secondary)

- As a developer, I want **clear failure reasons** when the PRD agent fails so that I can fix setup issues (Cursor connection, project access) and retry.
- As a developer, I want to **cancel an in-flight PRD run** if I selected the wrong project, branch, or directive.

## Core Features

### 1. PRD workflow initiation

- Create a workflow **slug** under a **mapped project**, with selected Git branch.
- Capture an optional **feature directive** used as input to the agent.
- Show PRD phase status: not started, running, draft ready for review, approved, failed.

### 2. Cursor PRD specialist agent execution

- Launch the **PRD specialist agent** from Pulse (business-focused requirements document; ADRs when applicable).
- Pass context: mapped project, branch, slug, directive, and repo signals Pulse can surface.
- Expose run states: **queued, running, completed, failed, cancelled**.

### 3. Live execution stream

- Display a **live stream** of PRD agent activity in the PRD workspace.
- Persist stream history **in Pulse** under the same project + slug for later audit.
- Highlight when **user action is required** (review draft, connection error).

### 4. PRD artifact review and approval

- Present the generated **PRD document** and **ADRs** from Pulse storage in a review-oriented view.
- Actions: **Approve**, **Reject with feedback** (triggers re-run with feedback), **Cancel run**.
- On approval, mark PRD as **approved** in Pulse; artifact remains under project + slug.
- Do **not** auto-start TechSpec or any later phase in this initiative.

### 5. Pulse artifact management

- All PRD-phase outputs live **only in Pulse**: PRD body, `adrs/`, approval metadata, run and stream history.
- Resolve artifacts by **mapped project id + slug**; no default write into the imported Git tree.
- Show artifact status: draft, pending approval, approved.
- Support listing workflows (slugs) per project from the orchestrator UI.

### 6. Cursor connection (user-facing)

- Guide the user to **connect Cursor** before the first PRD run; show status and remediation when disconnected.
- Never display secrets in UI, streams, or stored artifacts.

## User Experience

### Primary flow: idea to approved PRD

1. User selects a **mapped project** and branch.
2. User creates a workflow **slug** and enters a **feature directive**.
3. User starts **PRD agent** → live stream appears.
4. Agent completes → Pulse saves draft under **project + slug** → user **reviews PRD in app**.
5. User **approves** or **rejects with feedback** → on reject, user re-runs; on approve, PRD phase is complete in Pulse.
6. UI shows PRD **approved** for that slug; later phases remain unavailable until future initiatives ship.

### UX principles

- **PRD-only focus** in the workspace.
- **Pulse is the system of record** for PRD artifacts—no expectation that users look in the repo folder.
- **Approval is explicit**—agent completion does not equal approval.
- **Streaming is primary** for monitoring.
- UI copy in **PT-BR**; PRD document language follows team convention.

### Onboarding

- Checklist: map/import project → connect Cursor → create slug → enter directive → run PRD agent → approve in Pulse.

### Accessibility

- Stream, approve, and reject controls are keyboard-accessible with screen-reader labels for run status.

## High-Level Technical Constraints

- **Local Git projects only** for execution context; remote clone out of scope.
- **Cursor access required** to run the PRD agent.
- **Pulse-internal storage** for all artifacts, partitioned by mapped project and slug.
- **Desktop app**; web out of scope.
- **Secrets** must not appear in streams, logs, or stored artifacts.
- **Stable project identity** must survive re-import or path changes where possible.

## Non-Goals (Out of Scope)

- Writing workflow artifacts into the **imported repository** (including hidden vendor folders in the Git tree).
- **Export/sync to Git** (may be considered later; not MVP).
- **TechSpec, Tasks, task execution, QA, Review** phases and their agents.
- **Automatic advancement** to TechSpec after PRD approval.
- Replacing **Cursor IDE** for general coding.
- **Remote repository clone**, custom agent builder, org billing/admin, non-Cursor runtimes.
- **Fully autonomous** PRD approval without human review.

## Phased Rollout Plan

### MVP (Phase 1) — this PRD

- Mapped project + slug workflows, Cursor PRD agent, live stream, Pulse-side persistence, in-app review/approve/reject/retry/cancel, ADRs stored under same slug, Cursor connect onboarding, workflow list per project.

**Success criteria:**

- Median **PRD cycle time** (run start → approval) decreases ≥20% vs. manual baseline.
- ≥85% of started PRD workflows reach **approved** without abandonment.
- Pilot users produce approved PRDs without leaving Pulse for storage or review.

### Phase 2 (future)

- TechSpec specialist agent with the same Pulse storage pattern (project + slug).
- Optional export of approved artifacts to files or Git.
- Notification when PRD run completes.

### Phase 3+ (future)

- Remaining pipeline phases using the same project + slug artifact model inside Pulse.

## Success Metrics

| Metric | Definition | Target (pilot, 60 days post-MVP) |
| --- | --- | --- |
| PRD cycle time | Run start → PRD approved in Pulse | ≥20% reduction vs. manual baseline |
| PRD completion rate | Started workflows that reach approved | ≥85% |
| Rework rate | PRD runs needed before approval | Track; aim ≤35% |
| Time in Pulse for PRD | Self-reported % of PRD work in Pulse | ≥90% for pilot users |
| PRD agent failure rate | Failed runs / total runs | ≤10% |
| Artifact discoverability | Users find PRD by project + slug without filesystem search | ≥95% success in pilot tasks |

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Low trust in generated PRD | Mandatory approval; reject-with-feedback; visible stream |
| Vague directive produces weak PRD | Minimum directive quality before run |
| Cursor access blocks teams | Preflight connection status |
| Users expect PRD files in Git | Onboarding: artifacts live in Pulse; export deferred |
| Project re-import breaks artifact linkage | Stable internal project id (see ADR-003) |
| Slug collision within project | Validate uniqueness at creation |

## Architecture Decision Records

- [ADR-001: Native Pulse Cockpit for Cursor Workflow Orchestration](adrs/adr-001.md) — Pulse orchestrates runs, approval, and streaming.
- [ADR-002: PRD-Only MVP Scope](adrs/adr-002.md) — PRD phase first; other phases later.
- [ADR-003: Pulse-Internal Artifact Storage by Project and Slug](adrs/adr-003.md) — All artifacts inside Pulse, keyed by mapped project + slug; not in the Git repo.

## Open Questions

1. What is the **manual baseline** for PRD cycle time on pilot projects?
2. Is the PRD specialist agent **fixed** or selectable per project?
3. Who provides **Cursor credentials** in team pilots—individual or shared org account?
4. On **reject with feedback**, does re-run start automatically or only after “Run again”?
5. Should users **edit the PRD in Pulse** before approval, or only via agent re-run?
6. Should MVP include **read-only preview of repo context** in the review screen, without storing PRD in the repo?
