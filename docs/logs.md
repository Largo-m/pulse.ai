# Logs

O Pulse **não copia** o protocolo ACP para disco. O log completo fica no store do runtime (Cursor). O Pulse só guarda ponteiros.

```
agente ACP (JSON-RPC)
        │
        ├─ AcpLogger ────────── no-op (não grava arquivo)
        │
        └─ session/update
                │
                ├─ StreamRenderer     terminal clássico (só imprime)
                └─ CockpitSink        TUI
                        │
                        ├─ CockpitState.entries          (ao vivo)
                        ├─ CockpitState.acp_session_id
                        └─ RunRecorder ── .pulse/runs/<uuid>/meta.yaml
                                           (catálogo + acp_session_id)

Cursor ── ~/.cursor/acp-sessions/<sessionId>/store.db
          (histórico relê este SQLite)
```

## 1. Ponteiros — `pulse.db` e `meta.yaml`

**Tabela `agent_sessions`:** `id` (session Pulse), `project_id`, `agent_id`, `acp_session_id`, status.

Preenchida quando o `AcpSessionRunner` recebe o `sessionId` do runtime (`persist_runtime_session`).

**Run:** `.pulse/runs/<uuid>/meta.yaml` inclui `acp_session_id`. Não há `logs.jsonl`.

`AcpLogger` permanece na API (`log_sent` / `log_received`) para não espalhar `if` no runner; os métodos não escrevem arquivo.

## 2. Stream ao vivo — cockpit

**Memória:** `CockpitState.entries` (`LogEntry`)

`session/update` chega no `CockpitSink.handle_update`. Tools vagos são completados com o SQLite do Cursor (`CursorStoreIndex`).

`RunRecorder` grava só o `meta.yaml` (start, ~400 ms se dirty, finalize). O stream **não** é duplicado no workspace.

## 3. Terminal clássico (sem TUI)

`StreamRenderer` imprime no Rich Console. **Não** gera `LogEntry` e **não** grava `.pulse/runs/`.

## 4. Reler no histórico

`hydrate_history_item`:

1. Abre o último `run_id` ligado à spec (`latest_run_for`)
2. Se ainda existir `logs.jsonl` legado, usa
3. Senão, lê `acp_session_id` do `meta.yaml` e `list_session_events` no `store.db` do Cursor
4. Se não houver store: uma linha `Info` por fase — “Nenhum log persistido para esta sessão.”

Artefatos vêm do disco (`.md` da spec), não do log.

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
