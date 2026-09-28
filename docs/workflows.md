# Como o Pulse carrega e interpreta workflows

Workflows **não são lidos de um YAML de definição**. O Pulse conhece um catálogo hardcoded. “Carregar” significa: escolher o ID → resolver config → montar estado/UI → despachar o flow Python → interpretar artefatos e respostas do agente.

## 1. O catálogo (único lugar que “define” workflows)

Arquivo: `pulse/plan/spec_types.py`

```python
SPEC_TYPES = (
    SpecType("spec", "Nova spec", ""),
    SpecType("setup-project", "Setup project", "Setup inicial"),
    SpecType("analyze-codebase", "Analyze codebase", "Mapear código"),
)
```

O catálogo público alimenta o menu, a API e o settings.

| Consumidor | Uso |
| --- | --- |
| `HomeScreen` / menu terminal | lista de opções públicas |
| `run_plan` | `if spec_type_id == "..."` → função Python |
| settings de workflow | quais IDs podem ter agent/model |
| `CockpitState.WORKFLOW_PHASES` | quais steps a sidebar mostra |

Não existe plugin, discovery em disco, nem `workflows/*.yaml` de pipeline. ID desconhecido → exit `2`.

A config TOML/YAML (`workflows.spec.agent`, etc.) **não define o pipeline** — só agent e model. Ver [armazenamento.md](armazenamento.md).

## 2. Pipeline de carregamento (tudo workflow)

```
usuário escolhe "Nova spec"
        │
        ▼
Home / menu  →  workflow_id = "spec" + user_prompt
        │
        ▼
CockpitScreen.configure_workflow("spec")
        │     fase Classificar
        ▼
run_plan(spec_type_id="spec", workspace=..., stream=CockpitSink)
        │
        ▼
resolve_config(workflow="spec")
        │     agent, model, acp_command, permission_policy, cwd
        ▼
run_spec(...)               ← classifica e despacha
        │
        ├─ .pulse/specs/.route.yaml  (flow: full | quick)
        ├─ workflow.route            (sidebar ganha fases do flow)
        ├─ run_new_issue             se full
        └─ run_quick                 se quick
```

Passos comuns a **todos** os flows:

1. Gate: terminal interativo **ou** `stream.cockpit` (TUI).
2. `check_agent_in_path` + `check_auth`.
3. `resolve_config(workflow=<id>)`.
4. `cleanup_legacy_pulse_questions` (apaga perguntas antigas em disco).
5. Resolve skill bundled → paths no prompt (não o conteúdo).
6. Sobe `AcpSessionRunner` com o sink (cockpit ou console).

Detalhe de skills: [workflows-e-skills.md](workflows-e-skills.md). Detalhe de perguntas: [questions.md](questions.md).

## 3. Como a UI “interpreta” o workflow

Antes do ACP subir, o cockpit já sabe a forma:

```103:122:pulse/tui/state.py
WORKFLOW_PHASES = {
    "spec": (("classify", "Classificar"),),
    "new-issue": (("prd", "PRD"), ("techspec", "Techspec"), ...),
    "fix-bug": (("plan", "Planejar"), ("implement", "Implementar")),
    "setup-project": (("phase1", "Análise do projeto"), ("phase2", "Gerando specs")),
    "analyze-codebase": (("phase1", "Explorando codebase"), ("phase2", "Gerando docs")),
}
```

`configure_workflow(id)` cria a lista de `PhaseItem`. Depois da classificação, `apply_routed_flow` acrescenta as fases do flow escolhido sem apagar o log. O stream (`CockpitSink.begin_phase`) marca RUNNING / DONE. Tasks aninhadas (só `new-issue` Execute) vêm de `workflow.yaml` / `tasks.md` via `set_tasks`.

**Importante:** a sidebar e o `workflow.yaml` usam nomes parecidos, mas são camadas diferentes. A UI pode mostrar “PRD” enquanto o YAML ainda diz `awaiting_approval`.

## 4. Resolução de config por workflow

`resolve_config(..., workflow=id)`:

```
projeto.workflows[id].agent/model
  → global.workflows[id]
  → projeto.defaults
  → global.defaults
  → defaults do código
```

Só muda **quem** roda o agente (binário ACP + model). O **quê** (fases, prompts) continua no código Python do flow.

## 5. Cada workflow: o que carrega e o que interpreta

### `spec` — classifica e despacha

**Carrega** o prompt do usuário e a skill `pulse-spec-driven` (auto-sizing + Scope Eligibility).

**Interpreta**

1. Sessão ACP curta: o agente grava `.pulse/specs/.route.yaml` com `flow: full|quick`.
2. Pulse lê o arquivo. Se faltar, pergunta no terminal.
3. Emite `workflow.route` para a TUI remontar a sidebar.
4. Despacha `run_new_issue` (`full`) ou `run_quick` (`quick`).

### `new-issue` — o único com máquina de estados no Pulse

**Carrega**

| Fonte | Conteúdo |
| --- | --- |
| `find_resumable_workflows(workspace)` | `.pulse/specs/features/*/workflow.yaml` incompletos |
| ou `WorkflowState.create_new` + `save` | novo slug a partir do prompt |
| skill `pulse-spec-driven` | referências por fase |
| depois do Tasks | `tasks.md` → lista `T1`, `T2`, … |

**Interpreta**

O arquivo `workflow.yaml` é a fonte da verdade do orquestrador:

