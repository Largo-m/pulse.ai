---
status: pending
title: PrdWorkflowCubit and live stream panel
type: frontend
complexity: medium
dependencies:
  - task_08
  - task_09
---

# Task 10: PrdWorkflowCubit and live stream panel

**Phase:** PR-5 — Workspace PRD (UI)

## Overview

Adiciona `PrdWorkflowCubit` que gerencia fase PRD, run ativa, subscrição de stream e cancelamento; widgets de painel de stream com buffer limitado e copy PT-BR. Ainda sem alterar submit do orchestrator (task_13).

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `PrdWorkflowCubit` with states covering not started, running, pending approval, approved, failed, cancelled per PRD phase status
- MUST subscribe to `watchRun` stream and dispatch append use case or receive events via injected stream facade
- MUST dispose subscription on cancel/complete/cubit close
- MUST use design system tokens only (`workflow*` dimensions/radii/insets) — no magic numbers
- MUST use `OrchestratorStrings` or new `PrdWorkflowStrings` for all user-visible copy (PT-BR)
- MUST NOT use `setState` in widgets
- MUST provide cancel action calling cancel use case
- SHOULD cap UI buffer per TechSpec known risks (constant max lines)
</requirements>

## Subtasks
- [ ] 10.1 Define cubit state/events and wire use cases from task_08/09
- [ ] 10.2 Build stream panel widget(s) with semantics labels for run status
- [ ] 10.3 Build status chips and user-action-required highlights
- [ ] 10.4 Add `bloc_test` coverage for running→completed and cancel transitions
- [ ] 10.5 Add strings + `orchestrator_strings_test` or dedicated strings test

## Implementation Details

See TechSpec **Component Overview** (`PrdWorkflowCubit`, stream panel) and **Monitoring** (`streamLagMs` debug field optional).

Reuse `WorkflowPhaseStepper` with `WorkflowPhase.prd` from `lib/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart`.

### Relevant Files
- `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` — new
- `lib/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart` — reuse
- `lib/shared/theme/tokens/pulse_dimensions.dart` — workflow tokens
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — extend

### Dependent Files
- `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` — task_12 composes stream panel

### Related ADRs
- [ADR-001: Native Pulse Cockpit](../adrs/adr-001.md) — streaming primary UX
- [ADR-002: PRD-Only MVP](../adrs/adr-002.md) — PRD phase focus

## Deliverables
- `PrdWorkflowCubit` + state types
- Stream panel widget(s)
- PT-BR strings for stream/status/cancel
- `bloc_test` suite with **≥80% coverage** on cubit **(REQUIRED)**

## Tests
- Unit tests:
  - [ ] Cubit: start run emits `running` and appends first stream line to state
  - [ ] Cubit: completed run emits `pendingApproval` and stops subscription
  - [ ] Cubit: cancel transitions to `cancelled` and clears active subscription
  - [ ] Cubit: failed run surfaces failure message key without secret substrings
  - [ ] Strings test: all new stream keys non-empty PT-BR
- Integration tests:
  - [ ] N/A — widget tests deferred per project workflow
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on cubit
- Stream UI renderable in isolation (host widget test or manual QA note in PR)
- No `setState` under new widgets
