# Logs

O Pulse **não copia** o protocolo ACP para disco. O log completo fica no store do runtime (Cursor) enquanto a sessão está aberta. O Pulse não guarda histórico de run.

```
agente ACP (JSON-RPC)
        │
        ├─ AcpLogger ────────── no-op (não grava arquivo)
        │
        └─ session/update
                │
                ├─ StreamRenderer     terminal clássico (só imprime)
                └─ CockpitSink        TUI
                        └─ CockpitState.entries          (só na memória da tela)

Cursor ── ~/.cursor/acp-sessions/<sessionId>/store.db
          (o Pulse lê ao vivo para completar args de tool)
```

## 1. Ponteiro de sessão — `pulse.db`

**Tabela `agent_sessions`:** `id` (session Pulse), `project_id`, `agent_id`, `acp_session_id`, status.

Preenchida quando o `AcpSessionRunner` recebe o `sessionId` do runtime (`persist_runtime_session`). Não há `meta.yaml` nem `logs.jsonl`.

`AcpLogger` permanece na API (`log_sent` / `log_received`) para não espalhar `if` no runner; os métodos não escrevem arquivo.

## 2. Stream ao vivo — cockpit

**Memória:** `CockpitState.entries` (`LogEntry`)

`session/update` chega no `CockpitSink.handle_update`. Tools vagos são completados com o SQLite do Cursor (`CursorStoreIndex`). O stream não é gravado em arquivo.

## 3. Terminal clássico (sem TUI)

`StreamRenderer` imprime no Rich Console. **Não** gera `LogEntry` e **não** grava arquivo.

## 4. Reler no histórico

`hydrate_history_item` monta fases e artefatos a partir dos Markdowns da spec. As mensagens e tools são relidas do `store.db` do Cursor, usando o `acp_session_id` gravado em `spec_sessions` (ou, se essa linha não existir, as `agent_sessions` do mesmo projeto na janela da spec). Sem sessão ACP, cada fase mostra “Nenhum log persistido para esta sessão.”

## 5. O que **não** é log do Pulse

| Fonte | Papel |
| --- | --- |
| `~/.cursor/**/store.db` | log da sessão ACP; Pulse só lê |
| stderr do processo `agent` | não é persistido pelo Pulse |
| `~/.pulse/logs/acp/` | legado; código atual não escreve |
| `.pulse/artifacts/*/acp-events.jsonl` | leftover do `.gitignore` |

## Design da escolha

**O que:** o runtime é a fonte da sessão; o Pulse guarda `pulse_session_id` ↔ `acp_session_id`.

**Por quê:** copiar ACP para JSONL duplicava o protocolo e ficava incompleto. O store do Cursor já tem o histórico completo.

**Alternativas:** JSONL do Pulse, tabela `session_messages` própria.

**Trade-off:** histórico depende do store local do Cursor. Claude Code ainda não tem o mesmo adapter.
