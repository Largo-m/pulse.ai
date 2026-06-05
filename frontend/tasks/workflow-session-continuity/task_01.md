---
status: completed
title: Mapper de stream e modelos de conversa
type: backend
complexity: medium
dependencies: []
---

# Mapper de stream e modelos de conversa

## Overview

Introduz `PrdConversationMessageUiModel` e `PrdStreamEventMapper` para mapear `StreamEventEntity` / `PrdStreamEvent` em linhas de terminal e mensagens de conversa com as mesmas regras do fluxo live e da restauração (ADR-002). Extrai a lógica hoje duplicada em `PrdWorkflowCubit` para um mapper testável reutilizado nas tasks 03 e 04.

<critical>
- Leia `_prd.md` e `_techspec.md` antes de implementar.
- Consulte o TechSpec nas seções "PrdStreamEventMapper", "Conversation derivation" e "Data Models" — não copie snippets do TechSpec para o código da task.
- Foque no **o quê** entregar; minimize código além do necessário.
- Testes unitários são obrigatórios nesta task.
</critical>

<requirements>
1. DEVE existir `PrdConversationMessageUiModel` com `role` (`user` | `agent`), `displayText`, `timestamp` e `sequence`.
2. DEVE existir `PrdStreamEventMapper` mapeando eventos para `PrdStreamLineUiModel` com paridade ao comportamento atual do cubit (`_displayTextForEvent`, tipos `USER_ACTION`, terminal `done`/`result`).
3. DEVE derivar mensagens de usuário a partir de `workflowDirective` não vazio e de `runFeedback` opcional como mensagens separadas.
4. DEVE incluir eventos `assistant` e `result` com `payloadSummary` não vazio na conversa; DEVE excluir `thinking`, `tool_call` e `heartbeat` da conversa (permanecem só no terminal).
5. DEVE aplicar cap de 200 eventos por `sequence` descendente (últimos 200), alinhado a `PrdStreamBufferPolicy.maxInMemoryEvents`.
6. NÃO DEVE alterar schema Hive nem criar caixa de transcript.
</requirements>

## Subtasks

- [x] Criar `prd_conversation_message_ui_model.dart` em `presentation/models/`
- [x] Criar `prd_stream_event_mapper.dart` em `presentation/` com APIs para entidade persistida e `PrdStreamEvent` live
- [x] Cobrir mapeamento de tipos de evento e exclusões de conversa com testes unitários
- [x] Cobrir cap de 200 sequências e mensagens user/agent com testes unitários
- [x] Documentar contrato do mapper para consumo em restore (task 03) sem acoplar ao cubit ainda

## Implementation Details

Ver TechSpec seções **Data Models**, **Conversation derivation (ADR-002)** e **Development Sequencing** passo 1.

Mapper deve aceitar entradas já ordenadas por `sequence` asc do repositório; aplicar truncamento interno se a lista exceder 200.

### Relevant Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart` | Modelo de linha existente |
| `lib/features/orchestrator/presentation/prd_stream_buffer_policy.dart` | Constante `maxInMemoryEvents = 200` |
| `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` | Fonte da lógica live a extrair |
| `lib/features/orchestrator/domain/entities/stream_event_entity.dart` | Entrada persistida no restore |
| `lib/features/orchestrator/domain/entities/prd_stream_event.dart` | Entrada SSE no live |

### Dependent Files

| Arquivo | Motivo |
|---------|--------|
| `lib/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart` | Refatoração para usar mapper na task 04 |
| `lib/features/orchestrator/domain/usecases/restore_last_finalized_prd_session_use_case.dart` | Consumidor na task 03 |

### Related ADRs

- [ADR-002: Conversation Derived from Stream Events](adrs/adr-002.md)
- [ADR-004: Restore Presentation and Buffer Policy](adrs/adr-004.md) — cap 200

## Deliverables

- `PrdConversationMessageUiModel` e `PrdStreamEventMapper` implementados
- `test/features/orchestrator/presentation/prd_stream_event_mapper_test.dart` (ou caminho espelhado)
- Cobertura ≥ 80% nas classes novas
- `flutter analyze` limpo para arquivos tocados

## Tests

### Unit tests

- [x] `StreamEventEntity` tipo `assistant` com `payloadSummary` não vazio → uma `PrdConversationMessageUiModel` agent com mesmo texto
- [x] Evento `thinking` → linha terminal presente, zero mensagens de conversa
- [x] `workflowDirective` "Criar PRD" + `runFeedback` "Ajuste escopo" → duas mensagens user em sequências distintas
- [x] Lista com 250 eventos sequenciais → saída limitada às últimas 200 por `sequence`
- [x] `PrdStreamEvent` live tipo `result` com texto → paridade de linha terminal com mapeamento de entidade equivalente

### Integration tests

- [x] Nenhum nesta task (integração no cubit, task 04)

## Success Criteria

- Mapper cobre live e restore com mesmas regras documentadas no TechSpec
- Todos os testes unitários passando
- Cobertura ≥ 80% em mapper e modelo de conversa
- Nenhuma alteração de persistência ou UI
