# Product Requirements Document — Agentic Governance Command Center (Orchestrator Empty State)

## Overview

The Agentic Governance Command Center introduces the primary workspace for platform engineers who own repositories and will configure agentic orchestration. The Orchestrator empty state is the first-run experience when no workspace is active: it orients users to the operating environment and surfaces the two intended entry paths (local project and Git remote), aligned with the Stitch reference design for Agentic Governance Command Center.

This milestone delivers presentation and layout only: users can explore the shell and understand next actions while integrations remain deferred.

## Goals

- Establish immediate recognition of the command center paradigm (system context, standby readiness, dual onboarding paths).
- Preserve design parity with the approved Stitch screen for stakeholder review and iterative copy refinement.
- Provide a clear, honest placeholder experience for all primary actions until backend capabilities ship.
- De-risk later integration work by locking navigation hierarchy and terminology early.

## User Stories

- As a platform engineer, I want to see a structured command center shell so that I trust the product direction before connecting systems.
- As a repository owner, I want obvious paths for local workspace setup and Git-based sync so that I know where to start when integrations arrive.
- As a first-time visitor, I want the empty state to explain why the surface is idle so that I do not interpret standby as an error.
- As a stakeholder reviewing design, I want the delivered UI to match the reference layout so that feedback targets copy and flow rather than basic composition.

## Core Features

- **Global application chrome**: Branded top bar with workspace navigation affordance, import entry point, and account-related shortcuts (presentation only).
- **Context strip**: Breadcrumb-style system path and a standby indicator reflecting initialization without live workload.
- **Centered empty state narrative**: Icon, headline, and concise supporting text describing the orchestration environment status.
- **Dual onboarding cards**: Distinct cards for local project initialization and remote Git connection, each with title, description, and primary button (placeholder feedback only).
- **Persistent shell framing**: Bottom activity bar region and consistent dark visual system matching the reference palette.

## User Experience

- Users land in the Orchestrator empty state as the default command center view in the desktop shell.
- The sidebar retains access to a simple home view while promoting discoverability of the command center entry.
- Every actionable control that lacks a backend responds with a single, consistent non-destructive message (for example, a short “coming soon” acknowledgment) so users are not left guessing.
- Layout adapts from a single-column card stack to a two-column grid at wider widths to mirror the reference responsive behavior.
- Copy should remain scannable: short headline, two-sentence body, card descriptions under three lines where possible.

## High-Level Technical Constraints

- Must coexist with the existing Flutter desktop shell (custom title bar and sidebar navigation) without breaking window management behaviors.
- Visual system should remain self-contained to this surface where global theming differs, avoiding unintended regressions to other routes.

## Non-Goals (Out of Scope)

- Real directory mounting, filesystem browsing, or validation of local agent configuration.
- Git clone, fetch, authentication, or provider-specific flows.
- Live orchestration telemetry, agent lists, traces, or policy enforcement views.
- Multi-user collaboration, permissions modeling, or audit logging.

## Phased Rollout Plan

### MVP (Phase 1)

- Full shell and empty state presentation with placeholder feedback on interactions.
- Success: stakeholders sign off on layout, hierarchy, and copy direction; internal demos run without navigation dead-ends.

### Phase 2

- Implement local project initialization flow end-to-end with clear success and failure handling.
- Success: users can mount a valid workspace and transition to a populated orchestrator canvas.

### Phase 3

- Add Git remote synchronization and provider-specific guidance.
- Success: users can connect a remote, sync, and see workspace state reflected in downstream orchestrator views.

## Success Metrics

- Qualitative design sign-off against the Stitch reference for the empty state frame.
- Reduction in clarification questions during internal demos about “what happens next” compared to the prior placeholder home screen.
- Task completion proxy: users trigger at least one card or top-bar action and receive placeholder feedback (instrumentation optional for later).

## Risks and Mitigations

- **Misinterpretation as broken product**: mitigate with explicit, neutral placeholder language and consistent snackbar or banner behavior.
- **Copy drift from product positioning**: mitigate by aligning headline and body text with `pulse.ia` positioning in a future copy pass without blocking layout approval.
- **Scope creep into integrations**: mitigate by treating any backend work as a separate initiative gated on TechSpec approval.

## Architecture Decision Records

- [ADR-001: UI-only MVP with full shell parity and placeholder CTAs](adrs/adr-001.md) — Accept full-layout parity with non-destructive placeholder interactions instead of disabled CTAs or phased chrome.

## Open Questions

- Whether marketing prefers replacing “Neural Shell Systems” with `pulse.ia`-native naming before external demos.
- Localization policy for placeholder strings currently shown in Portuguese inside the Flutter shell.
- Exact taxonomy for “Workspaces” versus future navigation labels once multiple modules exist.
