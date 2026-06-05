---
status: completed
title: Approve, reject with feedback, and auto-rerun
type: backend
complexity: medium
dependencies:
  - task_08
---

# Task 09: Approve, reject with feedback, and auto-rerun

**Phase:** PR-4 — Lifecycle da run e gates de aprovação

## Overview

Entrega `ApprovePrdUseCase` e `RejectPrdWithFeedbackUseCase` que enfileira automaticamente nova run com `feedback` e `supersedesRunId`, atualiza metadados de aprovação no Hive e fecha o backend do MVP PRD antes da UI de review.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `ApprovePrdUseCase` setting approval status `approved`, `approvedAt`, and phase `approved` without starting TechSpec agent (ADR-002)
- MUST implement reject flow that stores feedback on rejected run, links new run via `supersedesRunId`, and calls `StartPrdAgentRunUseCase` in same flow without extra user click (ADR-007)
- MUST pass `feedback` into `PrdRunRequest` for superseding run
- MUST preserve `sourceRunId` / edit metadata when user had saved inline edits per ADR-008 coordination with task_11
- MUST NOT write approved PRD to Git repository
</requirements>

## Subtasks
- [x] 9.1 Implement approve use case updating `PrdApprovalEntity` and workflow phase
- [x] 9.2 Implement reject+auto-rerun orchestration use case
- [x] 9.3 Add metrics fields hooks (`approvedAt`, `supersedesRunId`) for observability table in TechSpec
- [x] 9.4 Unit tests: reject triggers exactly one new start; approve does not start run
- [x] 9.5 Wire use cases in composition

## Implementation Details

See TechSpec **Development Sequencing** step 9 and **Testing Approach → Critical scenarios** (reject auto-rerun, approved not in Git).

### Relevant Files
- `lib/features/orchestrator/domain/usecases/approve_prd_use_case.dart` — new
- `lib/features/orchestrator/domain/usecases/reject_prd_with_feedback_use_case.dart` — new
- `lib/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart` — task_08

### Dependent Files
- `lib/features/orchestrator/presentation/bloc/prd_review_cubit.dart` — task_11 invokes these

### Related ADRs
- [ADR-007: Automatic PRD Re-run After Rejection](../adrs/adr-007.md) — no second click
- [ADR-002: PRD-Only MVP Scope](../adrs/adr-002.md) — no TechSpec auto-start
- [ADR-008: Inline PRD Editing](../adrs/adr-008.md) — metadata on approve

## Deliverables
- Approve and reject use cases with fakes
- Unit tests covering lineage and phase transitions
- Unit tests with **≥90% coverage** **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Approve: workflow `prdPhaseStatus` becomes `approved`; `approvedAt` non-null
  - [x] Approve: does not invoke `CursorPrdAgentService.startRun`
  - [x] Reject with feedback `"missing NFRs"`: new run created with `supersedesRunId` pointing to prior run
  - [x] Reject: `StartPrdAgentRunUseCase` invoked exactly once automatically
  - [x] Reject: prior run retains stored feedback text for audit
  - [x] Approve after user-edited draft: approved artifact metadata records edit timestamp
- Integration tests:
  - [x] N/A
- Test coverage target: >=90%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=90%
- PR-4 backend complete
- Reject→running transition testable before UI task_11
