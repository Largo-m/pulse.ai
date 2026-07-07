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

agents:
  cursor:
    binary: agent
    models: [Auto, gpt-5.5]
  claude:
    binary: claude-code
    models: [claude-opus-4.8]

workflows:
  setup-project:
    agent: claude
    model: claude-opus-4.8
  analyze-codebase:
    agent: cursor
    model: gpt-5.5
```

Campos sobrescrevíveis por projeto: `agent`, `model`, `permission_policy` e `workspace.root`.

### Agentes e workflows

- `agents` define cada backend ACP (binário e modelos disponíveis). O comando ACP é
  derivado do binário (`<binary> acp`); use `acp_command` apenas para sobrescrever.
- `defaults.agent` / `defaults.model` definem o agente e modelo padrão.
- `workflows.<id>` permite que cada workflow use um agente e modelo próprios.

Workflows disponíveis: `new-issue`, `fix-bug`, `setup-project`, `analyze-codebase`.

O workflow `fix-bug` executa o Quick Mode do `tlc-spec-driven`: descreve →
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

## Comandos

```bash
pulse                  Welcome + menu (ou wizard no primeiro uso)
pulse init             Wizard de onboarding
pulse init --force     Reconfigurar
pulse doctor           Verificar ambiente
pulse doctor --test-acp Incluir teste ACP
pulse config           Mostrar config efetiva (global + projeto)
pulse config init      Criar .pulse/config.yaml no projeto atual
pulse plan "meu app" --type setup-project   Inicializar projeto via tlc-spec-driven
```
