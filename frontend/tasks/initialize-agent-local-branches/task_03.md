---
status: completed
title: "Estado e DI: cubit, composition e testes"
type: backend
complexity: medium
dependencies:
  - task_02
---

# Task 3: Estado e DI: cubit, composition e testes

## Overview

Introduz a máquina de estados de carregamento de branches (`InitializeAgentBranchesCubit`), registra service → use case → cubit em `OrchestratorComposition` conforme ADR-003, e cobre transições, seleção, troca rápida de projeto e `reset()` com `bloc_test`.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST criar `BranchLoadStatus` e `InitializeAgentBranchesState` com `status`, `branches`, `selectedBranch`, `activePath`, `loadGeneration`.
- MUST implementar `loadForProject(String absolutePath)` emitindo `loading` → resultado (`loaded`, `notGitRepository`, `failure`).
- MUST pré-selecionar `selectedBranch` com `headBranchName` quando presente na lista de branches locais.
- MUST incrementar `loadGeneration` a cada `loadForProject` e ignorar emissões obsoletas após await se a geração mudou.
- MUST expor `selectBranch(String name)` e `reset()` para limpar estado ao fechar o modal.
- MUST registrar cubit em `OrchestratorComposition.create()` / `MultiBlocProvider` e fechar no `dispose()`.
- MUST NOT alterar `initialize_agent_modal.dart` nesta tarefa.
</requirements>

## Subtasks
- [x] 3.1 Criar state + cubit com `loadForProject`, `selectBranch`, `reset`
- [x] 3.2 Wire service → use case → cubit em `orchestrator_composition.dart`
- [x] 3.3 Adicionar cubit ao `MultiBlocProvider` e `dispose()`
- [x] 3.4 Testes `bloc_test` para fluxos happy path, erro, não-Git, stale load e reset

## Implementation Details

Ver TechSpec **Data Models** (tabela Cubit state), **Data flow** passos 1–5, **Rapid project switching** e **Detached HEAD**.

Padrões: `recent_projects_cubit.dart`, `import_flow_cubit.dart`, wiring em `orchestrator_composition.dart` (linhas 27–66).

### Relevant Files
- `lib/app/di/orchestrator_composition.dart` — DI atual (`RecentProjectsCubit`, `ImportFlowCubit`)
- `lib/features/orchestrator/presentation/bloc/recent_projects_cubit.dart` — padrão cubit + use cases
- `test/features/orchestrator/presentation/bloc/recent_projects_cubit_test.dart` — padrão `bloc_test`
- `test/features/orchestrator/domain/usecases/fake_local_git_branches_service.dart` — fake (task_02)

### Dependent Files
- `lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart` — `BlocBuilder` + `loadForProject` (task_04)

### Related ADRs
- [ADR-003: InitializeAgentBranchesCubit in OrchestratorComposition](../adrs/adr-003.md) — cubit no escopo da composition, não ValueNotifier efêmero
- [ADR-001: Reactive Local Branch Loading](../adrs/adr-001.md) — reload reativo e default HEAD

## Deliverables
- `initialize_agent_branches_state.dart` e `initialize_agent_branches_cubit.dart`
- `orchestrator_composition.dart` atualizado com novo cubit e dispose
- Testes unitários do cubit com `FakeLocalGitBranchesService`
- Unit tests com 80%+ coverage **(REQUIRED)**

## Tests
- Unit tests:
  - [x] `loadForProject` emite `loading` seguido de `loaded` com branches do fake e `selectedBranch` igual ao head quando listado
  - [x] Outcome `notGitRepository` emite status `notGitRepository`, dropdown logicamente sem seleção válida
  - [x] Outcome `failure` emite status `failure`
  - [x] `selectBranch('feature/x')` atualiza `selectedBranch` mantendo `loaded`
  - [x] Duas chamadas rápidas a `loadForProject` com paths diferentes: apenas a última geração emite estado final (stale ignorado)
  - [x] `reset()` volta ao estado inicial (`initial` ou equivalente documentado no state)
  - [x] HEAD detached no fake: `loaded` com `selectedBranch == null` e branches não vazias
- Integration tests:
  - [x] N/A — composição validada indiretamente via cubit + analyze
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% no cubit e state
- Cubit acessível via `context.read<InitializeAgentBranchesCubit>()` dentro do escopo do orchestrator
- `dispose()` fecha o cubit sem vazamento
