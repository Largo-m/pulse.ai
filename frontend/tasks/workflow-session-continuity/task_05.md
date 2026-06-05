---
status: completed
title: Workspace PRD modos de sessão e conversa
type: frontend
complexity: high
dependencies:
  - task_04
---

# Workspace PRD modos de sessão e conversa

## Overview

Atualiza `WorkflowPrdWorkspace` e widgets relacionados para renderizar modos de sessão (vazio, restaurado, só em progresso, falha com retry, overlay de nova run), coluna de conversa derivada do estado e strings PT-BR em `OrchestratorStrings` (PRD UX + ADR-004).

<critical>
- Nenhum texto visível ao usuário como literal em widgets — apenas `OrchestratorStrings`.
- Sem `setState`; usar Bloc/Cubit e padrões existentes (`ValueNotifier` / atoms se necessário).
- Design system: tokens em `lib/shared/`, sem magic numbers.
</critical>

<requirements>
1. DEVE adicionar constantes PT-BR em `OrchestratorStrings` para empty, in-progress only, restore error, new-run overlay e rótulos de conversa.
2. DEVE renderizar terminal restaurado a partir de `PrdWorkflowState.streamLines` / buffers restaurados conforme modo.
3. DEVE mostrar affordance in-progress sem logs parciais quando `inProgressOnly`.
4. DEVE mostrar empty state distinto de `restoreFailed` com mensagem e ação retry (re-bind via cubit).
5. DEVE exibir lista de conversa (`PrdConversationMessageUiModel`) separada visualmente do editor de review.
6. DEVE exibir banner de overlay quando `restoredWithActiveRun` durante run ativo.
7. NÃO DEVE usar navegação ad-hoc; manter rotas existentes.
</requirements>

## Subtasks

- [x] Estender `orchestrator_strings.dart` com chaves de sessão
- [x] Atualizar `workflow_prd_workspace.dart` para layout conversa + terminal + modos
- [x] Ajustar `prd_workflow_stream_panel.dart` para estados in-progress / restored / failed
- [x] Criar widget de lista de conversa (feature-local) consumindo estado do cubit
- [x] Criar widget de banner overlay nova run
- [x] Testes unitários de strings novas; cubit já coberto na task 04

## Implementation Details

Ver TechSpec **WorkflowPrdWorkspace**, **User Experience** (happy path, in-progress, error) e PRD **Accessibility**.

`WorkflowUserPromptBubble` hoje só mostra directive — conversa restaurada usa lista dedicada, não substituir bubble sem critério de produto.

### Relevant Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` | Shell da workspace |
| `lib/features/orchestrator/presentation/widgets/prd_workflow_stream_panel.dart` | Painel de log |
| `lib/features/orchestrator/presentation/widgets/workflow_terminal_log.dart` | Render de linhas |
| `lib/features/orchestrator/presentation/orchestrator_strings.dart` | Copy PT-BR |
| `lib/features/orchestrator/presentation/bloc/prd_workflow_state.dart` | Modos de sessão |
| `test/features/orchestrator/presentation/orchestrator_strings_test.dart` | Se existir padrão de teste de strings |

### Dependent Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/widgets/prd_review_section.dart` | Layout adjacente (task 06) |

### Related ADRs

- [ADR-001: Last Completed Session Auto-Restore](adrs/adr-001.md)
- [ADR-004: Restore Presentation and Buffer Policy](adrs/adr-004.md) — sem banner “restored from date”

## Deliverables

- UI de workspace alinhada aos modos do cubit
- Strings PT-BR centralizadas
- Testes de strings (e cubit integration se adicionado widget smoke via state builders)

## Tests

### Unit tests

- [x] Novas constantes `OrchestratorStrings` não vazias e em PT-BR
- [x] Mapper de key `restoreFailed` → string de erro exibível (via strings test)

### Integration tests

- [x] Com cubit fake injetado em teste de widget **somente se** projeto adotar — caso contrário validar via cubit tests da task 04

## Success Criteria

- Reabrir workflow com histórico mostra log + conversa sem painel vazio
- In-progress não mostra linhas parciais
- Falha de restore mostra mensagem PT-BR e retry funcional
- `grep` sem `Text('` literais novos em widgets tocados
- `flutter analyze` limpo
