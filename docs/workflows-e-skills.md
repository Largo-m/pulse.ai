# Workflows e skills

> **Carga e interpretação de cada workflow** (catálogo, `run_plan`, `workflow.yaml`, UI): ver [workflows.md](workflows.md).

Workflows são **pipelines fixos no código**. Skills são **instruções para o agente**. O Pulse não executa a skill: ele monta um prompt, aponta arquivos no disco e o processo `agent acp` lê e age.

## Como um workflow começa

```
Home TUI / menu terminal
  → run_plan(spec_type_id)
    → run_new_issue | run_quick | run_setup_project | run_analyze_codebase
      → resolve_config(workflow=id)     # agent + model + cwd
      → resolve_bundled_skill(...)      # tlc-spec-driven
      → build_*_prompt(...)             # skill + rules + tarefa
      → AcpSessionRunner                # processo ACP
        → eventos → CockpitSink / StreamRenderer
```

Os quatro IDs estão hardcoded em `pulse/plan/spec_types.py`:

| ID | Label | Flow | Skill empacotada |
| --- | --- | --- | --- |
| `new-issue` | New issue | Specify → Design → Tasks → Execute | `tlc-spec-driven` |
| `fix-bug` | Fix / bug | Planejar → aprovar → Implementar | `tlc-spec-driven` |
| `setup-project` | Setup project | Análise → `.pulse/specs/project/` | `tlc-spec-driven` |
| `analyze-codebase` | Analyze codebase | Exploração → `.pulse/specs/codebase/` | `tlc-spec-driven` |

Não existe workflow plugin. ID desconhecido retorna exit `2`.

Cada workflow resolve **agent e model próprios** via config (ver [armazenamento.md](armazenamento.md)). Isso não carrega skill; só escolhe o backend ACP.

## Três camadas de skill (o que existe hoje)

### 1. Skill empacotada (bundled) — o Pulse injeta

Única skill que o Pulse conhece pelo nome: `tlc-spec-driven`.

- Disco: `pulse/skills/tlc-spec-driven/` (dentro do pacote Python)
- Loader: `resolve_bundled_skill("tlc-spec-driven")` exige `SKILL.md`
- No prompt: **só caminhos**, nunca o conteúdo (`extend_prompt_with_bundled_skill`)

O agente é instruído a ler no filesystem:

```
Use a skill instalada: `tlc-spec-driven`
Siga o workflow **Specify**.
- `<site-packages>/pulse/skills/tlc-spec-driven/SKILL.md`
- `.../references/specify.md`
```

Cada fase manda um **subconjunto** de referências:

| Workflow / fase | Referências apontadas |
| --- | --- |
| new-issue / specify | specify, discuss, state-management, user-input |
| new-issue / design | design, state-management, user-input |
| new-issue / tasks | tasks, state-management, user-input |
| new-issue / execute | implement, validate, coding-principles, state-management |
| fix-bug / plan | quick-mode, state-management, user-input |
| fix-bug / implement | quick-mode, coding-principles, state-management, user-input |
| setup-project | project-init, roadmap, state-management, user-input |
| analyze-codebase | brownfield-mapping, concerns, code-analysis, user-input |

Não há skill global do Pulse em `~/.pulse/skills/`. “Global” no produto é só config (`~/.pulse/config.toml`).

### 2. Skills do projeto (workspace) — o Pulse lista, o agente lê sob demanda

`discover_workspace_skills` faz `rglob("SKILL.md")` no workspace.

Inclui, por exemplo:

- `.cursor/skills/<nome>/SKILL.md`
- qualquer pasta do repo com `SKILL.md` (`custom/lint/SKILL.md`)

Pula diretórios: `.git`, `.pulse`, `.venv`, `venv`, `node_modules`, `dist`, `build`, `__pycache__`.

Por isso **`.pulse/skills/` legado não entra no índice**.

Metadados: frontmatter YAML (`name`, `description`) ou o nome da pasta.

