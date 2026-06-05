---
status: completed
title: "Fundação: git2dart, contrato de domínio, strings e payload"
type: chore
complexity: medium
dependencies: []
---

# Task 1: Fundação: git2dart, contrato de domínio, strings e payload

## Overview

Estabelece as bases da feature sem lógica de carregamento: dependência nativa `git2dart`, contrato de domínio para enumeração de branches locais, cópia PT-BR dos estados do dropdown e o DTO de submissão do modal. Nenhuma outra tarefa pode avançar na camada Git ou na UI de branches sem este pacote de artefatos.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST adicionar `git2dart` em `pubspec.yaml` com versão fixada e executar `flutter pub get` com sucesso no desktop alvo (macOS primeiro).
- MUST criar `LocalGitBranchesOutcome`, `LocalGitBranchesResult` e `LocalGitBranchesService` em `domain/service/` sem importar git2dart ou Flutter no domínio.
- MUST adicionar em `OrchestratorStrings` as chaves `initializeAgentBranchesLoading`, `initializeAgentBranchesNotGit` e `initializeAgentBranchesLoadFailed` em PT-BR, mais semantics de acessibilidade quando aplicável.
- MUST criar `InitializeAgentSubmitPayload` com `agentName`, `coreDirective`, `projectId` e `branchName`.
- MUST NOT implementar service impl, cubit ou alterações no modal nesta tarefa.
</requirements>

## Subtasks
- [x] 1.1 Adicionar e validar dependência `git2dart` no `pubspec.yaml`
- [x] 1.2 Criar contrato de domínio `LocalGitBranchesService` e tipos de resultado
- [x] 1.3 Adicionar strings PT-BR para loading, não-Git e falha de carga
- [x] 1.4 Criar modelo `InitializeAgentSubmitPayload`
- [x] 1.5 Atualizar testes de strings para as novas chaves

## Implementation Details

Ver TechSpec seções **Core Interfaces**, **Data Models** (`InitializeAgentSubmitPayload`) e **Status → UI mapping** para nomes de constantes e outcomes.

Arquivos a criar ou modificar:
- `pubspec.yaml`
- `lib/features/orchestrator/domain/service/local_git_branches_service.dart`
- `lib/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart`
- `lib/features/orchestrator/presentation/orchestrator_strings.dart`
- `test/features/orchestrator/presentation/orchestrator_strings_test.dart`

### Relevant Files
- `pubspec.yaml` — adicionar dependência nativa git2dart
- `lib/features/orchestrator/domain/service/local_directory_picker_service.dart` — padrão de interface em `domain/service/`
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — strings existentes do modal (`initializeAgentBranchLabel`, etc.)
- `test/features/orchestrator/presentation/orchestrator_strings_test.dart` — padrão de validação PT-BR e não-vazio

### Dependent Files
- `lib/features/orchestrator/service/local_git_branches_service_impl.dart` — consumirá o contrato (task_02)
- `lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart` — consumirá strings e payload (task_04)

### Related ADRs
- [ADR-002: git2dart (libgit2)](../adrs/adr-002.md) — escolha da dependência nativa
- [ADR-001: Reactive Local Branch Loading](../adrs/adr-001.md) — escopo metadata-only e estados de UI previstos nas strings

## Deliverables
- `git2dart` resolvido em `pubspec.yaml` com `flutter pub get` bem-sucedido
- Contrato `LocalGitBranchesService` + `LocalGitBranchesResult` no domínio
- Três novas constantes em `OrchestratorStrings` (loading, não-Git, falha)
- `InitializeAgentSubmitPayload` criado
- Unit tests com 80%+ coverage **(REQUIRED)** — `orchestrator_strings_test.dart` atualizado
- N/A integração HTTP

## Tests
- Unit tests:
  - [x] `initializeAgentBranchesLoading` é não vazio e em PT-BR (sem placeholder em inglês)
  - [x] `initializeAgentBranchesNotGit` é não vazio e descreve ausência de repositório Git
  - [x] `initializeAgentBranchesLoadFailed` é não vazio e é mensagem segura ao usuário
  - [x] Chaves existentes do modal continuam passando nos asserts atuais
- Integration tests:
  - [x] N/A — sem fluxo end-to-end nesta tarefa
- Test coverage target: >=80% nas classes/strings tocadas
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% nos arquivos alterados
- `flutter analyze` limpo nos arquivos desta tarefa
- Domínio permanece livre de imports git2dart/Flutter
- `compozy tasks validate` passa após todas as tarefas geradas
