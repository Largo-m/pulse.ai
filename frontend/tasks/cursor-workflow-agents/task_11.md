---
status: completed
title: PrdReviewCubit, inline editor, and review actions
type: frontend
complexity: medium
dependencies:
  - task_05
  - task_09
  - task_10
---

# Task 11: PrdReviewCubit, inline editor, and review actions

**Phase:** PR-5 — Workspace PRD (UI)

## Overview

Implementa revisão do PRD com editor markdown inline, estado dirty, salvar rascunho, aprovar e rejeitar com feedback — integrando use cases de task_05 e task_09. Inclui aviso antes de overwrite quando nova run substitui `prd.md`.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implement `PrdReviewCubit` loading draft from artifact repo when status is `draft` or `pendingApproval`
- MUST track dirty state separately from saved content; save invokes `SavePrdDraftUseCase`
- MUST wire Approve and Reject actions to task_09 use cases
- MUST warn user when new agent run would overwrite unsaved edits (dialog copy PT-BR)
- MUST show optional read-only repo path/branch header per TechSpec open question #6 resolution
- MUST use `ValueNotifier`/`ListenableBuilder` or cubit for editor state — no `setState`
- MUST show user-edited badge when `lastEditedAt` differs from agent `sourceRunId` metadata (ADR-008)
- MUST keep keyboard-accessible approve/reject controls with semantics labels
</requirements>

## Subtasks
- [x] 11.1 Implement `PrdReviewCubit` load/save/dirty transitions
- [x] 11.2 Build markdown editor widget subtree with DS tokens
- [x] 11.3 Build approve/reject/feedback UI (reject triggers auto-rerun via cubit)
- [x] 11.4 Implement unsaved-changes guard when `PrdWorkflowCubit` signals new run
- [x] 11.5 `bloc_test` for save, approve, reject, dirty overwrite guard

## Implementation Details

See TechSpec **Component Overview** (`PrdReviewCubit`) and **Testing Approach** (unsaved editor warning).

### Relevant Files
- `lib/features/orchestrator/presentation/bloc/prd_review_cubit.dart` — new
- `lib/features/orchestrator/presentation/widgets/` — review/editor widgets
- `lib/features/orchestrator/domain/usecases/save_prd_draft_use_case.dart` — task_05
- `lib/features/orchestrator/presentation/widgets/workflow_techspec_instruction_bar.dart` — pattern for instruction/feedback bars

### Dependent Files
- `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` — task_12

### Related ADRs
- [ADR-008: Inline PRD Markdown Editing](../adrs/adr-008.md) — editor before approval
- [ADR-007: Auto Re-run on Reject](../adrs/adr-007.md) — reject button behavior

## Deliverables
- `PrdReviewCubit` + review/editor widgets
- PT-BR strings for approve, reject, feedback, unsaved warning, edited badge
- `bloc_test` with **≥80% coverage** **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Load draft populates editor controller text from fake repo
  - [x] Save draft clears dirty flag and calls save use case once
  - [x] Approve invokes approve use case with current editor text persisted
  - [x] Reject with feedback `"add security"` invokes reject use case; does not require second run click
  - [x] Dirty guard: when new run pending and dirty true, cubit emits `mustConfirmOverwrite` (or equivalent) before load replaces text
  - [x] Approve blocked when connection disconnected if business rule applies at review time
- Integration tests:
  - [ ] N/A
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on review cubit
- Inline edit + approve path covered by tests
- ADR-008 behaviors demonstrable in PR-5
