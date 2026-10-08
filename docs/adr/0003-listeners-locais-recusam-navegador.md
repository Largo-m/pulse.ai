# ADR 0003 — Os listeners locais só atendem clientes locais que não são navegador

## Status

Aceito

## Data

2026-10-08

## Decisores

Jonathan Matos

## Contexto e problema

O Pulse abre dois servidores HTTP locais sem autenticação:

- a API do daemon (`/api/*`), em UDS (`~/.pulse/daemon.sock`, `0600`) e em
  TCP (`127.0.0.1:8787`, porta fixa);
- o bridge MCP `AskQuestion` de cada sessão ACP (`127.0.0.1`, porta aleatória).

O bind em loopback impede acesso pela rede, mas não protege de **um navegador
na mesma máquina**. A auditoria final (fase 9) confirmou com teste:

- **CSRF contra loopback.** Uma página qualquer pode fazer
  `fetch("http://127.0.0.1:8787/api/doctor/acp-probe?workspace=…", {method: "POST", mode: "no-cors"})`.
  É um *simple request*: não há preflight, e CORS só esconde a resposta — a
  rota roda. `acp-probe` recebe tudo por query string e sobe um CLI de agente
  no diretório que a página escolher.
- **Pergunta falsa ao usuário.** O bridge MCP lia qualquer corpo como JSON-RPC,
  inclusive `text/plain`; uma página podia pôr na tela uma "pergunta do agente"
  (ex.: "cole seu token"). A spec MCP (transporte Streamable HTTP) exige
  validar `Origin`.
- **DNS rebinding.** Um domínio do atacante que resolve para `127.0.0.1`
  chega ao listener com `Host` dele. A API já tinha `TrustedHostMiddleware`;
  o bridge MCP não checava `Host`.
- **`pulse-engine --host 0.0.0.0`** era aceito e punha a API sem autenticação
  na rede (o `Host: 127.0.0.1` é forjável por qualquer cliente).

## Fatores de decisão

- AGENTS.md §6.1: listener TCP só em `127.0.0.1`, sem CORS permissivo.
- Nenhum cliente legítimo é navegador: a CLI/TUI usa `httpx`, o agente fala
  MCP por HTTP de processo. Nenhum deles envia `Origin`.
- Não mudar o protocolo cliente↔daemon (`ENGINE_PROTOCOL`) nesta fase.

## Decisão

1. **Navegador não entra.** Qualquer request com header `Origin` recebe `403`
   antes de chegar a uma rota — na API ([`BrowserGuard`](../../pulse/api/browser_guard.py),
   ASGI puro, não interfere no SSE) e no bridge MCP
   ([`http_bridge.py`](../../pulse/mcp/http_bridge.py)). Navegadores sempre enviam
   `Origin` em POST e em requests cross-site; nenhum cliente nosso envia.
2. **`Host` precisa ser local** nos dois listeners (`TrustedHostMiddleware` na
   API; `127.0.0.1`/`localhost` no bridge), contra DNS rebinding.
3. **Respostas endurecidas**: `nosniff`, `X-Frame-Options: DENY`,
   `CSP default-src 'none'; frame-ancestors 'none'`, `Referrer-Policy: no-referrer`,
   `Cache-Control: no-store`.
4. **Só loopback**: `pulse-engine` recusa `--host` que não seja loopback
   (`ipaddress.is_loopback` ou `localhost`) com código 2.

### Consequências

- Uma UI web futura para o Pulse precisará de uma decisão nova (token por
  daemon + allowlist de origem); este ADR fecha a porta por padrão.
- HSTS e `Permissions-Policy` não se aplicam: HTTP puro em loopback e nenhuma
  página é renderizada. O `http-sec-audit` os reporta; ficam aceitos aqui.
- **Fica em aberto**: outro *usuário do sistema operacional* na mesma máquina
  alcança `127.0.0.1:8787` (o UDS é `0600`, o TCP não tem equivalente). A
  correção é um token por daemon guardado no meta `0600`, ou TCP opt-in —
  muda o protocolo e fica como follow-up em
  [`quality-scorecard.md`](../quality-scorecard.md).

## Prós e contras das opções

### 1. Recusar `Origin` (escolhida)

- Bom: uma regra, sem estado, cobre CSRF de qualquer origem, inclusive `null`
  e outras portas de `localhost`.
- Ruim: um cliente HTTP não-navegador que envie `Origin` por conta própria é
  recusado — nenhum dos nossos envia.

### 2. Exigir `Content-Type: application/json`

- Ruim: não cobre rotas sem corpo (`acp-probe`, `cancel`) e depende de cada
  rota declarar corpo.

### 3. Token por daemon em todas as requests

- Bom: também fecha o acesso de outros usuários locais.
- Ruim: muda o protocolo cliente↔daemon; maior que o escopo desta fase.

## Mais informações

- Testes: `tests/api/test_api_browser_guard.py`, `tests/api/test_daemon_loopback.py`,
  `tests/infra/test_http_bridge.py`.
- MCP, Streamable HTTP, "Security Warning": servidores devem validar `Origin`
  e fazer bind só em localhost.
