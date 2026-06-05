# PRD: Workflow Session Continuity (PRD Agent)

## Overview

Pulse.ai users run multi-step PRD workflows driven by an external agent. When they navigate away (another workflow, welcome screen) or close and reopen the application, the workflow workspace often appears empty: phase status may update, but terminal logs, user–agent conversation, and artifact presentation do not reflect what already happened.

This feature restores a **complete, trustworthy picture of the last finished agent session** when the user returns to a PRD workflow. It targets operators and builders who manage several workflows and need continuity without re-reading disk folders or guessing agent progress.

## Goals

- Eliminate “blank workflow” anxiety after leave-and-return (in-app or cold start).
- Reduce time-to-context when reopening a workflow from the sidebar to under 5 seconds perceived load for typical histories.
- Align in-app continuity with artifacts already written under `.compozy/tasks/<slug>/`.
- Ship PRD-phase continuity in MVP; establish the same user contract for TechSpec in a follow-on phase.

## User Stories

### Primary — Workflow owner

- As a **workflow owner**, I want to see the full terminal log from my last **completed** PRD agent run when I reopen the workflow, so that I can audit what the agent did without starting a new run.
- As a **workflow owner**, I want to see my prompts and the agent’s conversational responses from that same run, so that I remember what I asked and what was answered.
- As a **workflow owner**, I want artifact cards (PRD draft, ADRs, and related outputs) for that run to appear in the workflow UI, so that I can continue review or approval without hunting the filesystem.

### Primary — Returning after interruption

- As a **workflow owner**, I want the same restored view after closing Pulse.ai and reopening it, so that continuity does not depend on keeping the app open.

### Active run edge case

- As a **workflow owner**, when I return while a run is still in progress, I want a clear **in progress** indicator without partial logs or conversation, so that I am not misled by incomplete history.

### Secondary — Multi-workflow user

- As a **user juggling multiple workflows**, I want each workflow to restore its own last completed session independently, so that switching projects does not mix histories.

## Core Features

### 1. Automatic restore on workflow open

When the user opens a PRD workflow (sidebar or equivalent entry):

- Resolve the **most recent finalized run** for that workflow (completed, failed, or cancelled).
- Populate the workflow workspace with that run’s terminal log lines in chronological order.
- Populate the conversation transcript (user prompts and agent messages) tied to the same run.
- Show artifact cards linked to that run / workflow slug (PRD markdown, ADRs, and other outputs the product already surfaces).

All three surfaces must refer to the **same run** so the story is coherent.

### 2. Cross-session persistence

Restoration must work identically for:

- Navigating away within a single app session and returning.
- Fully quitting and relaunching Pulse.ai.

### 3. In-progress run presentation

If the latest run is still active:

- Do **not** replay partial stream logs or conversation.
- Show an explicit in-progress state (copy and visual treatment defined in UX).
- On transition to a terminal status, the next open (or explicit refresh behavior if product adds one) uses that run as the restorable “last completed” session per ADR-001.

### 4. Phase scope (MVP vs later)

- **MVP**: PRD workflow phase only.
- **Later**: TechSpec workflow with the same restore contract (logs, conversation, artifacts for last finalized run).

### 5. Explicit non-feature for MVP

- No run timeline picker or browsing of older finalized runs (deferred).
- No live reconnect/stream catch-up for active runs (deferred).

## User Experience

### Happy path

1. User starts or continues a PRD agent run; logs stream; user sends prompts; artifacts appear.
2. Run reaches a terminal state.
3. User navigates to welcome or another workflow—or closes the app.
4. User reopens the same workflow from the sidebar.
5. Workspace loads with scrollable terminal log, conversation thread, and artifact cards from step 2—no empty panel.

### In-progress path

1. User leaves while run is active.
2. User returns; workspace shows in-progress affordance only.
3. When run finishes, user opens workflow again and receives full restore per happy path.

