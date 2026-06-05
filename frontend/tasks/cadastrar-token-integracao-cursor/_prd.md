# PRD: Register Cursor Integration Token

## Overview

Pulse orchestrates PRD workflows by delegating agent runs to Cursor Cloud Agents. Today the product can detect missing or invalid credentials and block PRD execution, but admins have no in-app path to register, validate, rotate, or remove the API key. This feature closes that gap so a technical lead or workspace admin can configure Cursor once and unblock the team’s PRD agent runs.

**Problem:** PRD runs cannot start without a valid Cursor Cloud Agents API key, yet configuration is only referenced in error copy (“open settings”) without a working settings experience.

**Audience:** Technical lead or admin responsible for workspace-level setup (not every developer entering their own key in MVP).

**Value:** Reduces time-to-first successful PRD run, prevents silent failure, and gives admins confidence that the stored key works before the team depends on it.

## Goals

- Enable an admin to register a Cursor Cloud Agents API key inside Pulse with clear success or failure feedback.
- Block PRD agent execution until a credential is stored and passes connection validation.
- Support credential lifecycle in MVP: save, replace (rotate), and remove (disconnect).
- Revalidate connection when the orchestrator loads and when the admin tests from settings.
- Keep guidance minimal: masked input, save/test/remove actions, and an external link to official Cursor documentation.

**Target outcomes (MVP):**

- Admins who follow the banner or settings entry can complete setup in one session without leaving Pulse except for the doc link.
- Zero PRD agent starts attempted while the connection status is “missing credential” or “unauthorized” without an obvious path to fix.

## User Stories

### Admin (primary)

- As an admin, I want to paste my Cursor Cloud Agents API key in Pulse so that PRD agent runs can authenticate on my behalf.
- As an admin, I want to test the key before leaving settings so that I know it is accepted before my team retries PRD workflows.
- As an admin, I want to replace an expired or rotated key so that PRD runs resume without reinstalling the app.
- As an admin, I want to remove the stored key so that Pulse stops using Cursor until I configure it again.
- As an admin, I want PRD runs blocked until a valid key exists so that users do not start workflows that cannot complete.
- As an admin, I want the connection banner to open the same configuration I reach from the settings icon so that I am not confused by two different flows.

### Developer (secondary, MVP)

- As a developer using Pulse, I want to see that Cursor is disconnected and why so that I can ask my admin to fix credentials instead of debugging agent failures.
- As a developer, I want to be prevented from starting a PRD agent when credentials are missing so that I do not lose context on a doomed run.

## Core Features

### 1. Cursor integration settings surface (MVP)

A dedicated configuration area for Cursor integration, reachable from:

- The existing settings control in the orchestrator top bar.
- The “open settings” action on the Cursor connection banner when disconnected or invalid.

**Behavior:**

- Single shared surface for both entry points (hybrid light).
- Masked secret input (never show full key after save).
- Actions: **Test connection**, **Save**, **Remove / disconnect**.
- Status indicator after test or save: connected, invalid key, or unreachable (user-facing messages in PT-BR in product UI).
- Minimal guidance: short label, helper text, and link to official Cursor Cloud Agents / API key documentation (no in-app step-by-step wizard).

### 2. Credential validation on demand (MVP)

When the admin taps **Test connection** or **Save**, Pulse validates the key against Cursor (same outcome the user should expect for a working PRD run).

**Behavior:**

- Immediate feedback on the settings surface (success vs. invalid vs. network-type failure).
- Saving persists only after successful validation (or explicit product decision: save attempt triggers validation—admin must see failure reason if save is rejected).

### 3. Automatic revalidation on orchestrator load (MVP)

When the user opens the orchestrator workspace, Pulse re-runs connection preflight using the stored credential.

**Behavior:**

- Connected: no banner (or subtle connected state if product already exposes it).
- Missing / invalid / network: show existing remediation banner with CTA to the shared settings surface.

### 4. PRD execution gate (MVP)

PRD agent start actions remain disabled while connection status is not “connected.”

**Behavior:**

- Clear, actionable message pointing to settings or banner CTA.
- No queuing or “run anyway” escape hatch in MVP.

### 5. Credential removal (MVP)

Admin can clear the stored key from the same settings surface.

**Behavior:**

- After remove, connection status becomes disconnected; PRD gate applies; banner returns.

## User Experience

### Personas

| Persona | Goal in this feature |
|--------|----------------------|
| Admin | Configure and maintain one workspace Cursor API key |
| Developer | Understand blockers and escalate to admin |

### Primary flow — proactive setup

1. Admin opens Pulse orchestrator.
2. Admin opens settings (gear) → Cursor integration section.
3. Admin pastes API key from Cursor dashboard (external).
4. Admin taps **Test connection** → sees success or error with remediation hint.
5. Admin taps **Save** → key stored; status shows connected.
6. Admin returns to PRD workflow; agent start is enabled.

