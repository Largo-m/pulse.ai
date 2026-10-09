# Pulse

Orquestrador de agentes de IA via ACP, terminal-first. Suporta **Cursor**
(`agent` CLI) e **Claude Code** (`claude` CLI).

A responsabilidade do Pulse é uma só: **apontar qual agente roda agora e
quando**. Ele não sabe o que o agente faz. Workflows, steps e agentes são dado
em SQLite — o pacote não traz pipeline, prompt de domínio nem skill embutida.

Documentação de arquitetura (camadas, fluxos, glossário): [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Arquitetura

```
CLI (TUI)  --HTTP/UDS-->  Engine daemon  --ACP-->  runtime (Cursor | Claude Code)
```

- **Engine** (`pulse-engine`): composition root; dono do estado e das definições.
  Código em [`pulse/daemon/`](pulse/daemon/) e [`pulse/api/`](pulse/api/).
- **CLI** (`pulse`): cliente fino, somente TUI Textual. Código em
  [`pulse/cli/main.py`](pulse/cli/main.py), [`pulse/tui/`](pulse/tui/) e
  [`pulse/client/`](pulse/client/).
- O daemon expõe a mesma API em dois transportes: Unix Domain Socket
  `~/.pulse/daemon.sock` (usado pela CLI) e HTTP em `127.0.0.1:8787` (tooling).
- Contrato: [`contracts/openapi.yaml`](contracts/openapi.yaml)

```bash
pulse daemon start|status|stop
pulse-engine                  # foreground (= python -m pulse.daemon serve)
pulse-engine --host 127.0.0.1 --port 8787
```

`--host` só aceita endereço de loopback, e a API recusa requests de navegador
([ADR 0003](docs/adr/0003-listeners-locais-recusam-navegador.md)). Por TCP, toda
request leva o token do daemon, que muda a cada início
([ADR 0005](docs/adr/0005-tcp-exige-token-do-daemon.md)):

```bash
curl -H "Authorization: Bearer $(jq -r .token ~/.pulse/daemon.json)" \
  http://127.0.0.1:8787/api/status
```

## Runtimes suportados

Um *runtime* é o backend que executa um Pulse agent. Cada um declara binário,
comando ACP, checagens de ambiente e como aplicar modo e modelo:

| Runtime | Binário | Comando ACP | Autenticação |
| --- | --- | --- | --- |
| `cursor` | `agent` | `agent acp` | `agent login` ou `CURSOR_API_KEY` |
| `claude` | `claude` | `npx -y @agentclientprotocol/claude-agent-acp@0.86.0` | `claude /login` ou `ANTHROPIC_API_KEY` |

O Claude Code não fala ACP nativamente: o Pulse usa o adapter oficial distribuído
via npm, então o **Node.js 18+ (`npx`) precisa estar no PATH**. O adapter herda o
login do `claude` CLI — não há passo de autenticação separado.

Modelos do runtime `claude`: `default`, `opus[1m]`, `claude-fable-5-1`, `sonnet`,
`haiku`.

O registry fica em [`pulse/runtimes/`](pulse/runtimes/): adicionar um agente novo
é escrever um módulo com a subclasse de `AgentRuntime` e registrá-lo em
`RUNTIMES`. O resto do Pulse (config, doctor, onboarding, session runner) passa a
enxergá-lo sem mudanças.

## Instalação

```bash
pipx install -e .
```

## Primeiro uso

```bash
pulse init
```

O wizard pergunta qual runtime será o padrão e verifica:

- o binário do runtime no PATH (`agent`, ou `claude` + `npx`)
- autenticação (`agent login`/`CURSOR_API_KEY`, ou `claude /login`/`ANTHROPIC_API_KEY`)
- conexão ACP com prompt de teste
- diretório padrão, modelo e política de permissões

O `pulse doctor` reprova apenas o runtime ativo; os demais aparecem como aviso.
Assim uma máquina que só tem o Claude não falha por não ter o Cursor instalado.

A configuração da máquina e dos projetos é salva em `~/.pulse/pulse.db`.
Ao final, o `pulse init` também registra o workspace no SQLite (se ainda não existir).

## Configuração por projeto

Cada projeto tem um `project_id` no SQLite da máquina. A resolução segue:

```
defaults do código → machine (SQLite) → project_* (mesmo SQLite, por root_path)
```

`pulse init` e `pulse config init` cadastram o projeto sem agent, model nem
`permission_policy`: vazio herda da máquina, que é onde o onboarding grava a
escolha.

Campos por projeto: agent, model, permission_policy, workspace, use_worktree e
`workflows.*` (override de agent/model por id de workflow — não definem
pipeline).

Agents do projeto podem sobrescrever ou estender os da máquina (binary, models,
acp_command).

### Worktree por run

Projeto que é repositório git pode ligar **Worktree** em *Configurações*. Com a
chave ligada, cada run abre a própria cópia de trabalho:

```
~/.pulse/worktrees/<run_id>     branch  pulse/<workflow>-<run curto>
```

A árvore de trabalho do editor fica intocada, duas runs simultâneas param de se
atropelar, e revisar a entrega de uma run vira um `git diff` de uma branch.

O worktree **fica** quando a run acaba — ele é a entrega. Sai pelo detalhe da
run no Histórico (tecla `w`) ou junto quando a run é apagada; com mudança não
commitada dentro, é mantido e o Pulse avisa. A branch sempre fica.

Desligada a chave (o padrão), a run roda na raiz do projeto como sempre. Nos
dois casos a sessão mostra a branch atual ao lado do modelo.

### Workflows

Um workflow é uma linha em `workflow_defs` mais N em `workflow_steps`, no
`~/.pulse/pulse.db`. Cada step diz **qual agente** roda, **qual prompt** ele
recebe e se o Pulse deve **esperar aprovação** antes de seguir.

O banco nasce semeado ([`pulse/store/factory/`](pulse/store/factory/)) com os
loops de fábrica, que aparecem no menu **Nova sessão**:

| Loop | Steps |
| --- | --- |
| Nova spec | PRD → Techspec → Tasks → Implementar → Review ⇄ Fix review (laço, até 3 rodadas) |
| Correção rápida | Quick plan → Quick implement |
| Review | Review ⇄ Fix review (laço, até 3 rodadas) da branch atual vs `main`, roda direto |
| Setup do projeto | Entrevista → Artefatos (roda direto, sem aprovar) |
| Analisar codebase | Exploração → Documentação (roda direto, sem aprovar) |

Há ainda o loop genérico `default` ("Executar", um step sem pipeline). Ele não
entra no menu — repassar o prompt cru ao agente é o que se faz no terminal —
mas continua no banco e em `/api/workflows`, para quem chama o daemon direto.

A semeadura é `INSERT OR IGNORE`: quem editou não perde nada no upgrade, e linha
de fábrica apagada volta na abertura seguinte. Não há tela para editar workflows
ainda — quem quiser outro pipeline escreve no banco via
`pulse.store.workflow_defs`.

O Pulse abre uma sessão ACP **isolada por step** — o agente seguinte recebe só o
resumo do anterior, não o contexto. É o que permite trocar de runtime entre steps
e retomar uma run refazendo um step só.

O que o agente escreve fica onde o prompt do step mandar; o Pulse descobre pelos
tool-calls do ACP e guarda só o caminho. Não há convenção de pasta.

Modelo completo: [`docs/workflows.md`](docs/workflows.md).

A resolução por workflow segue: `projeto.workflows[id]` → `global.workflows[id]` →
`projeto.defaults` → `global.defaults` → padrões do código.

Veja a config efetiva (inclusive por workflow):

```bash
pulse config show
pulse config show --workflow default
```

## Documentação interna

Como o Pulse funciona hoje (código atual):

- [Armazenamento](docs/armazenamento.md) — o que é persistido e onde
- [Agentes](docs/agentes.md) — agentes e o loop de execução, passo a passo
- [Workflows](docs/workflows.md) — workflow como dado: definição, motor e retomada
- [Logs](docs/logs.md) — ACP bruto vs stream do cockpit
- [Questions](docs/questions.md) — questionário ` ```text `, `ask_question` e MCP

## Comandos

Toda run é iniciada pelo menu interativo do `pulse` — não há subcomando de workflow.

```bash
pulse                  Welcome + menu interativo (ou wizard no primeiro uso)
pulse init             Wizard de onboarding
pulse init --force     Reconfigurar
pulse doctor           Verificar ambiente
pulse doctor --test-acp Incluir teste ACP
pulse config           Mostrar config efetiva (global + projeto)
pulse config init      Registrar o projeto atual no SQLite
```
