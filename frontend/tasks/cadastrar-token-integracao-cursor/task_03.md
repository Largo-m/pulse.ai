---
status: completed
title: Strings PT-BR e UI modal de configuração Cursor
type: frontend
complexity: high
dependencies:
  - task_02
---

# Task 03: Strings PT-BR e UI modal de configuração Cursor

## Overview

Adiciona todo o copy PT-BR do fluxo de integração Cursor e os widgets de apresentação: sheet modal de settings e diálogo de confirmação de remoção. A UI consome `CursorConnectionCubit` via scope existente e mantém o rascunho da chave apenas em `TextEditingController` local.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST adicionar strings em `OrchestratorStrings` para formulário, botões Test/Save/Remove, estados configurado, erros de settings, confirmação destrutiva e label do link à documentação oficial Cursor (URL em constante, texto PT-BR).
- MUST criar `CursorIntegrationSettingsSheet` com input mascarado, ações Test/Save/Remove, indicador pós-save sem revelar chave, e link externo.
- MUST criar `CursorIntegrationRemoveConfirmDialog` e abrir antes de chamar remove no cubit (ADR-005).
- MUST resetar sessão do cubit (`resetSettingsSession`) e limpar controller ao fechar o modal.
- MUST resetar `isDraftTestPassed` quando o texto do draft mudar.
- MUST usar apenas tokens/átomos do design system; sem literais de UI nos widgets.
- MUST apresentar o sheet como modal (sem nova rota), seguindo padrão de modais do orchestrator (ex. `initialize_agent_modal.dart`).
</requirements>

## Subtasks
- [x] 03.1 Definir constantes PT-BR em `OrchestratorStrings` e testes de strings
- [x] 03.2 Implementar `CursorIntegrationSettingsSheet` com controller local e BlocBuilder
- [x] 03.3 Implementar diálogo de confirmação de remoção
- [x] 03.4 Conectar habilitação de Save ao estado `isDraftTestPassed` e operações em progresso
- [x] 03.5 Garantir dispose do controller e reset de sessão ao fechar

## Implementation Details

Ver TechSpec "Component Overview" (sheet e dialog) e ADR-002 (modal sem `RoutePaths`). Save habilitado somente após teste na sessão; Remove dispara dialog → cubit.remove. Após save bem-sucedido, UI mostra estado “configurado” sem exibir a chave.

### Relevant Files
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — copy centralizado
- `lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart` — referência de padrão modal no orchestrator
- `lib/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart` — métodos consumidos pela sheet
- `lib/features/orchestrator/presentation/widgets/cursor_connection_banner.dart` — CTA futuro (wiring na task 04)

### Dependent Files
- `test/features/orchestrator/presentation/orchestrator_strings_test.dart` — novas chaves não vazias e PT-BR
- `lib/features/orchestrator/presentation/orchestrator_placeholder_feedback.dart` — não reutilizar para fluxo real de settings

### Related ADRs
- [ADR-001: Hybrid Cursor Credential Entry via Shared Settings Surface](adrs/adr-001.md) — superfície única (preparada para task 04)
- [ADR-002: Cursor Settings as Modal Sheet Without Dedicated Route](adrs/adr-002.md) — modal sem rota
- [ADR-005: Confirmation Dialog Before Credential Removal](adrs/adr-005.md) — confirm antes de delete

## Deliverables
- Novas entradas em `OrchestratorStrings` + testes
- `cursor_integration_settings_sheet.dart` e `cursor_integration_remove_confirm_dialog.dart`
- Função ou helper para abrir o sheet (pode ficar na sheet ou na page — task 04 usa o entry point)
- Cobertura ≥80% em strings; widgets sem widget test no MVP

## Tests
- Unit tests:
  - [x] Cada nova constante em `OrchestratorStrings` é não vazia
  - [x] Constantes de erro e confirmação estão em PT-BR (sem placeholders em inglês)
  - [x] URL de documentação é constante nomeada e não vazia
- Integration tests:
  - [ ] Plano manual: colar chave → Test com sucesso → Save habilitado → Save → status connected
  - [ ] Plano manual: Remove → dialog → confirmar → banner disconnected
  - [ ] Plano manual: fechar modal limpa rascunho e reseta sessão do cubit
- Test coverage target: >=80% (strings); widgets validados manualmente
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% em `orchestrator_strings` e classes de strings relacionadas
- Sheet e dialog compilam sem literais de UI inline
- Save desabilitado até teste bem-sucedido na sessão
- Remoção exige confirmação explícita
