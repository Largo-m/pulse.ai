---
status: completed
title: Backend de validação e ciclo de vida da credencial Cursor
type: backend
complexity: high
dependencies: []
---

# Task 01: Backend de validação e ciclo de vida da credencial Cursor

## Overview

Esta task entrega a base de domínio e serviço para validar uma chave Cursor em rascunho sem persistir, e para gravar ou remover a credencial no armazenamento seguro. Sem ela, o cubit e a UI de settings não conseguem testar, salvar ou desconectar com segurança.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST adicionar `preflightCredential(String apiKey)` em `CursorPrdAgentService` e implementação que chama `GET /v1/me` com auth one-off, sem `write` no store (ver TechSpec "Core Interfaces" e "Integration Points").
- MUST estender o cliente HTTP para suportar requisição com chave explícita, reutilizando `TransientHttpRetry` e mapeamento 401 → `unauthorized`, 5xx → `network`, demais non-2xx → `unknown`.
- MUST criar `ValidateCursorCredentialUseCase`, `SaveCursorCredentialUseCase` e `RemoveCursorCredentialUseCase` conforme TechSpec "Core Interfaces".
- MUST atualizar stub, `FakeCursorPrdAgentService` e testes de `CursorPrdAgentServiceImpl` para o novo contrato.
- MUST NOT logar ou persistir a chave de rascunho no store durante validação de draft.
</requirements>

## Subtasks
- [x] 01.1 Adicionar `preflightCredential` na interface e na implementação do agente Cursor
- [x] 01.2 Permitir `GET /v1/me` com credencial explícita no cliente HTTP (sem leitura temporária do store)
- [x] 01.3 Implementar os três use cases de domínio (validate, save, remove)
- [x] 01.4 Alinhar stub e fake do agente ao novo método
- [x] 01.5 Cobrir cenários de sucesso e falha com testes unitários

## Implementation Details

Ver TechSpec seções "Implementation Design", "Integration Points" e "Development Sequencing" (passos 1–2). Padrão de falha: reutilizar `CursorConnectionFailure` e `Either<Failure, void>` como em `preflight()` existente.

### Relevant Files
- `lib/features/orchestrator/domain/service/cursor_prd_agent_service.dart` — contrato a estender
- `lib/features/orchestrator/service/cursor_prd_agent_service_impl.dart` — implementação de preflight draft e stored
- `lib/features/orchestrator/service/cursor_cloud_agent_http_client_impl.dart` — auth Basic one-off para draft
- `lib/features/orchestrator/service/cursor_prd_agent_service_stub.dart` — comportamento local em dev
- `lib/features/orchestrator/domain/service/cursor_credential_store_service.dart` — contrato usado por save/remove
- `lib/features/orchestrator/service/cursor_credential_store_service_impl.dart` — chave `cursor_prd_agent_credential`
- `lib/core/error/cursor_connection_failure.dart` — códigos de falha existentes

### Dependent Files
- `lib/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart` — espelhar `preflightCredential`
- `test/features/orchestrator/service/fakes/fake_cursor_cloud_agent_http_client.dart` — cenários HTTP de draft
- `test/features/orchestrator/service/cursor_prd_agent_service_impl_test.dart` — estender cobertura de preflight draft

### Related ADRs
- [ADR-003: Test-Gated Save with Draft Credential Validation](adrs/adr-003.md) — validação sem persistir até save

## Deliverables
- `preflightCredential` em interface, impl, stub e fake
- Três use cases em `lib/features/orchestrator/domain/usecases/`
- Override de auth no HTTP client para draft
- Testes unitários dos use cases e de `preflightCredential` na impl
- Cobertura ≥80% nos arquivos novos ou alterados desta task

## Tests
- Unit tests:
  - [x] `ValidateCursorCredentialUseCase`: chave válida retorna sucesso (`Right`)
  - [x] `ValidateCursorCredentialUseCase`: resposta 401 retorna `CursorConnectionFailure` unauthorized
  - [x] `ValidateCursorCredentialUseCase`: resposta 5xx retorna falha network
  - [x] `ValidateCursorCredentialUseCase`: chave vazia retorna falha apropriada (missing ou validação de entrada)
  - [x] `SaveCursorCredentialUseCase`: persiste via `FakeCursorCredentialStoreService.storedCredential`
  - [x] `RemoveCursorCredentialUseCase`: remove credencial do fake store
  - [x] `CursorPrdAgentServiceImpl.preflightCredential`: mapeia status HTTP como `preflight()` para 401, 5xx e sucesso
- Integration tests:
  - [x] N/A para MVP (projeto adia widget tests)
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80%
- Draft `GET /v1/me` funciona sem write no store
- Save/remove delegam apenas ao store, sem lógica de UI
