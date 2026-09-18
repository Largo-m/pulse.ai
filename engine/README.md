# Pulse Engine

Daemon composition root do Pulse.

## Entrypoints

```bash
pulse-engine
# ou
python -m pulse.daemon serve
```

Expõe a mesma API em:

- Unix Domain Socket: `~/.pulse/daemon.sock` (CLI)
- HTTP TCP: `127.0.0.1:8787` (tooling / clientes futuros)

Código: [`pulse/daemon/`](../pulse/daemon/), [`pulse/api/`](../pulse/api/), domínio em `pulse/{acp,plan,config,history,...}`.

Contrato: [`contracts/openapi.yaml`](../contracts/openapi.yaml).
