---
status: completed
title: Import select-source flow integration
type: frontend
complexity: medium
dependencies:
  - task_03
  - task_04
---

# Task 5: Import select-source flow integration

## Overview

Conecta o card **Selecionar local** ao `ImportFlowCubit`, trata cancelamento e falhas conforme o PRD, e na importação bem-sucedida executa `popUntil(RoutePaths.orchestrator)` seguido de `RecentProjectsCubit.refresh()` para exibir a sidebar atualizada (ADR-003).

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST wire `ImportProjectSelectSourcePage` / `ImportProjectSelectSourceBody` so local card calls `ImportFlowCubit.importLocal()` instead of placeholder snackbar
- MUST keep remote/Git card on existing coming-soon placeholder behavior (unchanged)
- MUST on import success: `Navigator.popUntil` to `RoutePaths.orchestrator` then `RecentProjectsCubit.refresh()` — only in page listener, not inside cubit
- MUST on picker cancel: no SnackBar, no persistence, user remains on select-source screen
- MUST on failure: show PT-BR message via `ImportProjectStrings` / `OrchestratorStrings` using existing feedback patterns (SnackBar or inline)
- MUST preserve top-bar **Importar projeto** entry still routing to select-source (dual entry points per PRD)
- MUST add error/cancel-related PT-BR strings to `ImportProjectStrings` with string tests
- MUST add cubit/page listener test or bloc_test proving success path triggers refresh contract (fake navigation optional)
- MUST run `dart format .`, `flutter analyze`, and full unit test suite before completion
</requirements>

## Subtasks
- [x] 5.1 Pass `onSelectLocal` from page to body; replace local card `onPlaceholder` wiring
- [x] 5.2 Add `BlocListener` (or equivalent) for `ImportFlowCubit` outcomes on select-source page
- [x] 5.3 Implement success navigation + `RecentProjectsCubit.refresh()` in page only
- [x] 5.4 Add failure/cancel strings and tests; wire user-visible failure feedback
- [x] 5.5 Verify remote card still shows coming-soon; run analyze, format, and all unit tests

## Implementation Details

See TechSpec **Data flow — import success**, **Integration Points → Cancel/Failure**, and **Known Risks** (forgotten refresh). Top bar on `OrchestratorPage` already navigates to `RoutePaths.orchestratorImportSelectSource` — no new routes.

### Relevant Files
- `lib/features/orchestrator/presentation/pages/import_project_select_source_page.dart` — listener + cubit access
- `lib/features/orchestrator/presentation/widgets/import_project_select_source_body.dart` — `onSelectLocal` callback
- `lib/features/orchestrator/presentation/import_project_strings.dart` — error messages PT-BR
- `lib/features/orchestrator/presentation/orchestrator_placeholder_feedback.dart` — pattern for coming-soon (remote only)
- `lib/app/router/route_paths.dart` — `popUntil` target constant
- `test/features/orchestrator/presentation/import_project_strings_test.dart` — extend tests

### Dependent Files
- `lib/features/orchestrator/presentation/pages/orchestrator_page.dart` — destination after pop; shows sidebar after refresh
- `lib/features/orchestrator/presentation/bloc/import_flow_cubit.dart` — from task_03
- `lib/features/orchestrator/presentation/bloc/recent_projects_cubit.dart` — refresh after success

### Related ADRs
- [ADR-003: Split Cubits for Recent Projects and Import Flow](adrs/adr-003.md) — page owns navigation + refresh

## Deliverables
- Updated `import_project_select_source_page.dart` and `import_project_select_source_body.dart`
- Updated `ImportProjectStrings` + string tests for new error keys
- Tests covering import flow listener behavior (bloc_test and/or cubit interaction test)
- Full project unit tests green after `dart format .` and `flutter analyze`
- Unit tests with **≥80% coverage** on new listener/string logic **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `ImportProjectStrings`: permission/error message keys non-empty PT-BR
  - [x] `ImportFlowCubit` success emission followed by manual `RecentProjectsCubit.refresh()` updates project count in fake scenario (documented test pairing or single test with both cubits faked)
  - [x] Cancel outcome does not call repository upsert (via use case fake from task_02 patterns)
- Integration tests:
  - [x] N/A for MVP per TechSpec (manual desktop QA matrix)
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on strings and import listener logic added in this task
- Local import from select-source returns to orchestrator with sidebar showing new project as active
- Cancel leaves user on select-source with no error toast
- Failure shows PT-BR message; remote card still coming-soon
- `flutter analyze` clean; `dart format .` applied
