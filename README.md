# Pulse

Orquestrador terminal-first de workflows com agentes de IA via Cursor.

## Instalação

```bash
pipx install -e .
```

## Primeiro uso

```bash
pulse init
```

O wizard verifica:

- `agent` no PATH
- autenticação (`agent login` ou `CURSOR_API_KEY`)
- conexão ACP com prompt de teste
- diretório padrão, modelo e política de permissões

A configuração global é salva em `~/.pulse/config.toml`. Ao final, o `pulse init`
também cria um `.pulse/config.yaml` no workspace escolhido (se ainda não existir).

## Configuração por projeto

Cada projeto pode ter suas próprias preferências em `.pulse/config.yaml`, que
sobrescrevem a config global. A resolução segue as camadas:

```
defaults do código → ~/.pulse/config.toml (global) → <projeto>/.pulse/config.yaml (projeto)
```

O template padrão gerado por `pulse init` e `pulse config init` é:

```yaml
version: 1

defaults:
  agent: cursor
  model: claude-sonnet-4-6
  permission_policy: deny_writes

workspace:
  root: .

workflows:
  new-issue:
    agent: cursor
    model: Auto
  fix-bug:
    agent: cursor
    model: Auto
  setup-project:
    agent: claude
    model: claude-opus-4.8
  analyze-codebase:
    agent: cursor
    model: gpt-5.5
```

Campos sobrescrevíveis por projeto: `defaults.agent`, `defaults.model`,
`permission_policy`, `workspace.root` e `workflows.*`.

Opcionalmente, um bloco `agents:` no YAML do projeto pode sobrescrever ou
estender os agents do `~/.pulse/config.toml` (binary, models, acp_command).

### Agentes e workflows

- `agents` define cada backend ACP (binário e modelos disponíveis). O comando ACP é
  derivado do binário (`<binary> acp`); use `acp_command` apenas para sobrescrever.
- `defaults.agent` / `defaults.model` definem o agente e modelo padrão.
- `workflows.<id>` permite que cada workflow use um agente e modelo próprios.

Workflows disponíveis: `new-issue`, `fix-bug`, `setup-project`, `analyze-codebase`.

O workflow `new-issue` executa o pipeline Specify → Design → Tasks → Execute.
Nas fases de planejamento (Specify/Design/Tasks) o Pulse envia só o **índice** de
rules/skills do projeto (sem inline). No Execute, rules são inlined e
`coding-principles.md` entra no prompt. As tasks do `tasks.md` são agrupadas em
**waves** (até 5 tasks prontas por sessão): sequenciais quando compartilham
dependências resolvidas, e em batch quando marcadas `[P]`. O Pulse só marca a
wave como `done` depois de rodar os comandos de gate extraídos do `Done when` /
`Verify`.

O workflow `fix-bug` executa o Quick Mode do `tlc-spec-driven`: descreve →
plano + `.pulse/specs/quick/NNN-slug/TASK.md` → aprovação no terminal → implementa →
verifica → `SUMMARY.md`. Nada de código de aplicação é alterado sem aprovação
explícita. A fase de plano também usa contexto em índice; a implementação usa
contexto completo.

A resolução por workflow segue: `projeto.workflows[id]` → `global.workflows[id]` →
`projeto.defaults` → `global.defaults` → padrões do código.

Veja a config efetiva (inclusive por workflow):

```bash
pulse config show
pulse config show --workflow setup-project
```

## Comandos

Todos os workflows são iniciados pelo menu interativo do `pulse` — não há subcomando `plan`.

```bash
pulse                  Welcome + menu interativo (ou wizard no primeiro uso)
pulse init             Wizard de onboarding
pulse init --force     Reconfigurar
pulse doctor           Verificar ambiente
pulse doctor --test-acp Incluir teste ACP
pulse config           Mostrar config efetiva (global + projeto)
pulse config init      Criar .pulse/config.yaml no projeto atual
```