### Error / empty states

- **No finalized run yet**: Show onboarding-aligned empty state (not started / awaiting first completion)—distinct from “failed to load history.”
- **Restore failure**: User-visible message in PT-BR explaining that history could not be loaded; offer retry; do not silently show empty logs.
- **Run finalized externally while away**: On open, detect terminal status and restore if finalized; otherwise keep in-progress rules.

### Accessibility and discoverability

- Restored content is scrollable and does not steal focus from primary actions (review, approve, start new run).
- In-progress vs restored-complete states must be distinguishable by text and iconography, not color alone.

## High-Level Technical Constraints

- Restoration must remain consistent with workflow identity (`projectId` + `slug`) and run records the product already persists.
- Restored artifact cards must reflect files the user can already access under the workflow’s Compozy task directory; no duplicate source of truth that can diverge silently.
- User-facing errors and labels remain **PT-BR** per product standards.
- Perceived restore time for typical histories should target **≤ 5 seconds** on desktop; very large histories may degrade gracefully (document in Open Questions if hard cap needed).

## Non-Goals (Out of Scope)

- Run timeline UI to select older finalized runs.
- Live streaming catch-up when returning to an active run.
- TechSpec workflow restore in MVP (Phase 2+).
- Export/share of conversation or logs.
- Cross-machine sync of session history (single device / local workspace assumption unless product defines cloud later).
- Rewriting or editing historical log lines in the UI.

## Phased Rollout Plan

### MVP (Phase 1) — PRD last-session restore

- Auto-restore last finalized run: logs, conversation, artifacts.
- In-progress-only badge when latest run is active.
- Works for in-app navigation and app restart.
- **Success criteria**: ≥ 90% of internal dogfood returns show non-empty history for workflows with at least one finalized run; zero conflating histories across two workflows in QA scenarios.

### Phase 2 — TechSpec parity

- Same restore behavior for TechSpec workspace.
- Reuse PRD patterns; validate artifact types specific to TechSpec.
- **Success criteria**: TechSpec reopen matches PRD satisfaction score in user interviews.

### Phase 3 — Run history (optional)

- Timeline or list to open older finalized runs.
- Compare iterations and superseded runs.
- **Success criteria**: Users with >3 runs per workflow adopt timeline without increasing median time-to-context on default open.

## Success Metrics

| Metric | Target |
|--------|--------|
| Workflows with ≥1 finalized run that show non-empty log + conversation on reopen | ≥ 95% in QA matrix |
| Median perceived time-to-first-log-line visible | ≤ 5 s (desktop, typical history) |
| Support tickets / feedback mentioning “lost agent history” | ↓ 80% within 30 days of launch |
| User task success: “find what the agent last did without new run” | ≥ 85% in moderated tests (n ≥ 8) |
| Incorrect run binding (logs from run A, artifacts from run B) | 0 critical defects in release QA |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Users expect partial logs during active runs | Clear in-progress copy; document in release notes |
| Large histories slow reopen | Measure load times; cap or paginate in Phase 3 if needed |
| Stale “in progress” after agent finished offline | Refresh run status on every workflow open |
| Artifact card shows file user deleted on disk | Show missing-artifact state; link to path only if policy allows |
| Confusion between draft review UI and restored conversation | Visual separation between review editor and agent transcript |

## Architecture Decision Records

- [ADR-001: Last Completed Session Auto-Restore](adrs/adr-001.md) — Auto-rehydrate the latest finalized run; in-progress runs show status only; PRD MVP first.

## Open Questions

- Should the user see a lightweight “Restored from run on &lt;date&gt;” banner for trust, or is implicit restore enough?
- Maximum log/conversation size before pagination or truncation—and whether truncation is acceptable for MVP.
- If the latest finalized run **failed**, should conversation still restore in full or collapse to error summary only?
- When a new run starts, should the UI immediately clear the previous restored view or keep it until the new run completes?
