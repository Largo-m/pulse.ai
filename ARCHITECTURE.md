# Arquitetura do Pulse

Documento para quem está chegando no projeto (incluindo quem ainda não domina Python).

## O que é o Pulse

O **Pulse** orquestra workflows com agentes de IA (via Cursor Agent).

Você interage pela **TUI** (interface no terminal, feita com Textual).  
Quem executa de verdade é o **Engine** (processo em background, o *daemon*).

```
Você digita `pulse`
        │
        ▼
   CLI / TUI  ──────►  Engine (daemon)  ──────►  Cursor Agent
   (só UI)              (cérebro)                (quem age no código)
        │                     │
   HTTP over UDS         plan / acp
   (~/.pulse/daemon.sock)
```

### Analogia rápida

| Peça | É como… |
|------|---------|
| CLI / TUI | App no celular |
| Engine | Servidor / backend |
| Contrato HTTP | API REST entre app e servidor |
| ACP | Canal de conversa com o Cursor Agent |
| `~/.pulse/` e `.pulse/` | Dados de config e do projeto |

---

## Princípios

1. **Daemon = verdade única** — runs, config efetiva e estado de workflow vivem no Engine.
2. **CLI é cliente fino** — a TUI não importa `plan/` nem `acp/` para executar workflow; fala com a API.
3. **Um contrato, dois transportes** — mesmas rotas `/api/*` em:
   - **UDS** (`~/.pulse/daemon.sock`) — CLI local
   - **TCP** (`127.0.0.1:8787`) — tooling e clientes futuros (ex.: Desktop)
4. **Ports & Adapters** — o domínio depende de interfaces (`StreamSink`, `PromptPort`), não de Textual.
5. **Sem UI legada de terminal** — não há mais menus questionary/Rich; tudo passa pela TUI.

Contrato OpenAPI: [`contracts/openapi.yaml`](contracts/openapi.yaml).

---

## Layout do repositório

```
pulse.ai/
├── README.md                 # uso rápido
├── ARCHITECTURE.md           # este arquivo
├── pyproject.toml            # pacote Python + entry points
├── contracts/openapi.yaml    # contrato HTTP da API
├── engine/README.md          # notas do Engine
├── cli/README.md             # notas da CLI
├── tests/                    # testes
└── pulse/                    # código principal
    ├── cli.py                # entrada dos comandos
    ├── cli_daemon.py         # start/stop/status do daemon
    ├── brand.py              # banner ASCII
    ├── ports.py              # interfaces Stream/Prompt
    ├── client/               # cliente HTTP do Engine
    ├── daemon/               # boot do daemon
    ├── api/                  # rotas FastAPI
    ├── tui/                  # interface Textual
    ├── plan/                 # workflows
    ├── acp/                  # protocolo com o Agent
    ├── config/               # configuração
    ├── history/              # runs persistidos
    ├── prompts/              # parse de perguntas (sem UI)
    ├── doctor/               # checks de ambiente
    ├── mcp/                  # ponte AskQuestion
    ├── skills/               # skill TLC embutida
    ├── context/              # rules/skills do workspace
    └── runtime/              # TTY, “pulse ready”
```

Hoje o código ainda vive no pacote único `pulse/`. A separação lógica é **CLI (cliente) × Engine (daemon) × domínio**.

---

## Camadas (de fora para dentro)

### 1. Entrada — CLI

| Arquivo | Função |
|---------|--------|
| [`pulse/cli.py`](pulse/cli.py) | Lê o comando (`init`, `doctor`, `config`, `daemon`) ou abre a TUI |
| [`pulse/cli_daemon.py`](pulse/cli_daemon.py) | `pulse daemon start \| stop \| status` |
| [`pulse/__main__.py`](pulse/__main__.py) | Permite `python -m pulse` |

Entry points (`pyproject.toml`):

- `pulse` → CLI
- `pulse-engine` → daemon em foreground
- `pulse-mcp-ask` → servidor MCP de perguntas

### 2. Interface — TUI Textual

Só existe tela e interação. Não executa workflow no mesmo processo via `run_plan`.

