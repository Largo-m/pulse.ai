---
status: completed
title: WorkflowPrdWorkspace and connection banner
type: frontend
complexity: medium
dependencies:
  - task_06
  - task_10
  - task_11
---

# Task 12: WorkflowPrdWorkspace and connection banner

**Phase:** PR-5 — Workspace PRD (UI)

## Overview

Compõe `WorkflowPrdWorkspace` com stepper de fase PRD, painel de stream (task_10), área de review/editor (task_11) e banner de conexão Cursor (`CursorConnectionCubit`). Entrega workspace PRD utilizável quando montado manualmente; submit global permanece em task_13.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST create `WorkflowPrdWorkspace` as PRD-only layout per TechSpec presentation table
- MUST compose existing `WorkflowPhaseStepper` highlighting PRD phase; later phases visually locked/deferred (ADR-002)
- MUST embed stream panel and review section without duplicating business logic (cubits provided via context)
- MUST show `CursorConnectionCubit` banner when disconnected with remediation CTA copy PT-BR
- MUST accept `InitializeAgentSubmitPayload` extended fields needed for slug/directive when passed from parent (prepare props; full wiring in task_13)
- MUST NOT navigate with ad-hoc `MaterialPageRoute` or string literal paths
- MUST register new cubits in `OrchestratorComposition` if not already done in prior tasks
</requirements>

## Subtasks
- [x] 12.1 Create `WorkflowPrdWorkspace` layout with DS max-width tokens
- [x] 12.2 Integrate stream + review children with `BlocProvider` scope
- [x] 12.3 Add connection banner widget bound to `CursorConnectionCubit`
- [x] 12.4 Add widget tests only if explicitly required — otherwise cubit tests + analyze suffice per project workflow
- [x] 12.5 Document manual QA steps in PR description for composed workspace

## Implementation Details

See TechSpec **Component Overview** (`WorkflowPrdWorkspace`) and mirror structure of `workflow_techspec_workspace.dart` without TechSpec coming-soon body in PRD workspace.

### Relevant Files
- `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` — new
- `lib/features/orchestrator/presentation/widgets/workflow_techspec_workspace.dart` — structural reference
- `lib/features/orchestrator/presentation/widgets/workflow_phase_stepper.dart` — reuse
- `lib/app/di/orchestrator_composition.dart` — cubit providers

### Dependent Files
- `lib/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart` — task_13 shows workspace

### Related ADRs
- [ADR-002: PRD-Only MVP](../adrs/adr-002.md) — workspace scope
- [ADR-001: Native Pulse Cockpit](../adrs/adr-001.md) — composed cockpit

## Deliverables
- `WorkflowPrdWorkspace` widget tree
- Connection banner widget
- Composition updates for PRD cubits
- Unit tests on any pure layout helpers; cubit tests from 10/11 satisfy coverage **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Connection banner: disconnected state renders remediation string constant from strings class
  - [x] Workspace props: given slug and projectId, stepper shows PRD as active phase (pure helper test if extracted)
- Integration tests:
  - [ ] N/A — widget tests second order
- Test coverage target: >=80% on any new non-UI logic
- All tests must pass

## Success Criteria
- All tests passing
- `flutter analyze` passes
- Workspace composable with existing orchestrator shell for local QA
- PR-5 UI complete pending shell wiring

## Manual QA (PR description)
1. Montar `WorkflowPrdWorkspace` manualmente com um `WorkflowEntity` de teste e `repoPath` válido; confirmar stepper com fase PRD ativa e fases posteriores esmaecidas.
2. Simular `CursorConnectionCubit` em `disconnected` e verificar banner com copy de remediação PT-BR e CTA desabilitado ou acionando callback de configurações.
3. Iniciar run PRD e validar painel de stream + transição para revisão ao concluir (`pendingApproval`).
4. Editar rascunho, salvar, aprovar e rejeitar com feedback; confirmar diálogo de overwrite quando nova run chega com edição suja.
