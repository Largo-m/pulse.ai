---
status: completed
title: Picker service, use cases, and unit tests
type: backend
complexity: high
dependencies:
  - task_01
---

# Task 2: Picker service, use cases, and unit tests

## Overview

Implementa a seleção de pasta via `file_picker` atrás de um contrato de serviço e os três use cases de negócio (importar, listar, selecionar ativo), incluindo regras de cap 10, dedupe por path e promoção na re-importação. Desbloqueia os cubits da task 03.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST define `LocalDirectoryPickerService`, `DirectoryPickOutcome`, and `DirectoryPickResult` in domain per TechSpec "Core Interfaces"
- MUST implement picker in `lib/features/orchestrator/service/` using `FilePicker.platform.getDirectoryPath()` with directories only and `lockParentWindow: true` on desktop
- MUST map picker `null` to `DirectoryPickOutcome.cancelled` without persistence or user error (PRD F1)
- MUST implement `ImportLocalProjectUseCase`: normalize path, `basename` display name, upsert, set active, enforce max 10 by dropping oldest `lastAccessedAt`
- MUST implement `ListRecentProjectsUseCase`: return projects sorted by `lastAccessedAt` descending
- MUST implement `SelectActiveProjectUseCase`: persist active id; allow clear when invalid on hydrate (TechSpec domain rules)
- MUST use fakes for `RecentProjectsRepository` and `LocalDirectoryPickerService` in tests — no real OS picker in CI
- MUST NOT add UI, cubits, or navigation in this task
</requirements>

## Subtasks
- [x] 2.1 Add domain picker contract and service implementation wrapping `file_picker`
- [x] 2.2 Implement `ImportLocalProjectUseCase` with dedupe, cap 10, and active assignment
- [x] 2.3 Implement `ListRecentProjectsUseCase` and `SelectActiveProjectUseCase`
- [x] 2.4 Add unit tests for picker outcomes and all use case rules from TechSpec "Testing Approach"
- [x] 2.5 Run `flutter analyze` on new orchestrator domain/service code

## Implementation Details

See TechSpec **Implementation Design**, **Integration Points → file_picker**, and **Testing Approach → Unit Tests** (use case rows).

`ImportLocalProjectUseCase` orchestrates picker → entity build → `upsertAndPromote` → active id. Re-import same `id` updates timestamp and order without duplicate rows (ADR-001, ADR-004).

### Relevant Files
- `lib/features/orchestrator/domain/` — created in task_01; extend with service contract and use cases
- `lib/features/orchestrator/data/repositories/recent_projects_repository_impl.dart` — consumed by use cases
- `pubspec.yaml` — `file_picker` already declared; use via service layer only

### Dependent Files
- `test/features/orchestrator/` — new `domain/` and `service/` test directories

### Related ADRs
- [ADR-001: Contextual Recent Projects Sidebar with Active Selection](adrs/adr-001.md) — cap 10, dedupe, promote on re-import
- [ADR-004: Normalized Absolute Path as Project Identity](adrs/adr-004.md) — dedupe key

## Deliverables
- `lib/features/orchestrator/domain/service/local_directory_picker_service.dart`
- `lib/features/orchestrator/service/local_directory_picker_service_impl.dart` (or equivalent naming)
- `lib/features/orchestrator/domain/usecases/import_local_project_use_case.dart`
- `lib/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart`
- `lib/features/orchestrator/domain/usecases/select_active_project_use_case.dart`
- Unit tests for picker service (fake platform) and all three use cases
- Unit tests with **≥80% coverage** **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Picker returns `cancelled` when platform returns null — no repository writes
  - [x] Picker returns `success` with absolute path when platform returns a path string
  - [x] Picker returns `failure` with message when platform throws
  - [x] `ImportLocalProjectUseCase`: new path creates project, sets active, persists via fake repo
  - [x] `ImportLocalProjectUseCase`: re-import same `id` updates `lastAccessedAt` and does not duplicate rows
  - [x] `ImportLocalProjectUseCase`: eleventh import drops project with oldest `lastAccessedAt`
  - [x] `ListRecentProjectsUseCase`: empty store returns empty list
  - [x] `ListRecentProjectsUseCase`: returns projects sorted newest-first
  - [x] `SelectActiveProjectUseCase`: persists given project id via repository
- Integration tests:
  - [ ] N/A (no UI; OS picker faked)
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on new use cases and picker service
- Use cases satisfy PRD F1 and F3 business rules without cubits
- `flutter analyze` passes
