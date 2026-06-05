---
status: completed
title: "Camada Git: service impl, use case e testes unitários"
type: backend
complexity: medium
dependencies:
  - task_01
---

# Task 2: Camada Git: service impl, use case e testes unitários

## Overview

Implementa a leitura real de branches locais via libgit2 (`git2dart`) na camada `service/`, expõe um use case fino no domínio e cobre cenários de sucesso, não-repositório, falha e HEAD detached com testes unitários e doubles injetáveis.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST implementar `LocalGitBranchesServiceImpl` em `service/` usando git2dart, com typedef `RepositoryOpener` injetável (default `Repository.open`).
- MUST mapear `GitException` / `ArgumentError` para `notGitRepository` ou `failure` conforme TechSpec **Service implementation sketch**.
- MUST retornar `branches` na ordem libgit2 (`branchesLocal`) e `headBranchName` do shorthand quando HEAD não estiver detached; quando `isHeadDetached`, `headBranchName` MUST ser `null` com `branches` ainda populadas.
- MUST garantir dispose/`free` do repositório em `try/finally`.
- MUST implementar `ListLocalGitBranchesUseCase` delegando `absolutePath` ao service.
- MUST criar `FakeLocalGitBranchesService` para testes do use case e cubit (task_03).
- MUST NOT alterar presentation, composition ou modal nesta tarefa.
</requirements>

## Subtasks
- [x] 2.1 Implementar `LocalGitBranchesServiceImpl` com opener injetável
- [x] 2.2 Implementar `ListLocalGitBranchesUseCase`
- [x] 2.3 Criar `FakeLocalGitBranchesService` em `test/`
- [x] 2.4 Testes do service impl (opener fake: sucesso, não-Git, exceção, detached HEAD)
- [x] 2.5 Testes do use case (delegação de path e propagação de outcome)

## Implementation Details

Ver TechSpec **Service implementation sketch**, **Core Interfaces** e **Testing Approach → Unit Tests** (`LocalGitBranchesServiceImpl`, `ListLocalGitBranchesUseCase`).

Padrão existente: `lib/features/orchestrator/service/local_directory_picker_service_impl.dart` com callback injetável; testes em `test/features/orchestrator/service/local_directory_picker_service_impl_test.dart`.

Spike ≤30 min: confirmar API `Branch.name` e dispose do repositório na versão instalada de git2dart.

### Relevant Files
- `lib/features/orchestrator/domain/service/local_git_branches_service.dart` — contrato (task_01)
- `lib/features/orchestrator/service/local_directory_picker_service_impl.dart` — padrão de impl + injeção
- `test/features/orchestrator/domain/usecases/fake_local_directory_picker_service.dart` — padrão de fake
- `test/features/orchestrator/service/local_directory_picker_service_impl_test.dart` — padrão de teste de service

### Dependent Files
- `lib/features/orchestrator/presentation/bloc/initialize_agent_branches_cubit.dart` — consumirá o use case (task_03)
- `lib/app/di/orchestrator_composition.dart` — registrará service e use case (task_03)

### Related ADRs
- [ADR-002: git2dart (libgit2)](../adrs/adr-002.md) — rejeita CLI e parsing manual de `.git`
- [ADR-001: Reactive Local Branch Loading](../adrs/adr-001.md) — apenas branches locais, sem remotes

## Deliverables
- `local_git_branches_service_impl.dart` funcional com opener injetável
- `list_local_git_branches_use_case.dart`
- `fake_local_git_branches_service.dart`
- Testes unitários do impl e do use case
- Unit tests com 80%+ coverage **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Service impl: `absolutePath` válido retorna `success` com lista de nomes e `headBranchName` quando HEAD aponta para branch local
  - [x] Service impl: path sem repositório Git retorna `notGitRepository`
  - [x] Service impl: opener lança exceção mapeável retorna `failure` (não `success`)
  - [x] Service impl: repositório com `isHeadDetached == true` retorna `success`, `branches` não vazia, `headBranchName == null`
  - [x] Use case: `call('/path/to/repo')` invoca `listLocalBranches` no service com o mesmo path
  - [x] Use case: outcome do fake (`notGitRepository`, `failure`) é repassado sem alteração
- Integration tests:
  - [ ] N/A para MVP (PRD: QA manual para fluxo completo)
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% em impl, use case e fakes
- Nenhum import de git2dart em `domain/` ou `presentation/`
- Opener injetável permite testes sem binário libgit2 real quando usar fake
