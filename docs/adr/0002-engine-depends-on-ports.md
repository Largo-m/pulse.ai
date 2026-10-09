# ADR 0002 — O motor depende de portas, não da infraestrutura

## Status

Aceito

## Data

2026-10-08

## Decisores

Jonathan Matos

## Contexto e problema

A [ADR 0001](0001-camada-de-dominio.md) isolou `domain/` e `replies/`, mas
deixou `orchestrator/` livre para usar `store/`, `config/` e `acp/`
diretamente. Na prática, `orchestrator/engine.py` fazia tudo sozinho:

- buscava a definição (`get_workflow`), resolvia a config (`resolve_config`),
  checava o runtime (`check_runtime_ready`, do `doctor/`) e montava o
  `AcpSessionRunner` com `cwd`, comando e política;
- gravava a run chamando `store.runs` em `engine.py`, `loops.py` e `waits.py`;
- abria worktree chamando `pulse.vcs` e `store.paths.worktrees_dir()`;
- descobria o que o stream sabia fazer com `getattr(stream, "info", None)` e
  `is_cockpit_stream` (um atributo `cockpit` que nenhuma porta declarava),
  e com isso escolhia entre levantar exceção ou imprimir no terminal.

Os custos eram concretos:

- **Testar o motor exigia remendar módulos.** Os testes trocavam
  `engine.AcpSessionRunner`, `engine.resolve_config`,
  `engine.check_runtime_ready` e `engine.is_interactive` por `monkeypatch`;
  um nome renomeado no motor quebrava teste sem quebrar comportamento.
- **O contrato do adapter era implícito.** Quem escrevia um sink novo só
  descobria `info`, `error`, `apply_phase_statuses` e `set_session_id` lendo
  os `getattr` do motor; esquecer um deles calava a UI sem erro.
- **Dois modos dentro do motor.** "Cockpit" e "terminal" eram ramos `if` em
  `run_workflow`, embora só o daemon chame o motor.
- **`get_runtime` caía no runtime padrão para id desconhecido**, contrariando
  "id desconhecido não existe" (AGENTS.md §2.2.3): um typo na config abria
  outro CLI em silêncio.

## Fatores de decisão

- AGENTS.md §2.1: "nova I/O precisa de uma porta primeiro, depois adapters".
- Testes do motor com fakes que implementam a porta, sem `monkeypatch` de
  módulo e sem `MagicMock` (AGENTS.md §5.1).
- A regra tem que ser verificável: contrato do import-linter e `mypy --strict`.
- Nenhuma rota, evento SSE ou tabela pode mudar.

## Opções consideradas

1. Manter o motor como está e só tipar os parâmetros com `Protocol`.
2. Portas para cada efeito do motor (stream, prompts, repositório, sessão do
   agente, workspace, perfil do agente), injetadas por `run_workflow` e
   montadas no daemon.
3. Um container de injeção de dependência (biblioteca externa).

## Decisão

Opção 2. O motor recebe tudo o que faz efeito por injeção, e só o daemon
(composition root) sabe quais adapters existem.

As portas moram em [`pulse/domain/ports.py`](../../pulse/domain/ports.py):

| Porta | O que o motor pede | Adapter de produção | Fake |
|---|---|---|---|
| `StreamSink` | mostrar o progresso da run | `ApiStreamSink` (`daemon/`) | `NullStreamSink` |
| `PromptPort` | perguntar à pessoa | `ApiPromptPort` (`daemon/`) | `NullPromptPort` |
| `RunRepository` | criar, carregar e gravar a run; listar artefatos | `SqliteRunRepository` (`store/`) | `InMemoryRunRepository` (testes) |
| `AgentSession` | abrir o agente, rodar um step, reviver | `AcpSessionRunner` (`acp/`) | `FakeAgentSession` (testes) |
| `Workspace` | branch atual e worktree da run | `GitWorkspace` (`vcs/`) | `FakeWorkspace` (testes) |
| `AgentProfiles` | model, política e instruções do agente de um step | `ConfiguredAgentProfiles` (`config/`) | `FixedAgentProfiles` (testes) |

- **`StreamSink` completo.** `info`, `error`, `apply_phase_statuses` e
  `set_session_id` entram no `Protocol`, e o motor chama sem `getattr`. O
  atributo `cockpit` some: o motor não tem mais dois modos. Falha de preparo
  (worktree que não abre, workflow sem step) sempre vira exceção para quem
  chamou. Um terminal sem TUI, quando existir, será outro adapter de
  `StreamSink`, desenhando a partir dos mesmos eventos que o cockpit recebe.
- **`AgentProfiles` é a sexta porta**, não prevista no plano: a resolução do
  model e da política por step lia `config/` e `store/`, e sem ela o motor
  continuaria preso aos dois.
- **`AgentSession.open(cwd)`** recebe o diretório na abertura, não no
  construtor: o daemon monta a sessão antes de o motor saber se a run vai
  trabalhar num worktree.
- **O daemon monta as portas** em [`daemon/runs.py`](../../pulse/daemon/runs.py):
  busca a definição, resolve a config, checa o runtime e só então chama
  `run_workflow(definition=…, ports=…)`.
- **`get_runtime` levanta `UnknownRuntime`** para id desconhecido.
- **Novo contrato no import-linter**: `orchestrator/` não importa `acp/`,
  `store/`, `vcs/` nem `doctor/` — nem direta nem indiretamente. Como
  `config/` e `runtimes/` chegam a `store/` e `acp/`, o motor também deixou de
  importá-los.
- **`mypy --strict` passa a cobrir `orchestrator/`**, com as mesmas flags do
  domínio.

### Consequências

**Boas**

- O motor roda inteiro em memória nos testes: os fakes implementam as portas e
  o `mypy` confere que implementam.
- O contrato de um adapter novo é o `Protocol`; esquecer um método é erro de
  tipo, não uma tela muda.
- `run_workflow` perdeu o ramo "terminal" e a checagem de TTY; quem decide
  como mostrar é o adapter.
- Trocar SQLite, git ou ACP por outra coisa é escrever um adapter.

**Ruins**

- `run_workflow` recebe mais parâmetros, agrupados em `EnginePorts`.
- O `AcpSessionRunner` continua sendo o adapter e a implementação do
  transporte ACP ao mesmo tempo; separar os dois fica para depois.
- Os fakes vivem em `tests/` e precisam acompanhar a porta; o `mypy` nos
  testes não roda, então a garantia vem dos testes de contrato que exercitam
  adapter e fake com as mesmas asserções.

**Neutras**

- Nenhuma rota, evento SSE ou tabela mudou.

## Prós e contras das opções

### 1. Só tipar os parâmetros

- Bom, porque o diff é pequeno.
- Ruim, porque o motor continuaria importando `store/`, `acp/` e `vcs/`, e o
  contrato de import não teria o que proibir.

### 2. Portas injetadas, montadas no daemon

- Bom, porque é o Ports & Adapters que o AGENTS.md já pede, aplicado ao motor.
- Bom, porque a regra vira contrato do import-linter.
- Ruim, porque toca o motor e todos os seus testes de uma vez.

### 3. Container de injeção

- Bom, porque automatiza a montagem.
- Ruim, porque adiciona dependência para montar um grafo que cabe em uma
  função, contra "a estrutura mais simples que resolve" (AGENTS.md §2.3).

## Mais informações

- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §2 e §3.5.
- [`AGENTS.md`](../../AGENTS.md) §2.1.
- [ADR 0001](0001-camada-de-dominio.md).
