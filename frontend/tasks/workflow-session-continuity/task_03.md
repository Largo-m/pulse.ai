---
status: completed
title: Use case de restauração da última sessão
type: backend
complexity: medium
dependencies:
  - task_01
---

# Use case de restauração da última sessão

## Overview

Implementa `RestoreLastFinalizedPrdSessionUseCase` que resolve o run terminal mais recente por `workflowKey`, carrega eventos do Hive e produz `PrdSessionSnapshot` (linhas + conversa) via `PrdStreamEventMapper` (ADR-001, ADR-002). Separa `empty` (sem run terminal) de falha de repositório (`Left`).

<critical>
- Leia `_prd.md` e `_techspec.md`.
- Use `PrdStreamEventMapper` da task 01 — não reimplemente regras de conversa.
- Testes unitários obrigatórios com `FakePrdRunRepository`.
</critical>

<requirements>
1. DEVE existir `RestorePrdSessionRequest` com `workflowKey`, `workflowDirective` e `WorkflowEntity` opcional para sync de fase.
2. DEVE existir `PrdSessionSnapshot` com `runId`, `runStatus`, `terminalLines`, `conversationMessages`.
3. DEVE usar `listRunsForWorkflow` (ordem `startedAt` desc) e selecionar o primeiro run com `status.isTerminal`.
4. DEVE retornar falha `Left` quando repositório falhar; DEVE distinguir “sem terminal” (snapshot vazio ou tipo de resultado acordado com cubit na task 04) de erro de IO.
5. DEVE carregar eventos via `listStreamEvents(runId)` e delegar mapeamento e cap 200 ao mapper.
6. NÃO DEVE chamar API cloud nesta task (reconcile é task 02 / cubit task 04).
</requirements>

## Subtasks

- [x] Criar `restore_last_finalized_prd_session_use_case.dart` e tipos de request/snapshot
- [x] Implementar algoritmo de seleção do run terminal mais recente
- [x] Integrar `PrdStreamEventMapper` com directive e `run.feedback`
- [x] Testes: múltiplos runs, cap 200, sem terminal, falha de repo
- [x] Garantir que dois `workflowKey` distintos não misturam eventos (QA PRD)

## Implementation Details

Ver TechSpec **Restore selection algorithm** e interface `RestoreLastFinalizedPrdSessionUseCase`.

Se o run mais recente for não terminal, o use case pode retornar `Left` específico ou tipo de resultado que o cubit interpreta como `inProgressOnly` — alinhar com task 04 na implementação (documentar no código via tipo de retorno, não comentários).

### Relevant Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/domain/repositories/prd_run_repository.dart` | `listRunsForWorkflow`, `listStreamEvents` |
| `lib/features/orchestrator/data/repositories/prd_run_repository_impl.dart` | Ordenação existente |
| `lib/features/orchestrator/presentation/prd_stream_event_mapper.dart` | Task 01 |
| `test/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart` | Seed de runs/eventos |

### Dependent Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` | Consumo no bind (task 04) |

### Related ADRs

- [ADR-001: Last Completed Session Auto-Restore](adrs/adr-001.md)
- [ADR-002: Conversation Derived from Stream Events](adrs/adr-002.md)
- [ADR-004: Restore Presentation and Buffer Policy](adrs/adr-004.md)

## Deliverables

- Use case + request/snapshot types
- Testes unitários com repositório fake pré-seedado
- Cobertura ≥ 80% no use case

## Tests

### Unit tests

- [x] Dois runs: `running` (mais recente) + `completed` anterior → após reconcile simulado fora do escopo, sem terminal no topo: comportamento definido com cubit (run não terminal primeiro → não produz snapshot terminal)
- [x] Run `completed` com 50 eventos → snapshot com 50 linhas e conversa com contagem > 0 quando há `assistant`
- [x] 300 eventos persistidos → snapshot usa no máximo 200 últimos por sequence
- [x] Nenhum run terminal → resultado vazio sem `Left` de falha de sistema
- [x] `listStreamEvents` retorna `Left` → `Left` failure propagado
- [x] `workflowKey` A vs B com runs diferentes → snapshots isolados

### Integration tests

- [x] Fake repo pré-seedado: após `call`, `terminalLines.length` > 0 e `conversationMessages` coerentes com mesmo `runId`

## Success Criteria

- Algoritmo de seleção conforme TechSpec
- Testes passando; cobertura ≥ 80%
- Sem dependência de UI ou cubit
