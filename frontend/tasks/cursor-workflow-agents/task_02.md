---
status: completed
title: Recent projects v2 UUID migration
type: backend
complexity: medium
dependencies:
  - task_01
---

# Task 02: Recent projects v2 UUID migration

**Phase:** PR-1 — Fundação e identidade de projeto

## Overview

Migra o documento de projetos recentes para `schemaVersion: 2` com `projectId` UUID estável e `canonicalPath` para resolução Git/sandbox. Todas as chaves downstream de workflow e artifacts passam a usar UUID, não path normalizado como id.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST bump `RecentProjectsDocument` to `schemaVersion: 2` with `LocalProjectEntity` fields: UUID `id`, `canonicalPath`, `displayName`, `lastAccessedAt`, `macosSecurityScopedBookmark` per TechSpec "Data Models"
- MUST implement migration use case: v1 path-as-id → v2 UUID + `canonicalPath` from former id; rewrite `activeProjectId` to UUID
- MUST preserve existing cap/dedupe/promote behavior in list/upsert use cases after migration
- MUST treat corrupt v1 JSON as empty document without crash (existing behavior)
- MUST update `ImportLocalProjectUseCase` to resolve existing UUID when `canonicalPath` matches
- MUST update all tests that assert path-as-id to UUID semantics
- MUST NOT store Cursor credentials or workflow data in SharedPreferences document
</requirements>

## Subtasks
- [x] 2.1 Extend document model and entity with v2 fields
- [x] 2.2 Implement `MigrateRecentProjectsUseCase` (or equivalent) invoked on first read after upgrade
- [x] 2.3 Update repository impl and import/upsert flows for UUID assignment
- [x] 2.4 Migrate unit tests and add v1→v2 fixture coverage
- [x] 2.5 Run `dart format .` and `flutter analyze`

## Implementation Details

See TechSpec **Data Models → Recent projects v2** and **Impact Analysis → recent_projects_document.dart**.

Modify `lib/features/orchestrator/data/models/recent_projects_document.dart`, `domain/entities/local_project_entity.dart`, `data/repositories/recent_projects_repository_impl.dart`, and `domain/usecases/import_local_project_use_case.dart`. Consider storage key bump or version field only — document decision in PR description, not here.

### Relevant Files
- `lib/features/orchestrator/data/models/recent_projects_document.dart` — schema v2
- `lib/features/orchestrator/domain/entities/local_project_entity.dart` — UUID id
- `lib/features/orchestrator/domain/usecases/import_local_project_use_case.dart` — path match → existing UUID
- `test/features/orchestrator/data/repositories/recent_projects_repository_impl_test.dart` — migration cases

### Dependent Files
- `lib/features/orchestrator/presentation/bloc/recent_projects_cubit.dart` — consumes migrated ids
- `test/features/orchestrator/domain/usecases/import_local_project_use_case_test.dart` — updated assertions

### Related ADRs
- [ADR-006: Stable Mapped Project Identity via UUID](../adrs/adr-006.md) — v2 migration requirement
- [ADR-003: Pulse-Internal Artifact Storage](../adrs/adr-003.md) — stable `projectId` keys

## Deliverables
- v2 document encoding/decoding
- Migration use case with tests for v1 sample JSON → v2 UUIDs
- Updated import and repository tests
- Unit tests with **≥90% coverage** on new migration and entity paths per project rules **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Migration: v1 document with two path ids produces two distinct UUIDs and matching `canonicalPath`
  - [x] Migration: `activeProjectId` in v1 rewritten to UUID in v2 output
  - [x] Migration: already v2 document is no-op
  - [x] Import: re-import same `canonicalPath` returns same UUID, does not duplicate list entry
  - [x] Corrupt JSON: empty document, null active id
- Integration tests:
  - [x] N/A — SharedPreferences mock sufficient
- Test coverage target: >=90% on migration use case and document changes
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90% on migration-related code
- `flutter analyze` passes
- Sidebar and modal continue to receive opaque UUID `projectId`
