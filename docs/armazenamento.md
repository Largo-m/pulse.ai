# Armazenamento do Pulse

O Pulse **não tem banco próprio**. Tudo que ele persiste vive em arquivos. Há três raízes e um store externo só de leitura.

```
~/.pulse/                         config e logs ACP (máquina)
<workspace>/.pulse/               config, specs e histórico do projeto
~/.cursor/                        SQLite do Cursor (Pulse só lê)
```

Resolução de config: `defaults do código` → `~/.pulse/config.toml` → `<projeto>/.pulse/config.yaml`.

## Quem escreve o quê

| Dado | Caminho | Formato | Quem escreve | Quem lê |
| --- | --- | --- | --- | --- |
| Config global | `~/.pulse/config.toml` | TOML | Pulse (`pulse init`, settings) | Pulse |
| Config do projeto | `.pulse/config.yaml` | YAML | Pulse (`pulse init`, `pulse config`) | Pulse |
| Estado de feature | `.pulse/specs/features/<slug>/workflow.yaml` | YAML | Pulse (orquestra) e o agente (quando o prompt pede) | Pulse |
| Specs / artefatos | `.pulse/specs/**/*.md` | Markdown | Agente ACP | Pulse (TUI, histórico) e o próximo prompt |
| Histórico de run | `.pulse/runs/<uuid>/` | YAML + JSONL | Pulse (`RunRecorder`) | TUI de histórico |
| Log bruto ACP | `~/.pulse/logs/acp/` | JSONL | Pulse (`AcpLogger`) | Diagnóstico manual |
| Args de tool do Cursor | `~/.cursor/**/store.db` | SQLite | Cursor | Pulse (só leitura) |

## 1. Config global — `~/.pulse/`

Arquivo: `~/.pulse/config.toml` (`pulse/config/paths.py`).

Conteúdo: versão, binário ACP, auth, defaults (agent, model, workspace, permission_policy), onboarding, lista de agents e overrides por workflow.

Escrita em:

- `pulse init` / `pulse init --force` → `mark_onboarding_complete`
- menu de configurações → `update_global_defaults`, `update_global_agent`, `update_global_workflow`

Se `~/.pulse/config.toml` não existe e `~/.dev-orchestrator/config.toml` existe, o Pulse **copia** o legado para o caminho novo.

Logs ACP também ficam aqui: ver [logs.md](logs.md).

## 2. Config do projeto — `.pulse/config.yaml`

Descoberta: sobe a partir do CWD até achar `.pulse/config.yaml`.

Campos: `defaults.agent`, `defaults.model`, `defaults.permission_policy`, `workspace.root`, `workflows.<id>`, opcionalmente `agents`.

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
└── HANDOFF.md        checkpoint de sessão (escrito pelo agente)
```

O Pulse **não gera** os Markdowns. O agente os cria porque o prompt aponta os arquivos. O Pulse só:

- cria e atualiza `workflow.yaml` no `new-issue` (`WorkflowState.save`)
- lista features em `.pulse/specs/features/*/workflow.yaml`
- lista quick tasks em `.pulse/specs/quick/*/TASK.md` (status no próprio Markdown)
- mostra `.md` da pasta da spec no painel de artefatos

`STATE.md` é a memória persistente do projeto (decisões, blockers, quick tasks). Não é um banco: é um Markdown que o agente mantém.

## 4. Runs — `.pulse/runs/<uuid>/`

Ignorado no git (`.gitignore`).

```
.pulse/runs/<uuid>/
├── meta.yaml      id, workflow, prompt, status, slug, spec_dir, fases, timestamps
└── logs.jsonl     stream do cockpit (uma linha por LogEntry)
```

`RunRecorder` no cockpit grava no start, a cada ~400 ms se houver mudança, e no finalize. Status: `running` | `completed` | `failed`.

O catálogo de histórico **não é um arquivo**: `HistoryCatalog` junta specs + último run.

## 5. Store do Cursor (externo)

O Pulse **não escreve** em `~/.cursor/`. `CursorStoreIndex` abre em modo leitura:

- `~/.cursor/acp-sessions/<sessionId>/store.db`
- ou `~/.cursor/chats/<hash>/<sessionId>/store.db`

Usa a tabela `blobs` para recuperar `args` de `tool-call` e completar títulos vagos no cockpit (`…`, `3 files`).

## 6. Só memória (não persiste)

- `CockpitState` (fases, tasks, entries, artefatos selecionados)
- sessão ACP (`sessionId`, processo do agent)
- `ResolvedConfig` (merge em runtime)
- questionários e permissões no terminal

Se o cockpit fechar no meio, o último flush em `.pulse/runs/` é o que sobra. `workflow.yaml` e os `.md` no disco é que permitem retomar um `new-issue`.

## 7. Legado e leftovers

O código **apaga** no start de workflow:

- `.pulse/skills/<skill>/questions/`
- `.pulse/handoff/<skill>.md`

O `.gitignore` ainda cita `.pulse/worktrees/` e `.pulse/artifacts/*/acp-events.jsonl`. **Nenhum código Python atual escreve nesses caminhos.**

Skills empacotadas (`pulse/skills/pulse-spec-driven/`) são arquivos do pacote, não armazenamento de workspace. Ver [workflows-e-skills.md](workflows-e-skills.md).