| Caminho | Função |
|---------|--------|
| [`pulse/tui/app.py`](pulse/tui/app.py) | App Textual; abre home, cockpit, settings, onboarding, history |
| [`pulse/tui/screens/home.py`](pulse/tui/screens/home.py) | Menu principal |
| [`pulse/tui/screens/cockpit.py`](pulse/tui/screens/cockpit.py) | Run ao vivo (fases, logs, prompts) |
| [`pulse/tui/screens/settings.py`](pulse/tui/screens/settings.py) | Modelo, permissões, workflows, doctor |
| [`pulse/tui/screens/onboarding.py`](pulse/tui/screens/onboarding.py) | Wizard do `pulse init` |
| [`pulse/tui/screens/history*.py`](pulse/tui/screens/) | Histórico |
| [`pulse/tui/state.py`](pulse/tui/state.py) | Estado visual do cockpit |
| [`pulse/tui/adapters/cockpit_sink.py`](pulse/tui/adapters/cockpit_sink.py) | Eventos do Engine → atualiza a tela |
| [`pulse/tui/adapters/prompt_bridge.py`](pulse/tui/adapters/prompt_bridge.py) | Perguntas/aprovações na TUI |
| [`pulse/tui/widgets/`](pulse/tui/widgets/) | Sidebar, log, header, artifacts… |
| [`pulse/tui/hydrate.py`](pulse/tui/hydrate.py) | Reconstrói tela a partir de run salvo |

### 3. Cliente do Engine

| Arquivo | Função |
|---------|--------|
| [`pulse/client/engine_client.py`](pulse/client/engine_client.py) | Cliente HTTP (UDS preferido; TCP fallback); pode auto-iniciar o daemon |
| [`pulse/client/run_session.py`](pulse/client/run_session.py) | Cria run → escuta SSE → responde `prompt.request` → devolve exit code |

### 4. Engine — daemon (composition root)

| Arquivo | Função |
|---------|--------|
| [`pulse/daemon/server.py`](pulse/daemon/server.py) | Sobe Uvicorn em TCP + UDS |
| [`pulse/daemon/paths.py`](pulse/daemon/paths.py) | `daemon.sock`, `daemon.json`, PID |
| [`pulse/daemon/runs.py`](pulse/daemon/runs.py) | Gerencia runs (start, status, cancel) |
| [`pulse/daemon/events.py`](pulse/daemon/events.py) | Barramento de eventos + correlator de prompts |
| [`pulse/daemon/adapters.py`](pulse/daemon/adapters.py) | Stream/Prompt do domínio → eventos da API |
| [`pulse/api/app.py`](pulse/api/app.py) | Rotas FastAPI |

#### API mínima (`/api`)

| Recurso | Exemplos |
|---------|----------|
| Runtime | `GET /status`, `GET /doctor`, `POST /doctor/acp-probe` |
| Config | `GET /config`, `GET /config/resolved`, `PATCH /config/global`, `POST /config/project` |
| Workflows | `GET /workflows`, `POST /workflows/{id}/runs` |
| Runs | `GET /runs/{id}`, `POST /runs/{id}/cancel`, `GET /runs/{id}/events` (SSE), `GET /runs/{id}/logs` |
| Prompts | Engine emite `prompt.request` no SSE; cliente responde `POST /prompts/{id}/answer` |
| History | `GET /history`, `GET /history/{id}` |

Persistência:

- Global: `~/.pulse/` (`config.toml`, `daemon.sock`, …)
- Projeto: `<workspace>/.pulse/` (`config.yaml`, `specs/`, `runs/`)

### 5. Domínio (regras de negócio)

Usado pelo Engine. A TUI **não** deve chamar isso direto para executar workflow.

#### Ports

| Arquivo | Função |
|---------|--------|
| [`pulse/ports.py`](pulse/ports.py) | `StreamSink`, `PromptPort`, `NullStreamSink`, `NullPromptPort` |

#### Plan (workflows)

| Arquivo | Função |
|---------|--------|
| [`pulse/plan/runner.py`](pulse/plan/runner.py) | Fachada: “roda este workflow” |
| [`pulse/plan/spec_types.py`](pulse/plan/spec_types.py) | Catálogo: `spec`, `setup-project`, `analyze-codebase` |
| [`pulse/plan/*_flow.py`](pulse/plan/) | Passo a passo de cada workflow |
| [`pulse/plan/*_prompt.py`](pulse/plan/) | Textos enviados ao agente |
| [`pulse/plan/specify_state.py`](pulse/plan/specify_state.py) | Estado Specify → Design → Tasks → Execute |
| [`pulse/plan/task_waves.py`](pulse/plan/task_waves.py) | Ondas de tasks no Execute |

#### ACP

| Arquivo | Função |
|---------|--------|
| [`pulse/acp/session_runner.py`](pulse/acp/session_runner.py) | Processo do agent, prompts, updates |
| [`pulse/acp/client.py`](pulse/acp/client.py) | Cliente ACP + probe |
| [`pulse/acp/models.py`](pulse/acp/models.py) | Helpers de modelo |
| [`pulse/acp/capabilities.py`](pulse/acp/capabilities.py) | Capacidades declaradas pelo Pulse |

