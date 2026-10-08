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

## 0. Log operacional do daemon — `~/.pulse/daemon.log`

O daemon sobe destacado com o stderr anexado a `~/.pulse/daemon.log`
([`pulse/daemon/logs.py`](../pulse/daemon/logs.py) configura o logger `pulse`).
Uma linha por fato, com o nome do evento SSE que ela espelha e sempre o
`run_id`, para dar `grep` numa run só:

```
2026-10-08 14:02:11,301 INFO pulse.daemon.runs run.started run_id=3f… workflow=new-issue resumed=False
2026-10-08 14:02:11,410 INFO pulse.daemon.adapters phase.begin run_id=3f… title='PRD'
2026-10-08 14:03:40,022 INFO pulse.daemon.adapters run.awaiting run_id=3f… waiting=True
2026-10-08 14:05:02,877 INFO pulse.daemon.adapters step.status run_id=3f… step=prd status=done
2026-10-08 14:09:13,550 INFO pulse.daemon.runs run.finished run_id=3f… status=done exit_code=0 seconds=422.2
```

| Evento | Nível | Quando |
| --- | --- | --- |
| `daemon.started` / `daemon.stopped` | INFO | subida e saída do processo (pid, endereços) |
| `run.started` / `run.finished` | INFO | início e fim da run: status, exit code, duração |
| `run.failed` | ERROR | o motor levantou; vem com o traceback |
| `run.cancel_requested` | INFO | stop pedido pelo usuário ou pelo desligamento |
| `phase.begin`, `step.status` | INFO | step começou; status final de um step mudou |
| `run.awaiting` | INFO | a run parou esperando o usuário, e voltou |
| `shutdown: runs still running…` | WARNING | run que não parou no prazo do SIGTERM |
| `… failed` (`pulse.api.app`) | ERROR | rota que respondeu 500, com traceback |

Só ids, status e tempos: **nunca** o prompt do usuário, o texto do agente ou o
ambiente (`AGENTS.md` §6.1). O arquivo não é rotacionado.

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
