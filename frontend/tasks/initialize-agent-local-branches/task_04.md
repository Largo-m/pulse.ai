---
status: completed
title: "Modal: integração com cubit, estados UI e callback onSubmit"
type: frontend
complexity: high
dependencies:
  - task_03
---

# Task 4: Modal: integração com cubit, estados UI e callback onSubmit

## Overview

Substitui branches hardcoded no modal "Novo agente" por dados reais do cubit, renderiza estados de loading/erro/não-Git conforme PRD F1–F5, desabilita **Salvar** até haver branch válida e expõe `onSubmit(InitializeAgentSubmitPayload)` ao confirmar.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST remover `_branchValues` e qualquer placeholder (`main`, `staging`, `feature/agent-init`).
- MUST chamar `cubit.loadForProject(entity.absolutePath)` ao abrir o modal e quando o usuário troca o projeto no dropdown.
- MUST usar `BlocBuilder<InitializeAgentBranchesCubit, InitializeAgentBranchesState>` para o campo de branch.
- MUST desabilitar dropdown de branch em `loading`, `notGitRepository`, `failure` e `initial`; exibir `CircularProgressIndicator` durante loading.
- MUST exibir helper text de `OrchestratorStrings` conforme mapeamento TechSpec **Status → UI mapping**.
- MUST habilitar **Salvar** somente quando `status == loaded && selectedBranch != null && branches.contains(selectedBranch)`.
- MUST estender `showInitializeAgentModal` com parâmetro opcional `void Function(InitializeAgentSubmitPayload)? onSubmit`.
- MUST invocar `onSubmit` com payload completo antes de `Navigator.pop` quando **Salvar** estiver habilitado.
- MUST chamar `cubit.reset()` no `dispose` do modal.
- MUST NOT usar literais de UI na árvore de widgets; MUST NOT usar `setState`.
- MUST NOT adicionar widget tests (política do projeto); validar via cubit/strings já cobertos + QA manual.
</requirements>

## Subtasks
- [x] 4.1 Remover `_branchValues` e `_branchNotifier` estático; integrar `BlocBuilder`
- [x] 4.2 Disparar `loadForProject` na abertura e na mudança de `projectId`
- [x] 4.3 Renderizar estados loading / loaded / notGit / failure no dropdown e helper
- [x] 4.4 Implementar regra de enablement de **Salvar** e callback `onSubmit`
- [x] 4.5 `reset()` do cubit no dispose; semantics de acessibilidade nos estados desabilitados

## Implementation Details

Problema atual — branches fixas:

```55:59:lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart
  static const List<String> _branchValues = <String>[
    'main',
    'staging',
    'feature/agent-init',
  ];
```

Ver TechSpec **Status → UI mapping**, **Submit enablement** e **Integration Points** (modal ↔ cubit ↔ `LocalProjectEntity.absolutePath`).

Design de referência (não copiar HTML): `references/stitch/initialize-agent-modal/screen.png`.

### Relevant Files
- `lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart` — alvo principal
- `lib/features/orchestrator/presentation/bloc/initialize_agent_branches_cubit.dart` — estado (task_03)
- `lib/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart` — payload (task_01)
- `lib/features/orchestrator/presentation/orchestrator_strings.dart` — cópia PT-BR (task_01)
- `lib/features/orchestrator/domain/entities/local_project_entity.dart` — `absolutePath` por `projectId`

### Dependent Files
- `lib/features/orchestrator/presentation/pages/orchestrator_page.dart` — passará `onSubmit` (task_05)

### Related ADRs
- [ADR-001: Reactive Local Branch Loading](../adrs/adr-001.md) — reload ao trocar projeto, HEAD default
- [ADR-003: InitializeAgentBranchesCubit in OrchestratorComposition](../adrs/adr-003.md) — cubit via `context.read`, reset ao fechar

## Deliverables
- Modal sem branches placeholder; UI reativa ao cubit
- Assinatura `showInitializeAgentModal(..., onSubmit?)` implementada
- Sem literais de usuário novos fora de `OrchestratorStrings`
- Regressão coberta pelos testes existentes de cubit/strings (task_02–03); sem novos widget tests
- Unit tests com 80%+ coverage **(REQUIRED)** — se alterar lógica testável extraída, adicionar testes; caso contrário documentar cobertura indireta nos critérios

## Tests
- Unit tests:
  - [x] Nenhuma regressão nos testes de `InitializeAgentBranchesCubit` e `OrchestratorStrings` ao integrar
  - [x] Se extrair helpers puros (ex.: `canSubmitAgent`), testar: `loaded` + branch na lista → true; `loaded` + `selectedBranch == null` → false; `notGitRepository` → false
- Integration tests:
  - [x] N/A automatizado — matriz QA manual PRD: repo multi-branch, pasta não-Git, falha simulada, troca de projeto atualiza lista e HEAD
- Test coverage target: >=80% no conjunto feature (cubit + domain); modal sem widget test
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% mantido no pacote orchestrator tocado pela feature
- Zero ocorrências de `main`/`staging`/`feature/agent-init` como opções fixas no modal
- **Salvar** desabilitado em não-Git, falha e HEAD detached sem seleção manual
- `flutter analyze` limpo em arquivos do modal
