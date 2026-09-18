# Logs

Existem **dois sistemas de log**, com propósitos diferentes. Não se misturam.

```
agente ACP (JSON-RPC)
        │
        ├─ AcpLogger ────────── ~/.pulse/logs/acp/<data>-<runId>.jsonl
        │                        protocolo bruto (debug)
        │
        └─ session/update
                │
                ├─ StreamRenderer     terminal clássico (só imprime)
                └─ CockpitSink        TUI
                        │
                        └─ CockpitState.entries
                                │
                                └─ RunRecorder ── .pulse/runs/<uuid>/logs.jsonl
                                                   stream do usuário (histórico)
```

## 1. Log ACP — protocolo bruto

**Onde:** `~/.pulse/logs/acp/YYYYMMDD-<run_id>.jsonl`  
**Código:** `pulse/acp/logger.py`  
**Escritores:** `AcpSessionRunner` e `AcpClient` (probe do `pulse doctor` / init)

Cada linha é um JSON:

```json
{
  "ts": "2026-09-18T22:01:00+00:00",
  "run_id": "a1b2-...",
  "session_id": "sess_...",
  "direction": "IN"
}
```

`direction`:

| Valor | Significado |
| --- | --- |
| `OUT` | Pulse → agent (`log_sent`) |
| `IN` | agent → Pulse (`log_received`) |
| `UPDATE` | `session/update` extraído do IN |
| `EVENT` | ciclo de vida Pulse (`process_start`, `run_isolated_phase_start`, `agent_request`, …) |

O `run_id` é um UUID do Pulse, **não** o `sessionId` do Cursor. O session id entra depois, no evento `session_id_set`.

Não há rotação, retenção nem UI. É arquivo de diagnóstico. Fora do git (home do usuário).

`pulse doctor --test-acp` também gera um arquivo desses via `AcpClient`.

## 2. Log do cockpit — o que a pessoa vê

**Memória:** `CockpitState.entries` (`LogEntry`)  
**Disco:** `.pulse/runs/<uuid>/logs.jsonl` + `meta.yaml`  
**Código:** `CockpitSink` → `RunRecorder` → `save_run`

Uma linha por entrada:

```json
{
  "kind": "Read",
  "title": "cli.py",
  "detail": "pulse/cli.py",
  "body": "",
  "active": false,
  "pending": false,
  "entry_id": 4,
  "tool_id": "toolu_01",
  "phase_id": "specify",
  "task_id": ""
}
```

`LogKind`: `Search`, `List`, `Read`, `Edit`, `Write`, `Shell`, `Info`, `Assistant`, `Question`, `Answer`, `Tool`.

### Como a linha nasce

`session/update` chega no `CockpitSink.handle_update`:

| `sessionUpdate` | Efeito |
| --- | --- |
| `agent_message_chunk` | texto do assistente (acumula; some `SETUP_READY`) |
| `agent_thought_chunk` | silêncio; só tenta enriquecer tools vagos |
| `tool_call` / `tool_call_update` / `tool_result` | cria/atualiza linha de tool |
| `session_info_update` | se o título for `Modelo: …`, atualiza o header |

Tools com título vazio viram `…`. Searches do tipo `3 files` ficam vagas até o Pulse ler o SQLite do Cursor (`CursorStoreIndex`) e preencher path/glob.

Perguntas do agente (`cursor/ask_question`, bloco ` ```text `) viram `Question` / `Answer` no stream, via `PromptDock`.

### Quando grava em disco

`RunRecorder` no `CockpitScreen`:

1. `start` — cria o `RunRecord` (ainda sem flush obrigatório)
2. `observe` a cada mudança de estado
3. `maybe_flush` a cada ~100 ms na UI, mas só escreve se passou **0,4 s** e está dirty
4. `finalize` / unmount — status `completed` ou `failed` + `ended_at`

`active` e `pending` **não** sobrevivem no arquivo: no save vão `false`. São só UI ao vivo (spinner).

## 3. Terminal clássico (sem TUI)

`StreamRenderer` imprime no Rich Console. **Não** gera `LogEntry` e **não** grava `.pulse/runs/`.

O log ACP **continua** sendo escrito, porque o `AcpSessionRunner` sempre instancia `AcpLogger`.

Histórico da Home só existe para runs que passaram pelo cockpit.

## 4. Reler no histórico

`hydrate_history_item`:

1. Abre o último `run_id` ligado à spec (`latest_run_for`)
2. Carrega `logs.jsonl`
3. Se não houver log: uma linha `Info` por fase — “Nenhum log persistido para esta sessão.”
4. Recoloca `task_id` em linhas de Execute que só tinham `Task T3` no título

Artefatos vêm do disco (`.md` da spec), não do log.

## 5. O que **não** é log do Pulse

| Fonte | Papel |
| --- | --- |
| `~/.cursor/**/store.db` | args de tools do Cursor, para completar o cockpit |
| stderr do processo `agent` | não é persistido pelo Pulse |
| `.pulse/artifacts/*/acp-events.jsonl` | leftover do `.gitignore`; código atual não escreve |

## Design da escolha

**O que:** dois JSONL — protocolo na home, UX no projeto.

**Por quê:** o ACP é barulhento (chunks, permissions, MCP). Misturar isso no histórico tornaria a TUI ilegível. O run do projeto precisa ser portátil com o workspace; o dump ACP é da máquina/debug.

**Alternativas:** um único log, banco, ou só console.

**Trade-off:** dois `run_id` diferentes (ACP logger vs `RunRecord.id`) não estão ligados por arquivo. Correlacionar exige timestamp + workflow. Sem cockpit, o histórico fica sem stream.
