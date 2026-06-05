---
status: completed
title: Estado de sessão, cubit e DI
type: frontend
complexity: high
dependencies:
  - task_01
  - task_02
  - task_03
---

# Estado de sessão, cubit e DI

## Overview

Estende `PrdWorkflowState` com `PrdSessionViewMode` e campos restaurados; torna `bindWorkflow` assíncrono executando reconcile → restore; refatora o caminho live para `PrdStreamEventMapper`; registra use cases em `OrchestratorComposition` e injeta no `PrdWorkflowCubit` (ADR-001, ADR-003, ADR-004).

<critical>
- Leia `_prd.md`, `_techspec.md` e ADRs 001, 003, 004.
- `bindWorkflow` DEVE ser async; testes com `bloc_test` onde aplicável.
- `startRun` com snapshot restaurado DEVE manter overlay (`restoredWithActiveRun`) sem limpar linhas restauradas até conclusão.
</critical>

<requirements>
1. DEVE existir `enum PrdSessionViewMode` com `empty`, `restored`, `inProgressOnly`, `restoreFailed`, `restoredWithActiveRun`.
2. DEVE estender `PrdWorkflowState` com `sessionViewMode`, `restoredRunId`, buffers restaurados (linhas/conversa) e flags necessários ao `copyWith`.
3. `bindWorkflow` DEVE: listar runs; se último não terminal com `cloudRunId` → `ReconcilePrdRunStatusUseCase`; depois `RestoreLastFinalizedPrdSessionUseCase`; emitir modo correto.
4. DEVE mapear `Left` de restore para `restoreFailed` com chave de mensagem (string key, não literal PT-BR no cubit).
5. DEVE refatorar `_appendBufferedLine` / mapeamento SSE para usar `PrdStreamEventMapper`.
6. `startRun` DEVE emitir `restoredWithActiveRun` quando já há snapshot restaurado, sem zerar `streamLines` restauradas conforme ADR-004.
7. DEVE registrar `RestoreLastFinalizedPrdSessionUseCase` e `ReconcilePrdRunStatusUseCase` em `OrchestratorComposition` e `createPrdWorkspaceCubitBundle`.
</requirements>

## Subtasks

- [x] Adicionar `PrdSessionViewMode` e campos em `prd_workflow_state.dart`
- [x] Injetar use cases no cubit; implementar `bindWorkflow` async
- [x] Refatorar live stream para mapper da task 01
- [x] Ajustar `startRun` para modo overlay com run ativo
- [x] Atualizar `prd_workflow_cubit_test.dart` com cenários restore/reconcile/failed/retry
- [x] Wire DI em `orchestrator_composition.dart` e bundle

## Implementation Details

Ver TechSpec **PrdWorkflowCubit**, sequence diagram em **System Architecture**, e **Impact Analysis** para cubit/composition.

Retry de restore: método público que re-invoca bind ou flag que workspace chama — expor no cubit o que a task 05 precisa para botão retry.

### Relevant Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/bloc/prd_workflow_state.dart` | Extensão de estado |
| `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` | Orquestração bind |
| `lib/app/di/orchestrator_composition.dart` | DI e `PrdWorkspaceCubitBundle` |
| `test/features/orchestrator/presentation/bloc/prd_workflow_cubit_test.dart` | Padrão com fakes e `_ControllablePrdAgentService` |
| Use cases das tasks 02 e 03 | Dependências injetadas |

### Dependent Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` | Consome novos campos de estado (task 05) |
| `lib/features/orchestrator/presentation/widgets/prd_workflow_stream_panel.dart` | Renderiza modos |

### Related ADRs

- [ADR-001: Last Completed Session Auto-Restore](adrs/adr-001.md)
- [ADR-003: Cloud Run Status Reconciliation on Workflow Open](adrs/adr-003.md)
- [ADR-004: Restore Presentation and Buffer Policy](adrs/adr-004.md)

## Deliverables

- Estado e cubit atualizados; DI completo
- Testes de cubit para restored, inProgressOnly, restoreFailed, restoredWithActiveRun, reconcile→restore
- Cobertura ≥ 80% em cubit/state alterados

## Tests

### Unit tests

- [x] `bindWorkflow` com run terminal seedado → emite `sessionViewMode` restored e `streamLines` não vazias
- [x] Último run `running` após reconcile ainda running → `inProgressOnly`, `streamLines` vazias
- [x] Restore retorna `Left` → `restoreFailed` com failure message key
- [x] Sem runs terminais → `empty`
- [x] `startRun` com estado restored → `restoredWithActiveRun` e linhas restauradas preservadas
- [x] Reconcile atualiza run para `completed` no mesmo bind → restore subsequente preenche linhas

### Integration tests

- [x] Fake `PrdRunRepository` + cubit: open workflow → `streamLines.length` > 0 e conversa no estado > 0

## Success Criteria

- `bindWorkflow` não deixa workspace vazio após navegação quando há run terminal persistido
- Todos os testes passando; cobertura ≥ 80% no cubit
- `flutter analyze` e `dart format .` aplicados
- Sem literais PT-BR no cubit (apenas keys para strings)
