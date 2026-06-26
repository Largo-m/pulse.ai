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

A configuração global é salva em `~/.dev-orchestrator/config.toml`.

## Comandos

```bash
pulse                  Welcome + menu (ou wizard no primeiro uso)
pulse init             Wizard de onboarding
pulse init --force     Reconfigurar
pulse doctor           Verificar ambiente
pulse doctor --test-acp Incluir teste ACP
pulse plan "meu app" --type setup-project   Inicializar projeto via tlc-spec-driven
```
