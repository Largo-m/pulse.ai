---
status: completed
title: Orchestrator shell wiring (slug, submit, sidebar, TechSpec gate)
type: frontend
complexity: medium
dependencies:
  - task_12
---

# Task 13: Orchestrator shell wiring (slug, submit, sidebar, TechSpec gate)

**Phase:** PR-6 — Integração no shell orchestrator

## Overview

Conecta o MVP PRD ao shell existente: campo slug no modal de inicialização, submit abre `WorkflowPrdWorkspace`, sidebar lista workflows por projeto, e workspace TechSpec permanece bloqueado até PRD `approved` para o slug.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST extend `InitializeAgentSubmitPayload` with `slug` (kebab-case) and pass through modal validation
- MUST change `InitializeAgentSubmitHandler` to open PRD workflow view instead of TechSpec-only view
- MUST add `prdWorkflow` (or equivalent) to `OrchestratorMainContentCubit` state enum alongside `welcome` and `techspecWorkflow`
- MUST call `CreateWorkflowUseCase` on submit before navigation/show workspace
- MUST populate `RecentProjectsSidebar` agents/workflows list via `ListWorkflowsByProjectUseCase` replacing empty stub
- MUST gate `WorkflowTechspecWorkspace` on `prdPhaseStatus == approved` for active slug; otherwise show PRD-required messaging PT-BR (ADR-002)
- MUST keep navigation via existing orchestrator shell — no new `RoutePaths` in MVP per TechSpec Impact Analysis
- MUST update/add tests for cubit state transitions, submit handler, and strings for slug validation errors
</requirements>

## Subtasks
- [x] 13.1 Add slug field + validation to `initialize_agent_modal.dart`
- [x] 13.2 Extend payload, submit handler, and main content cubit to PRD view
- [x] 13.3 Wire sidebar workflow list per active project UUID
- [x] 13.4 Implement TechSpec gate in `workflow_techspec_workspace.dart`
- [x] 13.5 Update `orchestrator_page.dart` body switch and tests

## Implementation Details

See TechSpec **Impact Analysis** table rows for `InitializeAgentSubmitHandler`, `OrchestratorMainContentCubit`, `recent_projects_sidebar.dart`, `initialize_agent_modal.dart`, `workflow_techspec_workspace.dart`.

Current handler only calls `showTechspecWorkflow`:

```4:10:lib/features/orchestrator/presentation/initialize_agent_submit_handler.dart
abstract final class InitializeAgentSubmitHandler {
  static void handle(
    OrchestratorMainContentCubit mainContentCubit,
    InitializeAgentSubmitPayload payload,
  ) {
    mainContentCubit.showTechspecWorkflow(payload);
  }
}
```

### Relevant Files
- `lib/features/orchestrator/presentation/initialize_agent_submit_handler.dart` — route to PRD
- `lib/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart` — new view state
- `lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart` — slug input
- `lib/features/orchestrator/presentation/widgets/recent_projects_sidebar.dart` — workflow list
- `lib/features/orchestrator/presentation/widgets/workflow_techspec_workspace.dart` — approval gate
- `lib/features/orchestrator/presentation/pages/orchestrator_page.dart` — body composition
- `test/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit_test.dart` — extend or create

### Dependent Files
- `test/app/router/shell_navigator_routes_test.dart` — unchanged if no new routes

### Related ADRs
- [ADR-002: PRD-Only MVP](../adrs/adr-002.md) — TechSpec locked until PRD approved
- [ADR-003: Pulse-Internal Artifact Storage](../adrs/adr-003.md) — slug in sidebar

## Deliverables
- End-to-end shell wiring from modal submit to `WorkflowPrdWorkspace`
- Sidebar workflow entries per project
- TechSpec gate UI copy PT-BR
- Unit/bloc tests for main content cubit and submit handler
- Unit tests with **≥80% coverage** on changed presentation logic **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `OrchestratorMainContentCubit.showPrdWorkflow` emits state with payload slug and projectId
  - [x] Submit handler calls `showPrdWorkflow` not `showTechspecWorkflow` after task completion
  - [x] Modal validation: empty slug prevents submit (cubit/handler not invoked — test validation helper)
  - [x] Modal validation: invalid slug format shows PT-BR error string key
  - [x] TechSpec gate helper: `prdPhaseStatus` not approved → gate active; approved → coming-soon/placeholder only
  - [x] Sidebar: when list use case returns two workflows, sidebar model contains two entries (via cubit or mapper test)
- Integration tests:
  - [x] N/A
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on modified presentation units
- `flutter analyze` and `dart format .` clean
- MVP user flow: modal → PRD workspace → stream → review → approve; TechSpec blocked until approved
- PR-6 closes feature initiative for merge to main
