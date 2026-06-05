---
status: completed
title: Cursor connection port and preflight cubit
type: backend
complexity: medium
dependencies:
  - task_01
---

# Task 06: Cursor connection port and preflight cubit

**Phase:** PR-3 — Cursor: conexão e serviço híbrido

## Overview

Introduz o contrato `CursorPrdAgentService` (métodos mínimos para preflight), armazenamento seguro de credencial fora de Hive/FS, e `CursorConnectionCubit` com estados conectado/desconectado/verificando para bloquear start de run na UI. Strings de remediation em PT-BR.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST define `CursorPrdAgentService` port in `domain/service/` per TechSpec "Core Interfaces"
- MUST implement credential read/write via platform-appropriate secure storage abstraction (no plaintext in Hive, SharedPreferences workflow doc, or stream payloads)
- MUST implement `CursorConnectionCubit` exposing preflight status suitable for onboarding banner
- MUST map HTTP 401 from preflight to `CursorConnectionFailure` with PT-BR remediation copy in `OrchestratorStrings` or new `PrdWorkflowStrings`
- MUST register cubit in `OrchestratorComposition`
- MUST NOT log API keys or tokens
- SHOULD allow stub/fake implementation for tests and for task_07 to extend same port
</requirements>

## Subtasks
- [x] 6.1 Define service port and connection failure types
- [x] 6.2 Implement secure credential store service under `service/` or `core/service/`
- [x] 6.3 Implement `CursorConnectionCubit` + state with `bloc_test`
- [x] 6.4 Add PT-BR strings for disconnected and 401 remediation
- [x] 6.5 Wire cubit in composition; no cloud run start yet

## Implementation Details

See TechSpec **Integration Points → Cursor Cloud Agents** (auth, fail fast on 401) and **Development Sequencing** step 6.

Follow existing `LocalGitBranchesService` contract/impl split. Presentation cubit under `presentation/bloc/`.

### Relevant Files
- `lib/features/orchestrator/domain/service/` — new port
- `lib/features/orchestrator/presentation/bloc/` — connection cubit
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — PT-BR copy
- `lib/app/di/orchestrator_composition.dart` — provider

### Dependent Files
- `test/features/orchestrator/presentation/orchestrator_strings_test.dart` — extend for new keys

### Related ADRs
- [ADR-004: Hybrid Cursor Runtime](../adrs/adr-004.md) — secrets outside artifacts
- [ADR-001: Native Pulse Cockpit](../adrs/adr-001.md) — connection onboarding

## Deliverables
- `CursorPrdAgentService` interface (start/watch/cancel signatures; impl deferred to task_07)
- Secure credential service + fake
- `CursorConnectionCubit` with bloc tests
- PT-BR strings + strings test updates
- Unit tests with **≥80% coverage** **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `CursorConnectionCubit`: missing credential emits disconnected with remediation message key
  - [x] `CursorConnectionCubit`: successful preflight emits connected
  - [x] `CursorConnectionCubit`: 401 response emits failure state without exposing token in state `toString`
  - [x] Secure store: save then read round-trip via fake
- Integration tests:
  - [ ] N/A — no real Cursor API in CI
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80%
- UI can observe connection state before task_12 banner
- No secrets in Hive or artifact paths
