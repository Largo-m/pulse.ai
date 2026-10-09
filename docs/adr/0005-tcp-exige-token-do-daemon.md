# ADR 0005 — O listener TCP exige o token do daemon

## Status

Aceito

## Data

2026-10-08

## Decisores

Jonathan Matos

## Contexto e problema

O [ADR 0003](0003-listeners-locais-recusam-navegador.md) fechou a API para
navegadores e para a rede, mas deixou um achado em aberto (F1 no
[scorecard](../quality-scorecard.md)): **outro usuário do sistema operacional**
na mesma máquina alcança `127.0.0.1:8787`. Loopback não separa usuários. Esse
usuário pode trocar o `permission_policy` para `auto_approve` e iniciar runs,
ou seja, executar agentes com as permissões do dono do daemon.

O socket UDS não tem esse problema: é `0600` (`bind_private_socket`), e o
kernel recusa o `connect` de outro usuário. O TCP não tem nada equivalente.

## Fatores de decisão

- AGENTS.md §6.1: TCP só em `127.0.0.1`, UDS só do usuário; segredos fora de
  logs, eventos e SSE.
- O TCP continua existindo para tooling e para clientes futuros ("um contrato, dois
  transportes" em `ARCHITECTURE.md`).
- A CLI e a TUI usam o UDS; nenhuma configuração nova para o usuário.

## Decisão

1. **Um token por daemon.** Ao subir, o daemon gera
   `secrets.token_urlsafe(32)` e o grava em `~/.pulse/daemon.json` junto com
   pid, host e porta. O arquivo é criado `0600` e, se um daemon antigo o
   deixou mais aberto, é apertado de novo (`write_daemon_meta`). Ler o token
   exige o mesmo que conectar no socket: ser o dono de `~/.pulse`.
2. **Só o TCP cobra.** [`TokenGuard`](../../pulse/api/token_guard.py) (ASGI
   puro, por fora de tudo) envolve só o app do listener TCP
   (`listener_configs` em `pulse/daemon/server.py`). Sem
   `Authorization: Bearer <token>` válido, a resposta é `401` com
   `WWW-Authenticate: Bearer`, e a rota não roda. A comparação usa
   `secrets.compare_digest`. O UDS segue sem token: o SO já protege, e não
   mandar o token por ali diminui por onde ele passa.
3. **O cliente apresenta o token só por TCP.** `EngineClient` lê o token do
   meta quando cai no TCP (ou recebe `http_base`); pelo socket não envia nada.
4. **`ENGINE_PROTOCOL` 8.** Um cliente novo reinicia um daemon anterior ao
   token, que seguiria aceitando TCP sem autenticação.

### Consequências

- Tooling que fala TCP precisa do header:
  `curl -H "Authorization: Bearer $(jq -r .token ~/.pulse/daemon.json)" http://127.0.0.1:8787/api/status`.
- O token muda a cada início do daemon; não há rotação durante a vida dele,
  nem precisa: ele nunca sai da máquina e só vale enquanto o processo vive.
- `pulse daemon status` não mostra o token.
- Um processo do **mesmo** usuário continua tendo acesso, pelo socket ou pelo
  meta. Isso é intencional: o daemon age em nome desse usuário.
- `GET /api/status` também exige o token por TCP. Saber que há um daemon (e
  sua versão) não é segredo forte, mas uma exceção seria uma regra a mais.

## Prós e contras das opções

### 1. Token por daemon no meta `0600` (escolhida)

- Bom: o TCP fica tão protegido quanto o socket, sem config nova; o tooling
  continua possível.
- Ruim: muda o protocolo (bump) e o tooling precisa ler o meta.

### 2. TCP opt-in (desligado por padrão)

- Bom: nenhuma superfície TCP para quem não usa.
- Ruim: quem liga volta a ter o F1 inteiro; seria preciso o token mesmo assim.

### 3. Checar o UID do peer da conexão TCP

- Ruim: não há API portátil para descobrir o dono de uma conexão TCP de
  loopback (no Linux só via `/proc/net/tcp`; no macOS, nada estável).

## Mais informações

- Testes: `tests/api/test_api_token_guard.py`, `tests/infra/test_daemon_meta.py`,
  `tests/client/test_engine_client_transport.py`.
- RFC 6750 (Bearer Token Usage) e RFC 9110 §11 (esquema case-insensitive).
