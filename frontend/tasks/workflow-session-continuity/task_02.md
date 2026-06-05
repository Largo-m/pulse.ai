---
status: completed
title: Status na nuvem e reconciliação de run
type: backend
complexity: medium
dependencies: []
---

# Status na nuvem e reconciliação de run

## Overview

Estende `CursorPrdAgentService` com `fetchRunStatus` e implementa `ReconcilePrdRunStatusUseCase` para atualizar runs locais ainda ativos quando o usuário reabre o workflow (ADR-003). Evita UI “em progresso” obsoleta após conclusão na nuvem sem hidratar falso terminal em caso de erro de rede.

<critical>
- Leia `_prd.md` e `_techspec.md` antes de implementar.
- Consulte TechSpec "Core Interfaces", "API Endpoints" e "Integration Points" — não duplique definições de interface no corpo da task.
- Foque no **o quê**; implementação HTTP isolada no service layer.
- Testes unitários obrigatórios (service + use case).
</critical>

<requirements>
1. DEVE adicionar `Future<Either<Failure, CloudRunStatus>> fetchRunStatus(String cloudRunId)` ao contrato `CursorPrdAgentService`.
2. DEVE implementar `CloudRunStatus` com `mappedPrdRunStatus` mapeado para `PrdRunStatus` terminal ou não terminal conforme resposta GET `/v1/agents/{agentId}/runs/{runId}`.
3. DEVE atualizar `CursorPrdAgentServiceImpl`, `cursor_prd_agent_service_stub.dart` e fakes de teste; stub pode retornar `Left` failure para cenários de teste.
4. DEVE implementar `ReconcilePrdRunStatusUseCase` que, dado `PrdRunEntity` não terminal com `cloudRunId`, chama `fetchRunStatus`, persiste via `PrdRunRepository.updateRun` e sincroniza fase do workflow quando aplicável.
5. DEVE pular chamada à nuvem quando credencial ausente (`CursorCredentialStoreService` / connection gate existente) e retornar resultado explícito de skip.
6. NÃO DEVE emitir estado de terminal restaurado na UI em falha de rede/401 — apenas atualizar persistência quando o mapeamento for confiável.
</requirements>

## Subtasks

- [x] Adicionar `CloudRunStatus` e método `fetchRunStatus` no domínio/service
- [x] Implementar GET no `CursorPrdAgentServiceImpl` com testes de status 200, 404, 401
- [x] Atualizar stub e `FakeCursorPrdAgentService` / fakes de lifecycle
- [x] Criar `reconcile_prd_run_status_use_case.dart` com `Either<Failure, …>` ou tipo de resultado documentado
- [x] Testes: cloud completed → run terminal + fase atualizada; still running → sem restore; sem credencial → skip

## Implementation Details

Ver TechSpec **API Endpoints**, **Integration Points** (auth, errors) e **ReconcilePrdRunStatusUseCase** na tabela de componentes.

Reutilizar padrões de `cursor_prd_agent_service_impl_test.dart` para HTTP fake. Use case depende de `PrdRunRepository`, `WorkflowRepository` (se fase sync já existir em use cases similares) e `CursorPrdAgentService`.

### Relevant Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/domain/service/cursor_prd_agent_service.dart` | Contrato a estender |
| `lib/features/orchestrator/service/cursor_prd_agent_service_impl.dart` | Implementação HTTP |
| `lib/features/orchestrator/service/cursor_prd_agent_service_stub.dart` | Stub de dev |
| `test/features/orchestrator/service/cursor_prd_agent_service_impl_test.dart` | Padrão de testes HTTP |
| `lib/features/orchestrator/domain/repositories/prd_run_repository.dart` | `updateRun` |
| `lib/features/orchestrator/domain/entities/prd_run_status_extensions.dart` | `isTerminal` |

### Dependent Files

| Arquivo | Motivo |
|---------|--------|
| `lib/app/di/orchestrator_composition.dart` | Registro na task 04 |
| `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` | Chamada no `bindWorkflow` na task 04 |

### Related ADRs

- [ADR-003: Cloud Run Status Reconciliation on Workflow Open](adrs/adr-003.md)

## Deliverables

- `fetchRunStatus` em interface, impl, stub e fakes
- `ReconcilePrdRunStatusUseCase` + testes em `test/features/orchestrator/domain/usecases/reconcile_prd_run_status_use_case_test.dart`
- Cobertura ≥ 80% nas classes novas/alteradas do service e use case

## Tests

### Unit tests

- [x] GET retorna status mapeado para `PrdRunStatus.completed` → `CloudRunStatus.mappedPrdRunStatus` completed
- [x] GET 404 → `Left` failure tipado (sem atualizar run local para completed)
- [x] GET 401 → `Left` failure; run local permanece `running`
- [x] Run sem `cloudRunId` → reconcile não chama HTTP
- [x] Credencial ausente → outcome skip, `updateRun` não chamado com status terminal inventado
- [x] Cloud `completed` + run local `running` → `updateRun` com status terminal e workflow phase coerente

### Integration tests

- [ ] Nenhum nesta task

## Success Criteria

- Contrato cloud alinhado ao TechSpec; testes de impl espelhando padrão existente
- Use case de reconcile testado para completed, running e skip sem credencial
- Todos os testes passando; cobertura ≥ 80% no escopo da task
- `flutter analyze` limpo
