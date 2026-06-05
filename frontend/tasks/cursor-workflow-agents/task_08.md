---
status: completed
title: PRD run lifecycle use cases
type: backend
complexity: high
dependencies:
  - task_07
---

# Task 08: PRD run lifecycle use cases

**Phase:** PR-4 — Lifecycle da run e gates de aprovação

## Overview

Implementa o ciclo completo de execução: iniciar run, anexar eventos de stream ao índice Hive (e JSONL opcional), cancelar, concluir com escrita de `prd.md`/`adrs/`, e mapear falhas para estados `failed`/`cancelled`. Liga `CursorPrdAgentService` aos repositórios.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `StartPrdAgentRunUseCase` blocking when connection preflight would fail (inject connection gate or cubit callback contract)
- MUST implement `AppendStreamEventUseCase` persisting `StreamEventEntity` and optional `streams/{runId}.jsonl`
- MUST implement cancel and complete/fail use cases updating `PrdRunEntity.status` per TechSpec run states
- MUST transition workflow `prdPhaseStatus` to `pendingApproval` on successful completion with artifacts on disk
- MUST cap in-memory stream buffer policy documented for presentation (constant); full history in JSONL/Hive index
- MUST NOT expose raw SSE payloads in UI types
</requirements>

## Subtasks
- [x] 8.1 Implement start run: persist run row, call service, bind `cloudRunId`
- [x] 8.2 Implement append stream with monotonic sequence
- [x] 8.3 Implement cancel and terminal status handlers
- [x] 8.4 Implement complete handler writing artifacts from agent output payload (fake-driven in tests)
- [x] 8.5 Unit tests for queued→running→completed and cancel mid-flight

## Implementation Details

See TechSpec **Data flow (happy path)** steps 2–4, **Testing Approach → Critical scenarios** (cancel mid-flight), and **Development Sequencing** step 8.

### Relevant Files
- `lib/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart` — new
- `lib/features/orchestrator/domain/usecases/append_stream_event_use_case.dart` — new
- `lib/features/orchestrator/domain/repositories/prd_run_repository.dart` — task_04
- `test/features/orchestrator/domain/usecases/fake_cursor_prd_agent_service.dart` — new fake

### Dependent Files
- `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` — task_10 subscribes to stream

### Related ADRs
- [ADR-001: Native Pulse Cockpit](../adrs/adr-001.md) — live stream persistence
- [ADR-005: Hive + Filesystem](../adrs/adr-005.md) — stream index + JSONL optional

## Deliverables
- Start/append/cancel/complete use cases
- Fake agent emitting completion with sample markdown
- Unit tests with **≥90% coverage** **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Start run: creates Hive run with status `queued` then `running` after service ack
  - [x] Append stream: three events stored with sequences 1, 2, 3 for same `runId`
  - [x] Cancel: in-flight run becomes `cancelled`; no further append accepted
  - [x] Complete: writes `prd.md`, sets phase `pendingApproval`, run status `completed`
  - [x] Fail: service error maps to `failed` without partial approval metadata
  - [x] Start blocked when connection gate reports disconnected (Left failure)
- Integration tests:
  - [x] Temp dir + fake Hive: complete run leaves `prd.md` bytes matching agent output
- Test coverage target: >=90%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90%
- Backend supports full happy path without UI
- Ready for approve/reject in task_09