No prompt vira um índice:

```
### Skills do projeto (sob demanda)
- **deploy** — `.cursor/skills/deploy/SKILL.md`
  Deploy para produção com checklist.
```

O Pulse **não abre** essas skills. O texto manda o agente ler só a `SKILL.md` relevante.

### 3. Skills globais do Cursor — o Pulse não carrega

`~/.cursor/skills/`, `~/.agents/skills/` e skills do usuário **fora do workspace** não são varridas.

Se o binário `agent acp` carregar skills globais do Cursor por conta própria, isso é comportamento do Cursor, não do Pulse. O Pulse não lista, não versiona e não injeta essas skills.

Rules do projeto (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/**`) também não são skills. Entram no mesmo bloco de contexto, em outro modo.

## Modo do contexto: index vs full

`extend_prompt_with_workspace_context(workspace, mode=...)`

| Modo | Quando | Rules | Skills do projeto |
| --- | --- | --- | --- |
| `index` | Specify, Design, Tasks, plano Quick | só caminhos | só índice |
| `full` | Execute, implement Quick, setup, analyze | caminhos + conteúdo até 16k chars | só índice |

Mesmo em `full`, skills do projeto **nunca são inlined**. Só rules.

## Fluxo de cada workflow

### new-issue

1. Limpa legado `.pulse/skills/.../questions`.
2. Resume `workflow.yaml` incompleto ou cria `.pulse/specs/features/<slug>/workflow.yaml`.
3. Fases `specify` → `design` → `tasks` → `execute`. Design/Tasks podem ser `skip`.
4. Cada fase de planejamento: sessão isolada + aprovação no terminal (`Aprovar / ajustes / cancelar`).
5. Execute: lê `tasks.md`, agrupa **waves** (até 5 tasks prontas). `[P]` pode ir em batch. O Pulse só marca `done` depois dos gates (`Done when` / `Verify`).
6. Sem `tasks.md` (fase pulada): um prompt inline de `implement.md`.

Retomar: `find_resumable_workflows` lê os `workflow.yaml` e pergunta se continua.

### fix-bug (Quick)

1. Plano (index) → agente cria `.pulse/specs/quick/NNN-slug/TASK.md` com `Awaiting Approval`.
2. Usuário aprova no terminal. Sem aprovação, **não** altera código de aplicação.
3. Fora de escopo: o agente pode oferecer migrar para `new-issue`.
4. Implement (full) → `SUMMARY.md` + `STATE.md`.

Não há `workflow.yaml` no quick. O status mora no `TASK.md`.

### setup-project

Duas fases na **mesma** sessão ACP:

1. Análise / entrevista (`INTERVIEW_MODE`)
2. Gera `PROJECT.md`, `ROADMAP.md`, `STATE.md`

### analyze-codebase

Mesmo desenho em duas fases: exploração → sete docs em `.pulse/specs/codebase/`.

## O que o Pulse controla vs o agente

| Pulse | Agente |
| --- | --- |
| Qual workflow rodou, ordem das fases, resume | Conteúdo de spec/design/tasks |
| Aprovação no terminal | Decidir skip de Design/Tasks |
| Gates de wave no Execute | Implementar e verificar a task |
| Gravar run + logs do cockpit | Atualizar Markdowns e, no new-issue, `workflow.yaml` |

## Design da escolha

**O que:** orquestrador + filesystem, skill única empacotada, skills do repo só como índice.

**Por quê:** o agente já sabe ler `SKILL.md`. Duplicar o conteúdo no prompt estoura contexto. Skills do projeto mudam por repo; a skill de planejamento do Pulse precisa ser a mesma em todo `pipx install`.

**Alternativas:** banco de workflows, skills globais em `~/.pulse/skills`, inline da skill no prompt.

**Trade-off:** não dá para plugar um quinto workflow sem código. Skills globais do Cursor ficam invisíveis para o Pulse.