### Primary flow — reactive setup (blocked PRD)

1. Developer or admin attempts PRD agent start without a valid key.
2. UI blocks action; connection banner explains missing/invalid credential.
3. User taps **Open settings** on banner → same settings surface as gear.
4. Admin completes paste → test → save flow.
5. Preflight re-runs; banner clears; PRD start enabled.

### Secondary flow — rotate key

1. Admin opens settings from gear or banner.
2. Admin enters new key, tests, saves (replaces previous).
3. Old key is no longer used; no separate “version history” in MVP.

### Secondary flow — disconnect

1. Admin opens settings → **Remove**.
2. Confirmation step recommended to prevent accidental removal.
3. Credential cleared; banner shown; PRD blocked.

### UX and accessibility

- All user-visible copy in PT-BR via centralized strings (project standard).
- Secret field: password-style masking, no copy-to-clipboard of stored secret.
- Keyboard-accessible actions; semantics labels for banner, form, and status.
- Errors distinguish: missing key, rejected key (401-class), and connectivity issues so admins know whether to rotate vs. check network/docs.

### Discoverability

- No standalone onboarding wizard in MVP.
- Banner + gear + blocked PRD affordances are the discovery channels.

## High-Level Technical Constraints

- Credential must be stored only on the local device using platform-appropriate secure storage (already a project dependency pattern).
- The full API key must never appear in logs, analytics, or UI after initial entry.
- Validation must reflect real Cursor Cloud Agents acceptance (same check used before PRD runs).
- Product depends on Cursor Cloud Agents API availability and admin obtaining the correct key type from Cursor dashboard (Cloud Agents / Integrations—not generic team keys that do not work for agents).
- Desktop-first orchestrator; web constraints out of scope unless already supported elsewhere.

## Non-Goals (Out of Scope)

- Per-developer OAuth or personal Cursor IDE session import.
- In-app illustrated wizard for dashboard navigation (deferred; MVP is link to official docs only).
- Team-wide credential sync across machines or central admin console in Pulse.
- Service account vs. user key selection UI (admin chooses key type outside Pulse).
- Billing, usage quotas, or Cursor plan management inside Pulse.
- Automatic key rotation reminders or expiry detection beyond validation failures.
- MCP server token configuration (separate product surface).

## Phased Rollout Plan

### MVP (Phase 1)

- Shared Cursor integration settings surface (gear + banner CTA).
- Masked input; test, save, remove.
- Validation on test/save; auto preflight on orchestrator load.
- PRD agent start gate when not connected.
- Minimal doc link; PT-BR strings.

**Exit criteria:** Admin can go from fresh install to successful test + PRD start in one flow; developers see consistent block + banner when credential missing.

### Phase 2

- Richer in-app guidance (step-by-step PT-BR, common mistake callouts).
- Optional “last validated at” timestamp for admins.
- Clearer connected indicator in top bar or workflow chrome.

### Phase 3

- Multi-tenant / team credential policies if product expands beyond single-machine admin setup.
- Audit log of credential changes (who rotated, when) for enterprise.

## Success Metrics

| Metric | Target (MVP direction) |
|--------|-------------------------|
| Time to first successful connection after install | Median &lt; 5 minutes for admin following doc link |
| PRD starts blocked by missing credential after setup complete | Near zero among admins who completed save + test |
| Support tickets “PRD won’t start / Cursor” citing wrong key type | Decrease vs. baseline once validation + doc link live |
| Credential removal → re-register completion rate | Admins can recover without reinstall |

**Qualitative:** Admins report they know where to fix Cursor issues without asking engineering.

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Admin creates wrong API key in Cursor dashboard | Immediate validation failure + link to official docs; existing unauthorized remediation copy |
| Admin assumes Team Settings key works for Cloud Agents | Doc link; optional Phase 2 in-app callouts |
| Developers blocked with no admin available | Banner copy states admin action required; no fake “connected” state |
| Key leaked via shoulder-surfing | Masked field; no reveal-after-save |
| Cursor API outage blocks all PRD work | Distinguish network vs. invalid key in messaging; retry via test button |

## Architecture Decision Records

- [ADR-001: Hybrid Cursor Credential Entry via Shared Settings Surface](adrs/adr-001.md) — Single settings surface opened from gear and connection banner; no onboarding wizard; PRD blocked until valid.

## Open Questions

- Should **Save** be allowed before a successful **Test**, or must test always pass first? (Recommend: test required on save for MVP consistency with user choice C.)
- Is a confirmation dialog required for **Remove**, and what is the exact PT-BR copy?
- Should the settings surface be a full page route, modal sheet, or side panel? (Product preference; not prescribed in this PRD.)
- After successful setup, should the orchestrator show a persistent “connected” indicator or only hide the banner?
- Enterprise service account keys: any copy difference for admins on Teams vs. individual accounts?
