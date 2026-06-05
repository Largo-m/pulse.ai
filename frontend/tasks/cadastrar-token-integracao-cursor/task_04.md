---
status: completed
title: Wiring da engrenagem, banner e workspace do orchestrator
type: frontend
complexity: medium
dependencies:
  - task_03
---

# Task 04: Wiring da engrenagem, banner e workspace do orchestrator

## Overview

Conecta os pontos de entrada do PRD — ícone de configurações na top bar e CTA do banner — ao mesmo sheet modal de integração Cursor. Substitui apenas o handler da engrenagem; placeholders de workspaces e ajuda permanecem inalterados.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST passar `onOpenCursorSettings` de `orchestrator_page` para `WorkflowPrdWorkspace` e para o banner.
- MUST alterar `OrchestratorAppTopBar` para aceitar `onOpenCursorSettings` em vez de usar `onPlaceholder` para a engrenagem.
- MUST abrir `CursorIntegrationSettingsSheet` (modal) a partir da engrenagem e do CTA do banner — mesma superfície (ADR-001).
- MUST NOT alterar `RoutePaths` nem registrar nova rota.
- MUST NOT wire `PrdWorkflowCubit.startRun()` na UI (fora de escopo).
- MUST executar `flutter analyze`, `dart format .` e suite de testes unitários ao concluir.
</requirements>

## Subtasks
- [x] 04.1 Adicionar callback `onOpenCursorSettings` na top bar e na page
- [x] 04.2 Propagar callback no `WorkflowPrdWorkspace` e no `CursorConnectionBanner`
- [x] 04.3 Implementar abertura do modal de settings nos dois entry points
- [x] 04.4 Verificar que placeholders restantes da top bar não foram alterados
- [x] 04.5 Rodar analyze, format e testes do projeto

## Implementation Details

Ver TechSpec "Impact Analysis" (orchestrator_page, OrchestratorAppTopBar, workflow_prd_workspace). Gap atual: `WorkflowPrdWorkspace` já declara `onOpenCursorSettings` mas `orchestrator_page` não passa o parâmetro; banner usa `onOpenSettings` null.

### Relevant Files
- `lib/features/orchestrator/presentation/pages/orchestrator_page.dart` — composição e callbacks
- `lib/features/orchestrator/presentation/widgets/orchestrator_app_top_bar.dart` — engrenagem
- `lib/features/orchestrator/presentation/widgets/workflow_prd_workspace.dart` — banner + preflight no mount
- `lib/features/orchestrator/presentation/widgets/cursor_connection_banner.dart` — CTA settings
- `lib/features/orchestrator/presentation/widgets/cursor_integration_settings_sheet.dart` — destino do modal (task 03)

### Dependent Files
- `lib/main.dart` — scope do `OrchestratorComposition` já provê cubit
- `test/features/orchestrator/presentation/bloc/prd_review_cubit_test.dart` — gate de approve inalterado; smoke opcional se houver testes de router/page

### Related ADRs
- [ADR-001: Hybrid Cursor Credential Entry via Shared Settings Surface](adrs/adr-001.md) — dois entry points, um sheet
- [ADR-002: Cursor Settings as Modal Sheet Without Dedicated Route](adrs/adr-002.md) — sem GoRouter

## Deliverables
- Top bar, page e workspace wired com o mesmo handler de abertura do sheet
- CTA do banner funcional quando policy exibe o banner
- `flutter analyze` limpo e `dart format .` aplicado
- Testes unitários existentes do orchestrator passando

## Tests
- Unit tests:
  - [x] Testes existentes de `cursor_connection_banner_policy`, `cursor_connection_cubit` e strings continuam passando após wiring
  - [x] Se existir teste de `OrchestratorComposition` ou DI, validar que cubit ainda é provido no scope
- Integration tests:
  - [ ] Manual: engrenagem abre sheet de Cursor (não snackbar “em breve”)
  - [ ] Manual: banner disconnected/failure → CTA abre o mesmo sheet
  - [ ] Manual: após save, banner some em connected; após remove, banner reaparece
- Test coverage target: >=80% (sem regressão nos pacotes alterados)
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% sem regressão
- Engrenagem e banner abrem a mesma configuração Cursor
- `flutter analyze` sem issues
- PRD: admin completa cadastro em uma sessão via UI in-app
