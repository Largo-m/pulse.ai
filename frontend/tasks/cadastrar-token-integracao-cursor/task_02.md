---
status: completed
title: DI, cubit de conexão e política do banner
type: frontend
complexity: high
dependencies:
  - task_01
---

# Task 02: DI, cubit de conexão e política do banner

## Overview

Registra os use cases na composição do orchestrator e estende `CursorConnectionCubit` para orquestrar teste de rascunho, save com gate de teste, remoção com preflight e sessão de settings. Atualiza a política do banner para estados `failure`, alinhada ao PRD de discoverability.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST registrar `ValidateCursorCredentialUseCase`, `SaveCursorCredentialUseCase` e `RemoveCursorCredentialUseCase` em `OrchestratorComposition` e injetá-los no `CursorConnectionCubit`.
- MUST estender `CursorConnectionState` com `isDraftTestPassed`, `CursorSettingsOperationStatus` e `settingsFeedbackMessageKey` (ver TechSpec "Data Models").
- MUST implementar no cubit: `testDraftCredential`, save bloqueado sem teste bem-sucedido na sessão, remove com preflight após delete, `resetSettingsSession` ao fechar modal.
- MUST mapear falhas para chaves PT-BR em `OrchestratorStrings` (nunca emitir a chave completa).
- MUST alterar `CursorConnectionBannerPolicy` para exibir banner em `disconnected` e `failure`.
- MUST NOT persistir rascunho da API key no estado do cubit (rascunho fica só no widget, task 03).
</requirements>

## Subtasks
- [x] 02.1 Estender estado e enum de operação de settings
- [x] 02.2 Implementar métodos de settings no `CursorConnectionCubit`
- [x] 02.3 Wire dos use cases em `OrchestratorComposition`
- [x] 02.4 Expandir política do banner para `failure`
- [x] 02.5 Atualizar testes do cubit e da política

## Implementation Details

Ver TechSpec "Component Overview", "Data Models" e "Development Sequencing" (passos 3–5). Fluxo save: test → flag → save → `runPreflight()` → `connected`. Fluxo remove: confirm (UI task 03) → delete → `runPreflight()` → `disconnected` ou `failure`.

### Relevant Files
- `lib/app/di/orchestrator_composition.dart` — registro e injeção dos use cases
- `lib/features/orchestrator/presentation/bloc/cursor_connection_state.dart` — novos campos
- `lib/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart` — orquestração de settings
- `lib/features/orchestrator/presentation/widgets/cursor_connection_banner_policy.dart` — `shouldShow` para failure
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — chaves de feedback (podem ser adicionadas em task 03 se preferir; cubit deve referenciar constantes existentes)

### Dependent Files
- `test/features/orchestrator/presentation/bloc/cursor_connection_cubit_test.dart` — cenários de settings
- `test/features/orchestrator/presentation/widgets/cursor_connection_banner_policy_test.dart` — failure deve mostrar banner
- `lib/features/orchestrator/presentation/widgets/prd_review_section.dart` — listener existente reage a mudanças de conexão

### Related ADRs
- [ADR-003: Test-Gated Save with Draft Credential Validation](adrs/adr-003.md) — flag `isDraftTestPassed` e save gated
- [ADR-004: Connection Banner Visible for Disconnected and Failure](adrs/adr-004.md) — política do banner
- [ADR-006: Settings Orchestration in CursorConnectionCubit](adrs/adr-006.md) — cubit como fonte única de conexão

## Deliverables
- `OrchestratorComposition` com três use cases wired no cubit
- Estado e cubit estendidos com sessão de settings
- `CursorConnectionBannerPolicy` atualizada
- Testes unitários do cubit e da política atualizados
- Cobertura ≥80% nos arquivos alterados

## Tests
- Unit tests:
  - [x] `testDraftCredential` com sucesso define `isDraftTestPassed` true e operação volta a idle
  - [x] `testDraftCredential` com 401 define flag false e `settingsFeedbackMessageKey` de unauthorized
  - [x] Save com `isDraftTestPassed` false não chama store write (permanece idle ou emite feedback de bloqueio)
  - [x] Save após teste bem-sucedido persiste, limpa flag de draft e emite `connected` após preflight
  - [x] Remove após confirmação (chamada direta ao método do cubit) executa delete e `runPreflight`, resultando em `disconnected` ou `failure`
  - [x] `resetSettingsSession` zera `isDraftTestPassed`, operação idle e feedback
  - [x] `CursorConnectionBannerPolicy`: `disconnected` → show true
  - [x] `CursorConnectionBannerPolicy`: `failure` → show true
  - [x] `CursorConnectionBannerPolicy`: `connected` → show false
- Integration tests:
  - [x] N/A para MVP
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80%
- Cubit expõe API completa para a sheet (task 03) sem persistir draft
- Banner visível em disconnected e failure
