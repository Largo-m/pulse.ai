# Pulse

Orquestrador terminal-first de workflows com agentes de IA via ACP. Suporta
**Cursor** (`agent` CLI) e **Claude Code** (`claude` CLI).

Documentação de arquitetura (camadas, fluxos, glossário): [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Arquitetura

```
CLI (TUI)  --HTTP/UDS-->  Engine daemon  --ACP-->  runtime (Cursor | Claude Code)
```

- **Engine** (`pulse-engine`): composition root; dono do estado e dos workflows
- **CLI** (`pulse`): cliente fino + TUI; fala com o daemon em `~/.pulse/daemon.sock`
- Contrato: [`contracts/openapi.yaml`](contracts/openapi.yaml)

```bash
pulse daemon start|status|stop
pulse-engine   # foreground
```

## Runtimes suportados

Um *runtime* é o backend que executa um Pulse agent. Cada um declara binário,
comando ACP, checagens de ambiente e como aplicar modo e modelo:

| Runtime | Binário | Comando ACP | Autenticação |
| --- | --- | --- | --- |
| `cursor` | `agent` | `agent acp` | `agent login` ou `CURSOR_API_KEY` |
| `claude` | `claude` | `npx -y @agentclientprotocol/claude-agent-acp` | `claude /login` ou `ANTHROPIC_API_KEY` |

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

`pulse init` e `pulse config init` cadastram o projeto com defaults: agent `cursor`, model `claude-sonnet-4-6`, `permission_policy` `deny_writes`, e workflows `spec` / `setup-project` / `analyze-codebase`.

Campos por projeto: agent, model, permission_policy, workspace e `workflows.*`.

Agents do projeto podem sobrescrever ou estender os da máquina (binary, models, acp_command).

### Agentes e workflows

- `agents` define cada backend ACP (binário e modelos disponíveis). O comando ACP
  vem do runtime registrado; use `acp_command` apenas para sobrescrever.
- `defaults.agent` / `defaults.model` definem o agente e modelo padrão.
- `workflows.<id>` permite que cada workflow use um agente e modelo próprios.

Workflows disponíveis: `spec`, `setup-project`, `analyze-codebase`.

O workflow `spec` classifica o pedido (auto-sizing da skill) e dispara o pipeline
Specify → Design → Tasks → Execute **ou** o Quick Mode. O usuário não escolhe feat vs fix.

O pipeline completo aponta a skill empacotada `pulse-spec-driven` (paths, sem inline). Rules,
skills e `AGENTS.md` do workspace são carregados pelo ACP a partir do `cwd`.
No Execute, `coding-principles.md` entra nas referências da skill. As tasks do
`tasks.md` são agrupadas em **waves** (até 5 tasks prontas por sessão):
sequenciais quando compartilham dependências resolvidas, e em batch quando
marcadas `[P]`. O Pulse só marca a wave como `done` depois de rodar os
comandos de gate extraídos do `Done when` / `Verify`.

O Quick Mode (quando o `spec` classifica o pedido como Small) descreve →
plano + `.pulse/specs/quick/NNN-slug/TASK.md` → aprovação no terminal → implementa →
verifica → `SUMMARY.md`. Nada de código de aplicação é alterado sem aprovação
explícita.

A resolução por workflow segue: `projeto.workflows[id]` → `global.workflows[id]` →
`projeto.defaults` → `global.defaults` → padrões do código.

Veja a config efetiva (inclusive por workflow):

```bash
pulse config show
pulse config show --workflow setup-project
```

## Documentação interna

Como o Pulse funciona hoje (código atual):

- [Armazenamento](docs/armazenamento.md) — o que é persistido e onde
- [Workflows — carga e interpretação](docs/workflows.md) — como cada workflow é carregado e interpretado
- [Workflows e skills](docs/workflows-e-skills.md) — skills empacotadas vs do projeto no prompt
- [Logs](docs/logs.md) — ACP bruto vs stream do cockpit
- [Questions](docs/questions.md) — questionário ` ```text `, `ask_question` e MCP

## Comandos

Todos os workflows são iniciados pelo menu interativo do `pulse` — não há subcomando `plan`.

```bash
pulse                  Welcome + menu interativo (ou wizard no primeiro uso)
pulse init             Wizard de onboarding
pulse init --force     Reconfigurar
pulse doctor           Verificar ambiente
pulse doctor --test-acp Incluir teste ACP
pulse config           Mostrar config efetiva (global + projeto)
pulse config init      Registrar o projeto atual no SQLite
```
