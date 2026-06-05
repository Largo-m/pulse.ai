---
status: completed
title: Cubits, composition wiring, and bloc tests
type: frontend
complexity: medium
dependencies:
  - task_02
---

# Task 3: Cubits, composition wiring, and bloc tests

## Overview

Expõe o estado de projetos recentes e do fluxo de importação via `RecentProjectsCubit` e `ImportFlowCubit`, e registra dependências (repositório, serviços, use cases, cubits) na composição do app. A UI das tasks 04–05 consome apenas esses cubits — sem lógica de negócio nas páginas.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST create `RecentProjectsCubit` under `presentation/bloc/` with hydrate on init, exposed list + `activeProjectId`, `selectProject`, and `refresh` (ADR-003)
- MUST create `ImportFlowCubit` with `importLocal()` delegating to `ImportLocalProjectUseCase` and states for loading, success, cancelled, and failure
- MUST NOT perform navigation or `RecentProjectsCubit.refresh()` inside cubits — page coordinates pop + refresh per ADR-003
- MUST wire repository, picker service, use cases, and cubits in `main.dart` and/or minimal `lib/app/di/` following existing app composition patterns
- MUST use `bloc_test` for cubit state transitions
- MUST NOT modify orchestrator pages, sidebar widgets, or router in this task
- MUST keep cubits testable with fake repository and fake picker injected via constructors
</requirements>

## Subtasks
- [x] 3.1 Define cubit states and implement `RecentProjectsCubit` (hydrate, select, refresh)
- [x] 3.2 Implement `ImportFlowCubit` (importLocal and outcome emissions)
- [x] 3.3 Register providers for repo, services, use cases, and cubits in app composition
- [x] 3.4 Add `bloc_test` coverage for hydrate, select, refresh, and import outcomes
- [x] 3.5 Verify `flutter analyze` passes

## Implementation Details

See TechSpec **System Architecture** (cubit responsibilities) and **Development Sequencing** steps 7–9. Split cubits intentionally: import page will listen to `ImportFlowCubit` and call `RecentProjectsCubit.refresh()` on success (task 05).

### Relevant Files
- `lib/main.dart` — `PulseShell` / `MaterialApp`; primary composition entry today
- `lib/features/orchestrator/domain/usecases/` — from task_02
- `pubspec.yaml` — `flutter_bloc` and `bloc_test` (added in task_01)

### Dependent Files
- `lib/app/di/` — create if no DI folder exists yet

### Related ADRs
- [ADR-003: Split Cubits for Recent Projects and Import Flow](adrs/adr-003.md) — no navigation inside cubits

## Deliverables
- `lib/features/orchestrator/presentation/bloc/recent_projects_cubit.dart` (+ state file if separated)
- `lib/features/orchestrator/presentation/bloc/import_flow_cubit.dart` (+ state file if separated)
- Composition registration in `main.dart` and/or `lib/app/di/`
- `bloc_test` suites for both cubits
- Unit tests with **≥80% coverage** on cubits **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `RecentProjectsCubit` initial load emits list and active id from fake repository
  - [x] `RecentProjectsCubit.selectProject` calls use case and emits updated active id
  - [x] `RecentProjectsCubit.refresh` re-reads repository after external update (simulated fake mutation)
  - [x] `RecentProjectsCubit`: active id not in list after hydrate emits no active highlight (null or equivalent state)
  - [x] `ImportFlowCubit.importLocal` emits loading then success when use case returns project
  - [x] `ImportFlowCubit.importLocal` emits cancelled without failure state when picker cancelled
  - [x] `ImportFlowCubit.importLocal` emits failure with message when use case/picker fails
- Integration tests:
  - [ ] N/A (composition smoke can be manual until task 04)
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on both cubits
- Cubits obtainable from widget tree via composition root
- No UI files changed; `flutter analyze` passes
