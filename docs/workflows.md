# Como o Pulse carrega e interpreta workflows

O Pulse **não conhece nenhum workflow por código**. Não há catálogo em Python,
nem `AGENT.md`/`PHASE.md` no pacote, nem skill embutida. Um workflow é um
conjunto de linhas no SQLite, e a única responsabilidade do Pulse é apontar
**qual agente roda agora** e **quando**.

## 1. Onde um workflow é definido

Tabelas em `~/.pulse/pulse.db` (ver [armazenamento.md](armazenamento.md)):

```
workflow_defs     id, label, description, is_default
workflow_steps    workflow_id, step_id, position, label,
                  agent_id, prompt_template, requires_approval
agent_defs        id, label, runtime, model, permission_policy, instructions
```

Acesso: [`pulse/store/workflow_defs.py`](../pulse/store/workflow_defs.py).

A configuração de fábrica é **semente do banco**, não arquivo do pacote: o
`SEED` em [`pulse/store/db.py`](../pulse/store/db.py) roda com `INSERT OR IGNORE`
na primeira abertura e cria um workflow `default` de um step só. Como é
`OR IGNORE`, quem já editou não perde nada no upgrade.

Id que não está em `workflow_defs` não existe: `run_workflow` levanta
`UnknownWorkflow`, e a API responde 404.

## 2. O laço do motor

[`pulse/orchestrator/engine.py`](../pulse/orchestrator/engine.py) — uma função
pública, `run_workflow`, e nenhum `if workflow_id == ...`:

```
run_workflow(workflow_id, user_prompt, …)
  │
  ├─ get_workflow(id)                 definição + steps, do banco
  ├─ resolve_config(workflow=id)      runtime, model, policy, cwd
  ├─ create_run | load_run            linha em `runs` + N em `run_steps`
  └─ para cada step pendente:
       control.checkpoint()           barreira de pausa/parada
       resolve_config(pulse_agent=…)  o agente DESTE step
       runner.use_agent(…)
       render(step.prompt_template)   valores da run
       run_isolated_phase | run_isolated_prompt
       save_step(status, summary)     desfecho no banco
```

A sessão ACP é **isolada por step**. O agente do step seguinte não herda o
contexto do anterior — só o resumo que o Pulse repassa. É isso que permite
trocar de runtime entre steps e retomar uma run refazendo um step só.

### Valores disponíveis no `prompt_template`

`{{chave}}`, e `{{#if chave}}…{{/if}}` para trecho opcional
([`pulse/prompts/render.py`](../pulse/prompts/render.py)). Chave sem valor é
**erro**, não buraco: instrução truncada sairia silenciosa.

| Chave | Conteúdo |
| --- | --- |
| `user_prompt` | o que o usuário pediu |
| `workspace` | diretório da run |
| `workflow_id` / `run_id` / `step_id` / `step_label` | identidade do passo |
| `previous_summary` | resposta do último step que produziu resumo |
| `artifacts` | arquivos que a run já escreveu, um por linha |

Não há chave com nome de artefato ou de fase: o motor não tem nenhum para
oferecer.

## 3. O que o motor interpreta da resposta do agente

Só o desfecho do questionário de aprovação
([`pulse/prompts/approval.py`](../pulse/prompts/approval.py)), quando o step tem
`requires_approval`:

| Desfecho | O que o Pulse faz |
| --- | --- |
| `approve` | step vira `done`, segue para o próximo |
| `adjust` / `continue` | devolve a conversa ao agente com as respostas |
| `skip` | step vira `skipped` — não é falha |
| `cancel` | step não fechou; cai no menu de retry |

Step sem aprovação só precisa que o agente feche o turno (`stopReason`).

Falha ou não-aprovação abre o menu **Refazer / Outro — dizer o que fazer /
Parar**. "Outro" injeta a orientação do usuário no prompt da tentativa seguinte.

O conteúdo do que o agente produziu **nunca** é interpretado. O Pulse não lê
Markdown, não valida formato, não espera arquivo com nome conhecido.

## 4. Estado, retomada e artefatos

| Tabela | Para quê |
| --- | --- |
| `runs` | de onde retomar (`current_step`, `status`) |
| `run_steps` | status, resumo e sessão ACP de cada step |
| `run_events` | o stream que o cockpit reexibe |
| `run_artifacts` | caminhos que o agente escreveu |

Retomar = rodar o primeiro step que não está `done`/`skipped`. Refazer
(`restart`) zera `run_steps` mantendo a run.

Pausar corta o turno em voo e devolve o step em curso para `pending`: ele não
terminou, então é refeito inteiro. Step já fechado nunca é refeito.

Artefato é descoberto pelos **tool-calls do ACP**: um `write`/`edit`/`create`
faz o Pulse gravar o caminho em `run_artifacts`
([`session_runner._record_artifacts`](../pulse/acp/session_runner.py)). Não há
convenção de pasta nem de extensão.

## 5. Config por workflow e por agente

`machine_workflows` e `project_workflows` guardam **override** de agent/model
por id de workflow — não definem pipeline nenhum, e nascem vazios.

```
agent_defs[step.agent_id]            runtime/model/policy declarados
  → agent_settings (por projeto)     o que o usuário ajustou na TUI
  → projeto.defaults
  → global.defaults
  → defaults do código
```

Campo vazio em `agent_defs` significa "use o padrão da máquina" — gravar um
runtime concreto na semente congelaria a escolha feita no `pulse init`.

## 6. A UI

[`CockpitState.configure_workflow`](../pulse/tui/state.py) monta a sidebar a
partir de `workflow_steps`, pelo mesmo caminho do motor. Não há mapa de fases na
UI. Workflow desconhecido resulta em sidebar vazia, que se preenche conforme os
steps começam.

## Design

**O quê:** workflow como dado (linhas no banco) e um motor único que só sequencia
steps.

**Por quê:** o Pulse é um orquestrador. Saber o que o agente faz o prendia a um
processo específico — trocar o pipeline exigia mexer em `spec_types`, `runner`,
um flow, o mapa da sidebar e cinco arquivos de prompt.

**Trade-off:** workflow novo agora é `INSERT`, não release. Em compensação não há
tela para editar isso ainda: quem quiser outro pipeline escreve no banco pela
API ou por `pulse.store.workflow_defs`.
