# Workflows e skills

> **Carga e interpretação de cada workflow** (catálogo, `run_plan`, `workflow.yaml`, UI): ver [workflows.md](workflows.md).

Workflows são **pipelines fixos no código**. Skills são **instruções para o agente**. O Pulse não executa a skill: ele monta um prompt, aponta arquivos no disco e o processo `agent acp` lê e age.

## Como um workflow começa

```
Home TUI / menu terminal
  → run_plan(spec_type_id)
    → run_spec | run_setup_project | run_analyze_codebase
      → resolve_config(workflow=id)     # agent + model + cwd
      → resolve_bundled_skill(...)      # pulse-spec-driven
      → build_*_prompt(...)             # skill bundled + tarefa
      → AcpSessionRunner                # processo ACP
        → eventos → CockpitSink / StreamRenderer
```

O catálogo público em `pulse/plan/spec_types.py`:

| ID | Label | Flow | Skill empacotada |
| --- | --- | --- | --- |
| `spec` | Nova spec | Classifica → pipeline completo ou quick | `pulse-spec-driven` |
| `setup-project` | Setup project | Análise → `.pulse/specs/project/` | `pulse-spec-driven` |
| `analyze-codebase` | Analyze codebase | Exploração → `.pulse/specs/codebase/` | `pulse-spec-driven` |

Não existe workflow plugin. ID desconhecido retorna exit `2`.

Cada workflow resolve **agent e model próprios** via config (ver [armazenamento.md](armazenamento.md)). Isso não carrega skill; só escolhe o backend ACP.

## Três camadas de skill (o que existe hoje)

### 1. Skill empacotada (bundled) — o Pulse injeta

Única skill que o Pulse conhece pelo nome: `pulse-spec-driven`.

- Disco: `pulse/skills/pulse-spec-driven/` (dentro do pacote Python)
- Loader: `resolve_bundled_skill("pulse-spec-driven")` exige `SKILL.md`
- No prompt: **só caminhos**, nunca o conteúdo (`extend_prompt_with_bundled_skill`)

O agente é instruído a ler no filesystem:

```
Use a skill instalada: `pulse-spec-driven`
Siga o workflow **Specify**.
- `<site-packages>/pulse/skills/pulse-spec-driven/SKILL.md`
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

### 2. Skills e rules do workspace — o ACP carrega

O Pulse **não** varre nem injeta no prompt:

- skills do repo (`.cursor/skills/**/SKILL.md`, qualquer `SKILL.md`)
- rules (`AGENTS.md`, `CLAUDE.md`, `.cursor/rules/**`)
- agents do workspace (`AGENTS.md`)

O binário `agent acp` recebe o `cwd` em `session/new` e carrega esse contexto sozinho.

### 3. Skills globais do Cursor — o Pulse não carrega

`~/.cursor/skills/`, `~/.agents/skills/` e skills do usuário **fora do workspace** não são varridas.

Se o binário `agent acp` carregar skills globais do Cursor por conta própria, isso é comportamento do Cursor, não do Pulse. O Pulse não lista, não versiona e não injeta essas skills.

## Fluxo de cada workflow

### spec

1. Classifica o pedido (auto-sizing + Scope Eligibility).
2. Agente grava `.pulse/specs/.route.yaml` (`flow: full|quick`).
3. Pulse despacha o pipeline completo ou o quick. Se o arquivo faltar, pergunta no terminal.

### new-issue

1. Limpa legado `.pulse/skills/.../questions`.
2. Resume `workflow.yaml` incompleto ou cria `.pulse/specs/features/<slug>/workflow.yaml`.
3. Fases `specify` → `design` → `tasks` → `execute`. Design/Tasks podem ser `skip`.
4. Cada fase de planejamento: sessão isolada + aprovação no terminal (`Aprovar / ajustes / cancelar`).
5. Execute: lê `tasks.md`, agrupa **waves** (até 5 tasks prontas). `[P]` pode ir em batch. O Pulse só marca `done` depois dos gates (`Done when` / `Verify`).
6. Sem `tasks.md` (fase pulada): um prompt inline de `implement.md`.

Retomar: `find_resumable_workflows` lê os `workflow.yaml` e pergunta se continua.

### fix-bug (Quick)

1. Plano → agente cria `.pulse/specs/quick/NNN-slug/TASK.md` com `Awaiting Approval`.
2. Usuário aprova no terminal. Sem aprovação, **não** altera código de aplicação.
3. Fora de escopo: o agente pode oferecer migrar para `new-issue`.
4. Implement → `SUMMARY.md` + `STATE.md`.

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

**O que:** orquestrador + filesystem, skill única empacotada. Rules/skills/agents do workspace ficam com o ACP.

**Por quê:** o LLM ACP já carrega o contexto do `cwd`. Duplicar no prompt do Pulse estoura contexto e compete com o carregamento nativo. A skill de planejamento do Pulse precisa ser a mesma em todo `pipx install`.

**Alternativas:** banco de workflows, skills globais em `~/.pulse/skills`, inline da skill no prompt.

**Trade-off:** não dá para plugar um quinto workflow sem código. O Pulse não controla o que o ACP injeta do workspace.
