---
status: completed
title: Dependencies and domain/data persistence layer
type: backend
complexity: high
dependencies: []
---

# Task 1: Dependencies and domain/data persistence layer

## Overview

Estabelece a base de persistência local para projetos recentes: dependências (`shared_preferences`), entidade de domínio, contrato do repositório, normalização de path e implementação de leitura/gravação JSON versionado. Esta task desbloqueia use cases e cubits sem tocar na UI.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST add `shared_preferences` to `pubspec.yaml` and run `flutter pub get`
- MUST add `bloc_test` to `dev_dependencies` for downstream cubit tasks
- MUST create `LocalProjectEntity` with `id`, `absolutePath`, `displayName`, `lastAccessedAt` per TechSpec "Data Models"
- MUST create `RecentProjectsRepository` interface per TechSpec "Core Interfaces"
- MUST implement path normalization helper (dedicated type or extension) so project `id` is the normalized absolute path (ADR-004)
- MUST persist versioned JSON at key `orchestrator.recent_projects.v1` with `schemaVersion`, `activeProjectId`, and `projects[]` (ADR-002)
- MUST implement `RecentProjectsLocalStorage` and `RecentProjectsRepositoryImpl` under `lib/features/orchestrator/data/`
- MUST treat corrupt or unparsable JSON as empty list and null active id without crashing
- MUST NOT import Flutter, Dio, or `dart:io` in `domain/`
- MUST follow Clean Architecture: domain contracts only; data layer implements persistence
</requirements>

## Subtasks
- [x] 1.1 Add `shared_preferences` and `bloc_test`; run `flutter pub get`
- [x] 1.2 Create domain entity, repository interface, and path normalizer
- [x] 1.3 Implement local storage adapter and repository with JSON round-trip
- [x] 1.4 Add unit tests for normalizer, repository round-trip, and corrupt JSON recovery
- [x] 1.5 Run `flutter analyze` on touched packages

## Implementation Details

See TechSpec sections **Implementation Design → Core Interfaces**, **Data Models**, and **Integration Points → shared_preferences**.

Create `lib/features/orchestrator/domain/` (entities, repositories) and `lib/features/orchestrator/data/` (storage + `RecentProjectsRepositoryImpl`). Cap-10, dedupe, and promote rules belong in use cases (task 02), not in the repository — repository exposes `listRecent`, `getActiveProjectId`, `upsertAndPromote`, `setActiveProjectId`.

### Relevant Files
- `pubspec.yaml` — add dependencies
- `lib/features/orchestrator/presentation/` — existing feature; new layers sit alongside
- `test/features/orchestrator/` — mirror new domain/data tests here

### Dependent Files
- `pubspec.lock` — updated after `flutter pub get`

### Related ADRs
- [ADR-002: shared_preferences for Recent Projects Persistence](adrs/adr-002.md) — versioned JSON document
- [ADR-004: Normalized Absolute Path as Project Identity](adrs/adr-004.md) — path as `id`

## Deliverables
- `lib/features/orchestrator/domain/entities/local_project_entity.dart`
- `lib/features/orchestrator/domain/repositories/recent_projects_repository.dart`
- Path normalizer (file location per team convention under `domain/`)
- `lib/features/orchestrator/data/recent_projects_local_storage.dart`
- `lib/features/orchestrator/data/repositories/recent_projects_repository_impl.dart`
- Unit tests for normalizer and repository (round-trip + corrupt JSON)
- Unit tests with **≥80% coverage** on new domain/data types **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `ProjectPathNormalizer` (or equivalent): relative path resolves to absolute; duplicate slashes normalized; empty input fails predictably
  - [x] `RecentProjectsRepositoryImpl`: save then `listRecent` returns same projects in stored order
  - [x] `RecentProjectsRepositoryImpl`: `getActiveProjectId` round-trips after `setActiveProjectId`
  - [x] `RecentProjectsRepositoryImpl`: malformed JSON string returns empty list and null active id
  - [x] `RecentProjectsRepositoryImpl`: missing prefs key returns empty list and null active id
- Integration tests:
  - [ ] N/A for this task (local prefs only; covered by unit fakes)
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on new domain/data code
- `flutter analyze` passes with no new issues
- Repository and entity match TechSpec contracts without UI or picker code
