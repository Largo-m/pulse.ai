---
status: completed
title: ADRs, artefatos e estados ausentes
type: frontend
complexity: medium
dependencies:
  - task_05
---

# ADRs, artefatos e estados ausentes

## Overview

Conecta `ListWorkflowAdrsUseCase` à workspace com `PrdAdrListSection`, alinha cards de PRD/ADR ao `restoredRunId` / `sourceRunId` e exibe estado PT-BR quando arquivo de artefato não existe no disco (mitigação PRD).

<critical>
- MVP: listar ADRs por slug do workflow; filtro fino por `sourceRunId` quando metadata ausente (TechSpec Known Risks).
- Copy em `OrchestratorStrings`; sem literais na UI.
</critical>

<requirements>
1. DEVE criar seção de ADRs na workspace usando `ListWorkflowAdrsUseCase` já registrado em `OrchestratorComposition`.
2. DEVE chamar `PrdReviewCubit.loadDraft()` / contexto de review coerente com fase `draft` ou `pendingApproval` após restore.
3. DEVE exibir `sourceRunId` na apresentação do card PRD quando approval restaurada corresponde ao `restoredRunId`.
4. DEVE mostrar estado missing-artifact PT-BR quando `ReadPrdMarkdownUseCase` ou listagem ADR falhar por arquivo ausente.
5. NÃO DEVE implementar restore de workflow TechSpec (fora de escopo MVP).
</requirements>

## Subtasks

- [x] Criar `prd_adr_list_section.dart` (ou equivalente) consumindo use case via composition/workspace
- [x] Wire `ListWorkflowAdrsUseCase` no mount da workspace (provider ou parâmetro do bundle)
- [x] Ajustar `prd_review_section.dart` / `PrdArtifactCard` para missing file e run id
- [x] Strings PT-BR para artefato ausente e títulos de seção ADR
- [x] Testes: `list_workflow_adrs_use_case` já existente + testes de review/missing path

## Implementation Details

Ver TechSpec **Artifact binding**, **PrdReviewCubit** e **Known Risks** (ADR UI sem filtro `sourceRunId`).

Paths de artefato: `{appSupport}/pulse/workflows/{projectId}/{slug}/` via `FilesystemArtifactServiceImpl` — não confundir com `.compozy/tasks/`.

### Relevant Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/domain/usecases/list_workflow_adrs_use_case.dart` | Já implementado |
| `lib/features/orchestrator/presentation/bloc/prd_review_cubit.dart` | Draft e approval |
| `lib/features/orchestrator/presentation/widgets/prd_review_section.dart` | Cards PRD |
| `lib/features/orchestrator/domain/entities/prd_approval_entity.dart` | `sourceRunId` |
| `lib/app/di/orchestrator_composition.dart` | `listWorkflowAdrsUseCase` exposto |

### Dependent Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` | Inclui nova seção |

### Related ADRs

- [ADR-001: Last Completed Session Auto-Restore](adrs/adr-001.md) — mesma run para artefatos

## Deliverables

- Seção ADR visível na workspace após restore
- Cards com estado ausente e coerência de run
- Testes unitários de strings e use case consumer (widget tests fora de escopo salvo pedido)

## Tests

### Unit tests

- [x] `ListWorkflowAdrsUseCase` com fake repo retorna N ADRs → seção recebe lista (teste de presenter/cubit leve se extraído)
- [x] Approval com `sourceRunId` igual a `restoredRunId` → card PRD indica run (via state builder test do review cubit)
- [x] Arquivo markdown ausente → estado UI usa string `missingArtifact` (key) sem throw na UI

### Integration tests

- [x] Dois workflows com ADRs distintos → listas não cruzam `workflowKey` (reutilizar padrão QA do PRD)

## Success Criteria

- Happy path PRD: log + conversa + card PRD + cards ADR referem mesma sessão restaurada
- Missing file não quebra workspace
- Testes passando; cobertura ≥ 80% em código novo da seção ADR
- `flutter analyze` e `dart format .` ok
