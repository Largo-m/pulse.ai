---
status: completed
title: Hive entities, adapters, and workflow/run repositories
type: backend
complexity: high
dependencies:
  - task_01
  - task_03
---

# Task 04: Hive entities, adapters, and workflow/run repositories

**Phase:** PR-2 — Persistência Pulse (FS + Hive + UCs base)

## Overview

Registra entidades Hive para workflows, runs, aprovação e índice de stream; implementa `WorkflowRepository` e `PrdRunRepository` com disciplina de consistência ponteiro Hive ↔ caminho FS. Desbloqueia listagem rápida na sidebar e metadados de fase PRD.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST define Hive types: `WorkflowEntity`, `PrdRunEntity`, `PrdApprovalEntity`, `StreamEventEntity` per TechSpec "Data Models → Hive entities"
- MUST register TypeAdapters before box open in composition (task_01 bootstrap)
- MUST implement `WorkflowRepository` with create, listByProject, findBySlug per TechSpec "Core Interfaces"
- MUST implement `PrdRunRepository` for run CRUD, stream event index append, and approval metadata linkage
- MUST enforce slug uniqueness per `projectId` at repository or use-case boundary
- MUST use write ordering: filesystem commit before Hive pointer update, or rollback file on Hive failure per ADR-005
- MUST NOT store secrets, full PRD body, or full stream payloads in Hive values (summaries only)
</requirements>

## Subtasks
- [x] 4.1 Create Hive entity classes and generated/manual adapters under `data/`
- [x] 4.2 Open named boxes in composition and expose repositories
- [x] 4.3 Implement `WorkflowRepositoryImpl` with project+slug keys
- [x] 4.4 Implement `PrdRunRepositoryImpl` including stream index entities
- [x] 4.5 Add repository fakes and unit tests for consistency and slug collision
- [x] 4.6 Wire repositories into `OrchestratorComposition`

## Implementation Details

See TechSpec **Implementation Design → Core Interfaces**, **Data Models**, and **Development Sequencing** steps 4.

Place adapters in `lib/features/orchestrator/data/models/` or `data/adapters/`. Domain contracts in `domain/repositories/`. Follow `RecentProjectsRepositoryImpl` placement patterns.

Task 04 index-only workflow CRUD without FS is supported when `FilesystemArtifactStore` is omitted; production composition wires FS-first create with Hive rollback via `PersistenceWriteCoordinator`.

### Relevant Files
- `lib/app/di/orchestrator_composition.dart` — box registration and providers
- `lib/features/orchestrator/data/repositories/recent_projects_repository_impl.dart` — reference impl style
- `lib/features/orchestrator/data/models/recent_projects_document.dart` — separate persistence from Hive boxes

### Dependent Files
- `lib/features/orchestrator/data/repositories/artifact_repository_impl.dart` — coordinated writes in task_05

### Related ADRs
- [ADR-005: Hive-Indexed + Filesystem Blobs](../adrs/adr-005.md) — index vs blob responsibilities
- [ADR-003: Pulse-Internal Artifact Storage](../adrs/adr-003.md) — workflow registry per project

## Deliverables
- Hive entities + adapters registered at startup
- `WorkflowRepository` and `PrdRunRepository` implementations
- Fakes for downstream use case tests
- Unit tests with **≥90% coverage** on repositories **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `create` workflow with duplicate slug for same `projectId` returns slug collision failure
  - [x] `listByProject` returns only workflows for requested UUID `projectId`
  - [x] `findBySlug` returns null when slug absent
  - [x] Stream index append increments `sequence` monotonically per `runId`
  - [x] Simulated Hive write failure after FS write triggers rollback or leaves no orphan pointer (per chosen strategy)
- Integration tests:
  - [x] In-memory Hive + temp dir: workflow create writes FS directory pointer only when task_05 coordinates; for task_04, index-only CRUD without FS is acceptable if documented
- Test coverage target: >=90%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90% on new repositories
- Boxes open without error after task_01 bootstrap
- Repositories ready for use cases in task_05
