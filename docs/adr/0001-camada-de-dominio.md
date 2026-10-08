# ADR 0001 — Camada de domínio isolada e raiz do pacote só com entry points

## Status

Aceito

## Data

2026-10-08

## Decisores

Jonathan Matos

## Contexto e problema

Até a fase 3 do plano de qualidade, o "domínio" da tabela de camadas do
[`AGENTS.md`](../../AGENTS.md) §2.1 era um conjunto espalhado: `orchestrator/`,
`prompts/`, e os módulos soltos na raiz `ports.py` e `runcontrol.py`. A raiz de
`pulse/` também guardava `cli.py`, `cli_daemon.py`, `paths.py`, `brand.py`,
`status_labels.py` e o pacote `runtime/` (singular, confundido com `runtimes/`).

Isso tinha três custos concretos:

- **Nenhum contrato de import alcançava o domínio de verdade.** O domínio podia
  importar `store/`, `config/` e `acp/`, então "domínio sem I/O" não era
  verificável.
- **Ciclo de pacotes.** `history/models.py` importava `pulse.tui.status_labels`,
  então o daemon carregava `pulse.tui` e `tui ↔ history` formavam um ciclo.
- **Definições anêmicas.** `WorkflowDef`/`StepDef` viviam em
  `store/workflow_defs.py` como sacos de dados; o motor e `orchestrator/loops.py`
  recalculavam laços, teto de rodadas, protocolo de desfecho e filhos de fan-out
  a partir das colunas cruas.

## Fatores de decisão

- As regras de camada precisam ser **contratos do import-linter**, não prosa
  (fase 3).
- Domínio testável sem banco, ACP nem UI.
- Um pacote novo precisa nascer coberto pelos contratos, sem alguém lembrar de
  listá-lo.
- Mudança só de estrutura: nenhum comportamento muda, e a suíte existente prova.

## Opções consideradas

1. Manter a estrutura e só escrever os contratos sobre ela.
2. Criar `domain/` e `replies/` puros, separar a orquestração em camada própria
   e deixar na raiz só os entry points.
3. Mover tudo para uma estrutura em camadas genérica (`domain/`,
   `application/`, `infrastructure/`).

## Decisão

Opção 2, porque é a única que torna "o domínio não depende de nada do Pulse"
uma regra verificável sem reescrever o motor.

- `domain/` reúne valores e regras sem I/O: `run.py`, `workflow.py` (definição
  como value object, com `RepeatRule`, `Loop` e `WorkflowDef.loops()`),
  `outcome.py`, `control.py` (ex-`runcontrol.py`) e `ports.py`.
- `replies/` (ex-`prompts/`) parseia as respostas: aprovação, permissão,
  questionário.
- `domain/` e `replies/` não importam nenhum outro pacote do Pulse.
- `orchestrator/` vira a camada de **orquestração**: usa o domínio, `store/`,
  `config/` e `acp/` para executar a run. `render.py` e `tty.py` vão para lá
  porque só o motor os usa.
- A raiz guarda só `__init__.py` e `__main__.py`. Cada módulo vai para o dono:
  `cli/`, `store/paths.py`, `client/protocol.py`, `tui/brand.py`,
  `history/status_labels.py`, `config/ready.py`.
- `tests/` espelha `pulse/`, uma pasta por pacote.

Os contratos ficam em `[tool.importlinter]` no `pyproject.toml` e rodam em
[`tests/architecture/`](../../tests/architecture/).

### Consequências

**Boas**

- "Domínio sem UI e sem I/O" e "só a CLI abre a TUI" são checados por
  `lint-imports` e pelo `pytest`. O ciclo `tui ↔ history` acabou.
- A definição responde por si (`step.declares_outcome`, `loop.next_round()`,
  `step.for_item()`), e o motor perdeu a aritmética de índices.
- Os contratos "todo pacote menos alguns" são conferidos contra as pastas de
  `pulse/`, então um pacote novo já nasce coberto.

**Ruins**

- Quase todo import do projeto mudou de caminho; branches abertas antes da
  mudança precisam de rebase.
- `client/protocol.py` é lido pelo daemon: a constante mora com o cliente, que
  é o lado que decide reiniciar um daemon velho, e o daemon importa de
  `client/`.
- Ainda há três cadeias indiretas da TUI até `acp/` no `ignore_imports`
  (catálogo de modelos e parsing de model-id); a lista só diminui, mas existe.

**Neutras**

- Nenhuma tabela, rota ou evento mudou por causa desta decisão.

## Prós e contras das opções

### 1. Manter a estrutura

- Bom, porque não mexe em import nenhum.
- Ruim, porque o contrato de domínio teria que listar módulos soltos da raiz
  um a um, e `ports.py`/`runcontrol.py` continuariam sem dono.
- Ruim, porque o ciclo `tui ↔ history` continuaria.

### 2. `domain/` + `replies/` puros, orquestração separada

- Bom, porque cada camada vira um pacote, e um pacote é o que o import-linter
  sabe proibir.
- Bom, porque mantém os nomes do glossário (workflow, step, run, agent).
- Ruim, porque o diff de imports é grande.

### 3. Camadas genéricas (`application/`, `infrastructure/`)

- Bom, porque é um padrão conhecido.
- Ruim, porque troca o vocabulário do Pulse (`orchestrator`, `store`, `acp`)
  por nomes genéricos sem ganhar nenhuma regra a mais.
- Ruim, porque contraria "a estrutura mais simples que resolve" (AGENTS.md §2.3).

## Mais informações

- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §3.5 e a tabela "Pode / Não deve".
- [`AGENTS.md`](../../AGENTS.md) §2.1.
- PRs #44 (estrutura de pastas) e #45 (definição com comportamento), mergeados
  na #43.
