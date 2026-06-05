---
status: completed
title: Workflow and artifact domain use cases
type: backend
complexity: medium
dependencies:
  - task_04
---

# Task 05: Workflow and artifact domain use cases

**Phase:** PR-2 — Persistência Pulse (FS + Hive + UCs base)

## Overview

Entrega os use cases de domínio para criar workflow com slug kebab-case único, listar workflows por projeto, salvar rascunho de PRD e ler PRD/ADRs — tudo com `Either<Failure, T>`. Fecha o backend de persistência sem integração Cursor.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `CreateWorkflowUseCase` validating kebab-case slug and uniqueness via Hive query
- MUST implement `ListWorkflowsByProjectUseCase` for sidebar consumption
- MUST implement `SavePrdDraftUseCase` and read helpers delegating to `ArtifactRepository` with metadata updates in `PrdRunRepository`/`PrdApprovalEntity`
- MUST return `Either<Failure, T>` for all public use case methods
- MUST define failures: slug validation, slug collision, artifact persistence (names per TechSpec error handling)
- MUST wire use cases in `OrchestratorComposition` as factories
- MUST NOT call Cursor API or start agent runs
</requirements>

## Subtasks
- [x] 5.1 Add domain entities `WorkflowEntity` exports and failure types under `core/error` or feature domain
- [x] 5.2 Implement create + list workflow use cases with fakes
- [x] 5.3 Implement save draft and read PRD/ADR use cases coordinating Hive + FS
- [x] 5.4 Register use cases in composition scope
- [x] 5.5 Unit tests: happy path, slug collision, invalid slug format

## Implementation Details

See TechSpec **Implementation Design**, **Development Sequencing** step 5, and **Testing Approach → Unit Tests** (create workflow slug collision).

Mirror `test/features/orchestrator/domain/usecases/fake_recent_projects_repository.dart` pattern for new fakes.

### Relevant Files
- `lib/features/orchestrator/domain/usecases/` — new use case files
- `lib/features/orchestrator/domain/repositories/workflow_repository.dart` — from task_04
- `lib/features/orchestrator/domain/repositories/artifact_repository.dart` — from task_03
- `lib/app/di/orchestrator_composition.dart` — DI wiring

### Dependent Files
- `lib/features/orchestrator/presentation/widgets/recent_projects_sidebar.dart` — consumes list in task_13

### Related ADRs
- [ADR-003: Pulse-Internal Artifact Storage](../adrs/adr-003.md) — slug + project resolution

## Deliverables
- Create/list/save/read use cases with fakes
- Composition wiring for downstream cubits
- Unit tests with **≥90% coverage** on use cases **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `CreateWorkflowUseCase`: valid kebab slug `cursor-workflow-agents` persists workflow
  - [x] `CreateWorkflowUseCase`: duplicate slug for same `projectId` returns Left slug collision
  - [x] `CreateWorkflowUseCase`: slug `Bad_Slug` returns Left validation failure
  - [x] `ListWorkflowsByProjectUseCase`: empty project returns empty list
  - [x] `SavePrdDraftUseCase`: writes markdown and updates `lastEditedAt` metadata
  - [x] Read PRD returns content after save via fake artifact repo
- Integration tests:
  - [x] Optional: fake Hive box + temp dir through repository impl (defer if covered in task_04)
- Test coverage target: >=90%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90% on new use cases
- PR-2 backend usable without network
- Ready for `CursorPrdAgentService` context in task_07
