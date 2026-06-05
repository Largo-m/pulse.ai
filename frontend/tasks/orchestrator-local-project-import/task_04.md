---
status: completed
title: OrchestratorPage, sidebar UI, router, and strings
type: frontend
complexity: high
dependencies:
  - task_03
---

# Task 4: OrchestratorPage, sidebar UI, router, and strings

## Overview

Substitui `OrchestratorEmptyPage` por `OrchestratorPage` na rota existente, adiciona sidebar contextual de projetos recentes com seleção ativa, tokens de layout no design system e copy PT-BR centralizada. Empty state permanece inalterado quando não há projetos (PRD F2, ADR-001).

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST rename/replace `OrchestratorEmptyPage` with `OrchestratorPage` on unchanged `RoutePaths.orchestrator` (ADR-005)
- MUST use conditional `Row`: sidebar only when `projects.isNotEmpty`; full-width empty body when zero projects
- MUST create `RecentProjectsSidebar` and `RecentProjectListTile` consuming `RecentProjectsCubit` via `BlocBuilder` or equivalent
- MUST set active project on row tap via `RecentProjectsCubit.selectProject` without navigation or workspace UI (PRD F2)
- MUST apply active visual state using DS tokens only (border/weight + `PulseColors` accent); not color alone (PRD accessibility)
- MUST add sidebar width token to `PulseDimensions` before use in layout (no magic numbers)
- MUST add PT-BR strings to `OrchestratorStrings` (e.g. section title **Projetos recentes**, tooltips) — no literals in widgets
- MUST update `shell_navigator_routes.dart` and `shell_navigator_routes_test.dart` to build `OrchestratorPage`
- MUST NOT wire import flow or `ImportFlowCubit` in this task (task 05)
- MUST NOT use `setState` for hover/active UI — use `ValueNotifier`, `MouseHoverBuilder`, or cubit-driven state
</requirements>

## Subtasks
- [x] 4.1 Add `orchestratorSidebarWidth` (or equivalent) to `PulseDimensions` and unit test
- [x] 4.2 Implement `RecentProjectsSidebar` and `RecentProjectListTile` with DS tokens and a11y
- [x] 4.3 Implement `OrchestratorPage` layout and connect `RecentProjectsCubit`
- [x] 4.4 Update router builder and router tests; remove/rename `orchestrator_empty_page.dart`
- [x] 4.5 Extend `OrchestratorStrings` and string tests (PT-BR, non-empty)
- [x] 4.6 Run `dart format .` and `flutter analyze`

## Implementation Details

See TechSpec **System Architecture**, **Impact Analysis** (OrchestratorEmptyPage, ShellNavigatorRoutes, PulseDimensions, OrchestratorStrings), and **PRD Mapping** F2.

Existing chrome (`OrchestratorAppTopBar`, breadcrumb, bottom bar, empty state body) stays; only layout wrapper gains optional sidebar column.

### Relevant Files
- `lib/features/orchestrator/presentation/pages/orchestrator_empty_page.dart` — rename/replace to `orchestrator_page.dart`
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — sidebar copy
- `lib/app/router/shell_navigator_routes.dart` — route builder
- `lib/shared/theme/tokens/pulse_dimensions.dart` — new sidebar width token
- `lib/shared/ui/mouse_hover_builder.dart` — hover without `setState`
- `test/app/router/shell_navigator_routes_test.dart` — expects `OrchestratorEmptyPage` today
- `test/features/orchestrator/presentation/orchestrator_strings_test.dart` — extend for new keys

### Dependent Files
- `lib/features/orchestrator/presentation/widgets/orchestrator_empty_state_body.dart` — reused inside page when sidebar hidden
- `lib/main.dart` — cubit providers from task_03 must be ancestor of this route

### Related ADRs
- [ADR-001: Contextual Recent Projects Sidebar with Active Selection](adrs/adr-001.md) — hide at zero, cap display from cubit list
- [ADR-005: OrchestratorPage on Existing Orchestrator Route](adrs/adr-005.md) — same path, new page type

## Deliverables
- `lib/features/orchestrator/presentation/pages/orchestrator_page.dart`
- `lib/features/orchestrator/presentation/widgets/recent_projects_sidebar.dart`
- `lib/features/orchestrator/presentation/widgets/recent_project_list_tile.dart`
- Updated `OrchestratorStrings` + `orchestrator_strings_test.dart`
- Updated `PulseDimensions` + `pulse_dimensions_test.dart`
- Updated `shell_navigator_routes.dart` and router tests
- Unit/string tests with **≥80% coverage** on new strings and widgets logic where testable without widget tests **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `OrchestratorStrings`: new sidebar keys non-empty and contain expected PT-BR fragments (e.g. "Projetos recentes")
  - [x] `OrchestratorStrings`: no English placeholder equals for new keys
  - [x] `PulseDimensions`: sidebar width token positive and distinct from unrelated layout tokens
- Integration tests:
  - [x] `shell_navigator_routes_test`: `RoutePaths.orchestrator` builds `OrchestratorPage` (not `OrchestratorEmptyPage`)
- Test coverage target: >=80% on new/updated test targets
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on strings and dimension tests for this scope
- Sidebar hidden with zero projects; visible with one or more
- Active row visually distinct per DS; keyboard activation works on list tiles
- `flutter analyze` passes; no user-facing string literals in widgets
