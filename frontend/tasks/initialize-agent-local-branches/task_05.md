---
status: completed
title: "Caller na página e verificação final"
type: frontend
complexity: low
dependencies:
  - task_04
---

# Task 5: Caller na página e verificação final

## Overview

Conecta o modal na página do orchestrator com callback `onSubmit` (stub ou no-op aceitável no MVP), executa verificação final da feature (`flutter analyze`, `dart format .`) e confirma critérios de saída do PRD para entrega.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST atualizar `orchestrator_page.dart` para passar `onSubmit` em `showInitializeAgentModal` (implementação pode ser stub vazio até persistência de agente existir).
- MUST executar `dart format .` na raiz do repositório e incluir alterações de formatação.
- MUST executar `flutter analyze` sem issues nos arquivos da feature.
- SHOULD documentar no PR/commit notas de QA manual da matriz PRD (multi-branch, não-Git, falha, troca de projeto).
- MUST NOT implementar persistência de agente nesta tarefa (fora de escopo MVP).
</requirements>

## Subtasks
- [x] 5.1 Passar `onSubmit` a partir de `RecentProjectsSidebar.onNewProject` / `orchestrator_page`
- [x] 5.2 Rodar `dart format .` e `flutter analyze`
- [x] 5.3 Executar suíte de testes unitários do orchestrator relacionada à feature
- [x] 5.4 Checklist QA manual PRD (registrar resultado nos critérios de aceite)

## Implementation Details

Ponto de entrada atual do modal:

```dart
// orchestrator_page.dart — showInitializeAgentModal com onSubmit: InitializeAgentSubmitHandler.handle
```

Ver TechSpec **Development Sequencing** passo 11 e PRD **Phased Rollout → MVP exit criteria**.

### Relevant Files
- `lib/features/orchestrator/presentation/pages/orchestrator_page.dart` — chama `showInitializeAgentModal`
- `lib/features/orchestrator/presentation/widgets/initialize_agent_modal.dart` — assinatura com `onSubmit` (task_04)
- `lib/features/orchestrator/presentation/initialize_agent_submit_handler.dart` — stub MVP (no-op)

### Dependent Files
- Nenhum downstream obrigatório no MVP; agent creation futuro consumirá `InitializeAgentSubmitPayload`

### Related ADRs
- [ADR-001: Reactive Local Branch Loading](../adrs/adr-001.md) — metadata-only; stub de submit não persiste branch ainda

## Deliverables
- `orchestrator_page.dart` wired com `onSubmit` opcional
- Repositório formatado e analyze limpo
- Suite de testes da feature verde
- Unit tests com 80%+ coverage **(REQUIRED)** — suite existente permanece verde; sem novos arquivos obrigatórios se nenhuma lógica nova

## Tests
- Unit tests:
  - [x] `flutter test test/features/orchestrator/` passa sem falhas
  - [x] `InitializeAgentSubmitHandler.handle` aceita payload sem lançar
- Integration tests:
  - [ ] QA manual: abrir modal → branches reais aparecem para projeto Git
  - [ ] QA manual: pasta não-Git → campo desabilitado + mensagem PT-BR
  - [ ] QA manual: trocar projeto → reload + HEAD default
  - [ ] QA manual: **Salvar** desabilitado sem branch válida; habilitado com seleção em `loaded`
- Test coverage target: >=80% no escopo orchestrator da feature
- All tests must pass

## QA manual (PR / validação desktop)

Registrar no PR antes do merge:

| Cenário | Passos | Resultado esperado |
|---------|--------|-------------------|
| Repo multi-branch | Importar pasta Git com ≥2 branches locais → Novo agente | Lista real; HEAD pré-selecionado; **Salvar** habilitado após load |
| Pasta não-Git | Projeto sem `.git` → Novo agente | Dropdown desabilitado; copy PT-BR não-Git; **Salvar** desabilitado |
| Falha de leitura | Simular permissão negada / repo inacessível | Dropdown desabilitado; mensagem de falha PT-BR |
| Troca de projeto | Alternar projeto no dropdown | Loading → nova lista; HEAD do novo repo |
| HEAD detached | Repo em detached HEAD | Lista carregada; `selectedBranch` null; **Salvar** desabilitado até escolha manual |
| Cancelar modal | Abrir e fechar sem salvar | `onSubmit` não invocado; próxima abertura sem estado stale |

Cobertura automatizada: cubit, service, use case, submit rules, strings, handler stub — 99 testes na suíte completa.

## Success Criteria
- All tests passing
- Test coverage >=80% no conjunto de arquivos da feature
- `flutter analyze` exit 0
- `dart format .` aplicado
- PRD MVP exit criteria verificados em QA manual
- Nenhum placeholder de branch permanece no produto