#### Config, history, prompts, doctor, mcp, skills

| Pasta | Função |
|-------|--------|
| [`pulse/config/`](pulse/config/) | Global TOML, projeto YAML, resolve efetivo, catálogo de models |
| [`pulse/history/`](pulse/history/) | Models neutros, grava/lê `.pulse/runs/` |
| [`pulse/prompts/`](pulse/prompts/) | Parse de ask-question / questionnaires (sem UI) |
| [`pulse/doctor/`](pulse/doctor/) | Checks de agent/auth/ambiente |
| [`pulse/mcp/`](pulse/mcp/) | Ponte MCP AskQuestion |
| [`pulse/skills/`](pulse/skills/) | Skill `pulse-spec-driven` |
| [`pulse/context/`](pulse/context/) | Descobre rules/skills do workspace |
| [`pulse/runtime/`](pulse/runtime/) | `is_interactive`, `is_pulse_ready` |

---

## Fluxo completo (ex.: Nova spec na TUI)

```
1. Usuário: pulse
2. cli.py garante Engine up → abre PulseApp (HomeScreen)
3. Usuário escolhe "Nova spec" e descreve a spec
4. CockpitScreen → EngineRunSession
5. client: POST /api/workflows/spec/runs
6. daemon/runs.py → plan/runner.py → spec_flow.py
7. Classificar → `.pulse/specs/.route.yaml` → despacha new-issue ou quick
8. flow → acp/session_runner.py → processo `agent acp`
9. Agent responde → eventos SSE → CockpitSink → tela atualiza
10. Agent pergunta → prompt.request → TUI responde
   → POST /prompts/{id}/answer
11. run.finished → history em .pulse/runs/
```

---

## O que pode / não pode misturar

| Pode | Não deve |
|------|----------|
| TUI chamar `pulse/client/` | TUI importar `plan/` ou `acp/` para executar workflow |
| Engine chamar `plan/`, `acp/`, `config/` | Domínio importar Textual / widgets |
| CLI renderizar doctor/config em texto | CLI reimplementar a lógica dos flows |
| `prompts/` parsear perguntas | `prompts/` depender de UI |

---

## Design patterns usados

| Pattern | Onde | Para quê |
|---------|------|----------|
| Composition Root | `daemon/` | Só o daemon monta o grafo de serviços |
| Ports & Adapters | `ports.py` + TUI/API adapters | Domínio independente da UI |
| Facade | `plan/runner.py` | Uma entrada estável para workflows |
| Transport parity | UDS + TCP | Mesmo contrato para CLI e futuros clients |
| Correlated request/response | `prompt.request` + `POST /prompts/{id}/answer` | Aprovações sobre HTTP/SSE |

---

## Comandos úteis

```bash
pip install -e ".[dev]"

pulse                  # TUI
pulse init             # onboarding (tela Textual)
pulse doctor           # via Engine (use --local para checks locais)
pulse config show
pulse daemon start
pulse daemon status
pulse daemon stop
pulse-engine           # daemon em foreground

pytest
```

---

## Glossário

| Termo | Significado |
|-------|-------------|
| **Daemon** | Processo em background (o Engine) |
| **UDS** | Unix Domain Socket — arquivo local (`daemon.sock`); HTTP por cima |
| **SSE** | Server-Sent Events — stream HTTP de eventos do run |
| **ACP** | Agent Client Protocol — JSON-RPC com o Cursor Agent |
| **Port** | Interface (contrato) que o domínio espera |
| **Adapter** | Implementação da port (TUI, API, Null…) |
| **Composition root** | Único lugar que “liga” todas as peças |
| **Workflow** | Pipeline tipado (`spec`, `setup-project`, …) |
| **Run** | Uma execução concreta de um workflow |

---

## Fora de escopo atual

- App Desktop (será feito do zero no futuro; consumirá a mesma API HTTP)
- Gateway remoto / pairing
- Monorepo físico total (`engine/pulse_engine` vs `cli/pulse_cli` como packages separados)

---

## Referências rápidas

- Uso do produto: [`README.md`](README.md)
- OpenAPI: [`contracts/openapi.yaml`](contracts/openapi.yaml)
- Engine: [`engine/README.md`](engine/README.md)
- CLI: [`cli/README.md`](cli/README.md)
- Skill de processo: [`pulse/skills/pulse-spec-driven/`](pulse/skills/pulse-spec-driven/)
