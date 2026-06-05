---
status: completed
title: CursorPrdAgentService hybrid implementation
type: backend
complexity: high
dependencies:
  - task_02
  - task_05
  - task_06
---

# Task 07: CursorPrdAgentService hybrid implementation

**Phase:** PR-3 — Cursor: conexão e serviço híbrido

## Overview

Implementa `CursorPrdAgentServiceImpl` com cliente Cloud Agents API, mapeamento SSE → `PrdStreamEvent`, cancelamento, e `PrdRunContextBuilder` que monta contexto local (UUID, `canonicalPath`, branch, slug, directive) via serviços Git/sandbox existentes.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `startRun`, `watchRun`, `cancelRun` per TechSpec "Core Interfaces" and `PrdRunRequest` fields
- MUST build local context from `RecentProjectsRepository` + `ListLocalGitBranchesUseCase` / sandbox services — not from raw paths in presentation
- MUST map cloud/network errors to `CursorConnectionFailure` or `PrdRunFailure` without SDK payloads in UI-facing types
- MUST apply exponential backoff on HTTP 5xx for transient calls per TechSpec Integration Points
- MUST NOT write to imported Git tree
- MUST provide fake implementation emitting deterministic stream events for downstream task_08 tests
- SHOULD isolate HTTP paths behind single impl file for API churn mitigation per ADR-004
</requirements>

## Subtasks
- [x] 7.1 Implement `PrdRunContextBuilder` resolving project UUID to canonical path and branch
- [x] 7.2 Implement cloud client + SSE parser → `PrdStreamEvent`
- [x] 7.3 Implement `CursorPrdAgentServiceImpl` in `service/`
- [x] 7.4 Register impl in composition replacing stub
- [x] 7.5 Unit tests with fake HTTP/SSE fixtures; verify no repo writes

## Implementation Details

See TechSpec **API Endpoints**, **Integration Points**, and **Development Sequencing** step 7. Reference Cursor SDK docs externally — do not duplicate endpoint paths in this file.

Use `lib/features/orchestrator/service/local_git_branches_service_impl.dart` and `project_sandbox_access_service_impl.dart` for branch validation.

### Relevant Files
- `lib/features/orchestrator/service/cursor_prd_agent_service_impl.dart` — new
- `lib/features/orchestrator/domain/service/cursor_prd_agent_service.dart` — from task_06
- `lib/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart` — branch context
- `lib/features/orchestrator/data/repositories/recent_projects_repository_impl.dart` — UUID → path

### Dependent Files
- `lib/features/orchestrator/domain/usecases/` — task_08 start run consumes service

### Related ADRs
- [ADR-004: Hybrid Cursor Runtime](../adrs/adr-004.md) — cloud + local context
- [ADR-001: Native Pulse Cockpit](../adrs/adr-001.md) — streaming contract

## Deliverables
- `PrdRunContextBuilder`
- `CursorPrdAgentServiceImpl` + `FakeCursorPrdAgentService`
- Recorded fixture tests for stream mapping
- Unit tests with **≥90% coverage** on service and builder **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `startRun` with valid request returns `PrdRunEntity` with non-empty `cloudRunId`
  - [x] `watchRun` fake emits three events in order with increasing sequence
  - [x] `cancelRun` invokes cancel endpoint once and completes
  - [x] Missing project UUID in context builder returns Left not-found failure
  - [x] 5xx response triggers retry policy bounded (assert call count via mock)
  - [x] Service fake: no file writes under repo path (spy on git/filesystem services)
- Integration tests:
  - [ ] N/A — cloud API not required in CI
- Test coverage target: >=90%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90% on service layer
- Fake usable by task_08 use case tests
- PR-3 deliverable complete for lifecycle wiring
