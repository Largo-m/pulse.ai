---
status: completed
title: Filesystem artifact store and ArtifactRepository
type: backend
complexity: medium
dependencies:
  - task_02
---

# Task 03: Filesystem artifact store and ArtifactRepository

**Phase:** PR-2 — Persistência Pulse (FS + Hive + UCs base)

## Overview

Implementa o armazenamento de blobs markdown em application support sob `pulse/workflows/{projectId}/{slug}/`, com contrato de domínio `ArtifactRepository` e escrita atômica (temp → rename). Permite ler/escrever `prd.md` e listar `adrs/` sem Hive de conteúdo.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST create `ArtifactRepository` interface per TechSpec "Core Interfaces" section
- MUST implement layout `pulse/workflows/{projectId}/{slug}/prd.md` and `adrs/adr-NNN.md` using `path_provider` application support directory
- MUST use atomic write (temp file then rename) for `writePrdMarkdown`
- MUST return typed failures via `Either<Failure, T>` (`ArtifactPersistenceFailure`) without SDK details in messages
- MUST NOT write artifacts into imported Git repository paths
- MUST NOT persist API keys, tokens, or full PRD bodies in logs
- SHOULD support empty/missing `prd.md` with predictable failure or empty string per contract tests
</requirements>

## Subtasks
- [x] 3.1 Define domain contract and `PrdArtifactMetadata` / `AdrEntry` models
- [x] 3.2 Implement `FilesystemArtifactStore` under `data/`
- [x] 3.3 Implement `ArtifactRepositoryImpl` coordinating paths only (no Hive yet)
- [x] 3.4 Add temp-directory unit tests with real IO on temp dir
- [x] 3.5 Register repository stub in composition (optional no-op provider until task_05)

## Implementation Details

See TechSpec **Data Models → Filesystem layout** and **Integration Points → Filesystem**.

New files under `lib/features/orchestrator/domain/repositories/artifact_repository.dart` and `lib/features/orchestrator/data/`. Introduce `lib/core/error/` failure types if not present, aligned with orchestrator patterns.

### Relevant Files
- `pubspec.yaml` — `path_provider` already present
- `lib/features/orchestrator/domain/repositories/` — new contract
- `lib/features/orchestrator/data/` — store + impl
- `test/features/orchestrator/data/` — mirror tests

### Dependent Files
- `lib/app/di/orchestrator_composition.dart` — future wiring in task_05

### Related ADRs
- [ADR-003: Pulse-Internal Artifact Storage](../adrs/adr-003.md) — project + slug layout
- [ADR-005: Hive-Indexed + Filesystem Blobs](../adrs/adr-005.md) — markdown on disk tier

## Deliverables
- `ArtifactRepository` contract and domain value types
- `FilesystemArtifactStore` + `ArtifactRepositoryImpl`
- Unit tests: round-trip PRD write/read, ADR list, atomic write failure simulation
- Unit tests with **≥90% coverage** on repository and store **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `writePrdMarkdown` then `readPrdMarkdown` returns identical content for valid projectId/slug
  - [x] `listAdrs` returns entries sorted or ordered per contract when `adrs/` contains `adr-001.md` and `adr-002.md`
  - [x] Write failure mid-rename leaves prior `prd.md` unchanged
  - [x] Invalid slug path segments rejected or sanitized per kebab-case policy delegated to workflow layer
- Integration tests:
  - [x] Temp directory integration: full path layout created under fake app support root
- Test coverage target: >=90%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90% on artifact repository code
- Artifacts resolvable by `projectId` + `slug` only
- No Git tree writes in implementation