| Campo | Como o Pulse usa |
| --- | --- |
| `current_phase` | de onde retomar o loop (`_phase_start_index`) |
| `phases.<name>.status` | skip se `approved`/`done`; espera se `awaiting_approval` |
| `phases.techspec.skip` / `tasks.skip` | não roda Techspec/Tasks |
| `tasks[].id/status` | o que falta no Execute; sync a partir de `tasks.md` |

Ordem fixa: `prd` → `techspec` → `tasks` → `execute` (`PHASE_ORDER`).

Por fase de planejamento:

1. Marca `in_progress`, grava YAML.
2. Monta prompt (`build_prd_prompt`, …) com a skill empacotada + tarefa.
3. `run_isolated_phase` — sessão ACP isolada + questionário de aprovação.
4. Classifica outcome (`approve` / `adjust` / `cancel` / `skip`) — ver [questions.md](questions.md).
5. Se aprovou: `approve_phase` + `save`. Em Tasks: `sync_tasks_from_markdown`.
6. Recarrega YAML do disco (`_reload_state`) — o agente pode ter marcado `skip` nas próximas fases.

No Execute:

1. Lê tasks do YAML / `tasks.md`.
2. Sem tasks → um `run_isolated_prompt` inline (`implement.md`).
3. Com tasks → `parse_task_specs` + `build_waves` (até 5, `[P]` em batch).
4. Cada wave: prompt da skill + gates (`Done when` / `Verify` / `Gate check passes`).
5. Só depois do gate o Pulse marca a task `done` no YAML.

O agente **escreve** `PRD.md`, `TECHSPEC.md`, `tasks.md` e atualiza o YAML. O Pulse **lê** o YAML para decidir o próximo passo.

### `fix-bug` — estado no Markdown, não no YAML

**Carrega**

- Não lê `workflow.yaml`.
- Prompt de plano (`build_quick_plan_prompt`).
- Skill refs: `quick-mode.md`, …

**Interpreta**

1. Até 4 turns de plano + questionário.
2. Outcomes: `approve`, `cancel`, `migrate`, `adjust`, `reduce_scope`.
3. Sem `approve` → **não** entra na implementação.
4. Com `approve` → `build_quick_implement_prompt` na mesma sessão ACP (muda para AGENT_MODE).

O “estado” que o histórico vê depois vem de `.pulse/specs/quick/NNN-slug/TASK.md` (`**Status:** …`), parseado por `list_quick_tasks` — o Pulse não orquestra fases a partir desse arquivo durante o run; só o agente o mantém.

UI: 2 steps (`plan`, `implement`).

### `setup-project` — duas fases, sem resume

**Carrega**

- Prompt de entrevista (`build_setup_project_prompt`).
- Nenhum estado YAML de workflow.

**Interpreta**

1. Fase 1 (`INTERVIEW_MODE`): agente analisa / pergunta.
2. Se houver ` ```text `, coleta respostas; se não, segue.
3. Fase 2 (`AGENT_MODE`): `build_setup_project_artifact_prompt` com resumo + respostas → espera `PROJECT.md`, `ROADMAP.md`, `STATE.md`.

Não há resume automático. Rodar de novo é outra sessão.

UI: `phase1`, `phase2`.

### `analyze-codebase` — espelho do setup

**Carrega / interpreta** igual ao setup, com prompts e artefatos de codebase:

1. Exploração.
2. Questionário opcional.
3. Gera os 7 docs em `.pulse/specs/codebase/`.

UI: `phase1`, `phase2`.

## 6. Tabela: o que o Pulse interpreta vs o que só o agente lê

| Artefato | `new-issue` | `fix-bug` | `setup` / `analyze` |
| --- | --- | --- | --- |
| `workflow.yaml` | Pulse lê/escreve e decide fases | — | — |
| `PRD.md` / `TECHSPEC.md` / `tasks.md` | Agente escreve; Pulse synca tasks e mostra no painel | — | — |
| `TASK.md` / `SUMMARY.md` | — | Agente; histórico lê status | — |
| `project/*` / `codebase/*` | Agente (contexto) | Agente | Agente gera |
| bloco ` ```text ` | Pulse classifica aprovação | Pulse classifica aprovação | Pulse injeta no prompt fase 2 |
| `cursor/ask_question` / MCP | Resposta volta ao agente | idem | idem |
| gates de shell | Pulse roda no Execute | — | — |

## 7. Relação UI ↔ orquestrador ↔ agente

```
┌─────────────────┐     begin_phase / LogEntry      ┌──────────────┐
│  CockpitState   │ ◄───────────────────────────────│ CockpitSink  │
│  (só memória)   │                                  └──────▲───────┘
└────────┬────────┘                                         │
         │ configure / set_tasks                    session/update
         │                                          ┌───────┴───────┐
┌────────▼────────┐     workflow.yaml / prompts     │ AcpSession    │
│  Flow Python    │ ───────────────────────────────►│ Runner + ACP  │
│  (orquestrador) │ ◄── aprovação / gates / reload  │               │
└────────┬────────┘                                  └───────────────┘
         │
         ▼
   .pulse/specs/...   (disco = resume + histórico)
```

## Design

**O que:** workflows como funções Python + um catálogo de IDs; estado interpretável só onde o orquestrador precisa (`workflow.yaml` no new-issue).

**Por quê:** o agente já segue a skill no disco. O Pulse precisa de máquina de estados só para resume, aprovação e gates — o resto é prompt.

**Alternativas:** DSL YAML de pipelines, plugins, um workflow.yaml genérico para todos.

**Trade-off:** novo workflow = código novo em `spec_types`, `runner`, flow, `WORKFLOW_PHASES` e prompts. Config por projeto não muda o comportamento do pipeline, só o modelo/agente.
