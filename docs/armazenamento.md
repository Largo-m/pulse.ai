# Armazenamento do Pulse

Config operacional vive em SQLite. Specs continuam Markdown no workspace. O Pulse não grava log ACP em arquivo.

```
~/.pulse/pulse.db                 config da máquina, projetos e ponteiros de sessão
~/.pulse/agents/                  prompts dos agents do Pulse (uma cópia na máquina)
<workspace>/.pulse/specs/         artefatos Markdown
~/.cursor/                        SQLite do Cursor (Pulse só lê, ao vivo)
```

Resolução de config: `defaults do código` → tabela `machine` → tabelas `project_*` no mesmo `pulse.db`, identificadas por `project_id` / `root_path`.

## Quem escreve o quê

| Dado | Caminho | Formato | Quem escreve | Quem lê |
| --- | --- | --- | --- | --- |
| Config global | `~/.pulse/pulse.db` (`machine*`) | SQLite | Pulse (`pulse init`, settings) | Pulse |
| Config do projeto | `~/.pulse/pulse.db` (`projects`, `project_*`) | SQLite | Pulse (`pulse init`, `pulse config`) | Pulse |
| Estado de feature | `.pulse/specs/features/<slug>/workflow.yaml` | YAML | Pulse (orquestra) e o agente (quando o prompt pede) | Pulse |
| Specs / artefatos | `.pulse/specs/**/*.md` | Markdown | Agente ACP | Pulse (TUI, histórico) e o próximo prompt |
| Agents do Pulse | `~/.pulse/agents/<id>/AGENT.md` | Markdown | Pulse (cópia no init) e o usuário | Pulse (`load_agent`) |
| Ponteiro de sessão | `~/.pulse/pulse.db` (`agent_sessions`) | SQLite | Pulse (`persist_runtime_session`) | diagnóstico |
| Log da sessão ACP | `~/.cursor/**/store.db` | SQLite | Cursor | Pulse (só leitura) |

## 1. Config da máquina — `~/.pulse/pulse.db`

Tabelas `machine`, `machine_agents`, `machine_workflows`.

Conteúdo: versão, binário ACP, auth, defaults (agent, model, workspace, permission_policy), onboarding, lista de runtimes e overrides por workflow.

Escrita em:

- `pulse init` / `pulse init --force` → `mark_onboarding_complete`
- menu de configurações → `update_global_defaults`, `update_global_agent`, `update_global_workflow`

Não há mais `config.toml`. Override de testes: variável `PULSE_DB`.

O log da sessão fica no Cursor: ver [logs.md](logs.md).

## 2. Config do projeto — mesmo SQLite, `project_id`

Descoberta: sobe a partir do CWD até achar um `root_path` cadastrado em `projects`.

Campos em `project_settings` / `project_workflows` / `project_agents`: agent, model, permission_policy, workspace, workflows.

Criado por `pulse init` (se ainda não existir) e `pulse config init`. Atualizado pelo menu de settings do projeto.

A config efetiva por workflow é: `projeto.workflows[id]` → `global.workflows[id]` → `projeto.defaults` → `global.defaults` → defaults do código (`pulse/config/resolved.py`).

## 3. Specs — `.pulse/specs/`

Árvore esperada pela skill `pulse-spec-driven`:

```
.pulse/specs/
├── project/          PROJECT.md, ROADMAP.md, STATE.md
├── codebase/         STACK, ARCHITECTURE, CONVENTIONS, STRUCTURE, TESTING, INTEGRATIONS, CONCERNS
├── features/<slug>/  spec.md, context.md, design.md, tasks.md, workflow.yaml
├── quick/NNN-slug/   TASK.md, SUMMARY.md
├── .route.yaml       última classificação de Nova spec (full | quick)
└── HANDOFF.md        checkpoint de sessão (escrito pelo agente)
```

O Pulse **não gera** os Markdowns. O agente os cria porque o prompt aponta os arquivos. O Pulse só:

- classifica Nova spec lendo `.pulse/specs/.route.yaml`
- cria e atualiza `workflow.yaml` no `new-issue` (`WorkflowState.save`)
- lista specs em `.pulse/specs/features/*/workflow.yaml` e `.pulse/specs/quick/*/TASK.md`
- mostra `.md` da pasta da spec no painel de artefatos

`STATE.md` é a memória persistente do projeto (decisões, blockers, quick tasks). Não é um banco: é um Markdown que o agente mantém.

## 4. Agents — `~/.pulse/agents/`

O init copia cada `AGENT.md` empacotado para `~/.pulse/agents/<id>/AGENT.md` se o arquivo ainda não existir. A cópia vale para todos os projetos desta máquina. O Pulse não lê `<projeto>/.pulse/agents/`, `.cursor/agents/`, `.claude/agents/` nem `.codex/agents/`.

Quem ganha o prompt:

1. bundled do pacote, se a cópia da máquina não existir
2. `~/.pulse/agents/<id>/AGENT.md` (ou `<id>.md`)

Um agent extra, fora do catálogo, só entra se estiver em `~/.pulse/agents/`.

## 5. Histórico

Não há catálogo de runs. O cockpit não grava `meta.yaml`. A lista de histórico lê specs em `.pulse/specs/` (`workflow.yaml` e `TASK.md`). Abrir um item antigo mostra as fases e os Markdowns. O log da sessão não é relido.

## 6. Store do Cursor (externo)

O Pulse **não escreve** em `~/.cursor/`. `CursorStoreIndex` abre em modo leitura:

- `~/.cursor/acp-sessions/<sessionId>/store.db`
- ou `~/.cursor/chats/<hash>/<sessionId>/store.db`

Usa a tabela `blobs` para recuperar `args` de `tool-call` no cockpit ao vivo.

## 7. Só memória (não persiste)

- `CockpitState` (fases, tasks, entries, artefatos selecionados)
- sessão ACP (`sessionId`, processo do agent)
- `ResolvedConfig` (merge em runtime)
- questionários e permissões no terminal

Se o cockpit fechar no meio, o stream da sessão se perde. `workflow.yaml` e os `.md` no disco é que permitem retomar um `new-issue`.

## 8. Legado e leftovers

O código **apaga** no start de workflow:

- `.pulse/skills/<skill>/questions/`
- `.pulse/handoff/<skill>.md`

O `.gitignore` ainda cita `.pulse/worktrees/` e `.pulse/artifacts/*/acp-events.jsonl`. **Nenhum código Python atual escreve nesses caminhos.**

Skills empacotadas (`pulse/skills/pulse-spec-driven/`) são arquivos do pacote, não armazenamento de workspace. Ver [workflows-e-skills.md](workflows-e-skills.md).
