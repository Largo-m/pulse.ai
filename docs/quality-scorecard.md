# Scorecard de qualidade — auditoria final (fase 9)

Data: 2026-10-08 · Branch: `chore/final-audit` · Base: fase 8b (`refactor/split-large-modules`)

Quatro skills, rodadas sobre o repositório inteiro: `software-architect`
(scorecard), `tactical-ddd`, `security-audit` (incluindo `http-sec-audit` e
`cors-auditor`) e `python-quality`. Cada achado foi conferido no código antes de
entrar aqui; os corrigidos têm o teste que falhava antes da correção.

## Resumo

| Área | Nota | Leitura |
|---|---|---|
| Arquitetura (`software-architect`, 53 itens) | **26,5/53 — 50 % (D)**; 66 % (C) sem os 13 itens de operação que não cabem numa CLI local | Fronteiras, contratos e invariantes de dados fortes; observabilidade e confiabilidade operacional fracas. D é forçado pelo item STOP-SHIP F1 (abaixo) |
| Domínio (`tactical-ddd`, 0 = rico … 7+ = anêmico) | **Leve, ~2** | Núcleo rico (`RunRecord`, `Outcome`, definições, `RunControl`); anemia nas bordas (`ResolvedConfig` 5) |
| Segurança (`security-audit`) | **3 vulnerabilidades corrigidas, 1 em aberto** | SAST, segredos, dependências e CORS limpos; CSRF em loopback e bind fora de loopback corrigidos |
| Qualidade (`python-quality`) | **Tudo verde** | ruff, format, mypy estrito, vulture, 8 contratos de import, 93 % de cobertura por branch, 98,1 % de mutantes mortos |

## 1. Arquitetura — `software-architect`

Modo SCORECARD de `references/design-review-scorecard.md`: PASS 1, PARTIAL 0,5,
FAIL 0; A ≥ 90 %, B 75–89 %, C 60–74 %, D < 60 %.

| Seção | Nota | Evidência |
|---|---|---|
| A Propósito e escopo | 3/4 | Missão e não-objetivos em `AGENTS.md` §1 e `ARCHITECTURE.md`; requisitos não funcionais não listados |
| B Fronteiras e domínio | 3,5/5 | 8 contratos import-linter; valores congelados no domínio. Ciclos `acp`↔`runtimes` e `store`→`config` agora explícitos no baseline |
| C Contratos | 3,5/5 | `ENGINE_PROTOCOL`, teste de contrato OpenAPI; eventos SSE só em prosa |
| D Dados | 2,5/5 | Run gravada numa transação; migrações só adicionam colunas, sem versão; sem backup; TUI ainda escreve tabelas |
| E Confiabilidade | 1/6 | Timeouts em git e CLIs; SIGTERM não cancela runs nem encerra os processos ACP |
| F Segurança | 5/8 | SQL parametrizado, subprocess em lista, socket `0600`, guarda de navegador, scanners no CI. **F1 FAIL**: TCP sem autenticação contra outro usuário local |
| G Observabilidade | 0,5/7 | Só `pulse doctor` e `docs/logs.md`; o primeiro `logging` do pacote entrou neste PR (traceback de 500) |
| H Testes e entrega | 3/6 | 1 751 testes, cobertura por branch 93 %, mutação 98 %, 3 rodadas aleatórias no CI, matriz 3.11–3.14; sem feature flags nem baseline de performance |
| I IA / agentes | 4,5/7 | Permissão nega por padrão, aprovação humana, `max_rounds`, `parse_outcome` falha seguro; sem harness de avaliação, orçamento de custo ou versão de prompt |

Os invariantes de dados de `AGENTS.md` §2.2 se mantêm: nenhum conteúdo de
domínio fora da semente de fábrica, nenhum `if workflow_id == …`.

## 2. Domínio — `tactical-ddd`

| Classe / módulo | Nota | Observação |
|---|---|---|
| `RunRecord`, `StepRecord`, `StepStatus`/`RunStatus` | 0–2 | Transições por método com guarda; só `created_at`/`updated_at` como `str` |
| `RunControl`, `Outcome`/`parse_outcome` | 0 | Encapsulados; `Outcome` falha seguro para `MISSING` |
| `WorkflowDef`, `StepDef`, `RepeatRule`, `Loop` | 0 | `Loop` ganhou invariante neste PR |
| Orquestrador | Leve | Coordenador fino: toda transição é método do agregado |
| `replies/approval.py` | 0 | Desfechos viraram `ApprovalOutcome` neste PR |
| `PhaseItem` (history) | 7 → ~2 | Cadeias de setter na TUI viraram `end_as`, `restart`, `show_closed`, `resume_clock` |
| `HistoryItem`, `HistoryStatus` | 2 | Segundo vocabulário de status da run (`in_progress` × `running`) |
| `ResolvedConfig` | 5 | Saco de dados; tuplas `(valor, fonte)` e uma de 6 posições; fontes como `str` |

## 3. Segurança — `security-audit`

| Ferramenta | Resultado |
|---|---|
| `sast-lite pulse/` | Nenhum achado |
| `secret-scanner .` | Nenhum segredo. Com `--include-tests`, só os fixtures fictícios dos testes do próprio scanner (`AKIA…EXAMPLE`) — falso positivo |
| `dependency-check --online` | `pyproject.toml` e as 54 dependências instaladas (`pip freeze`) consultadas no OSV.dev: nenhuma vulnerabilidade conhecida |
| `http-sec-audit` (headers reais via `TestClient`) | Antes: 6 achados (CSP, HSTS, nosniff, XFO, Referrer, Permissions). Depois: 2, aceitos — HSTS não tem efeito em HTTP puro em loopback e nenhuma página é renderizada |
| `cors-auditor` (origem `https://evil.example`, GET e preflight) | Nenhuma configuração permissiva. CORS não era o problema: veja CSRF abaixo |
| `prompt-injection-tester` | Não rodado de novo: nenhum prompt de fábrica nem parser de saída do agente mudou; `tests/architecture/test_prompt_injection.py` segue verde |

### Corrigidos neste PR

| Sev. | CWE | Achado | Correção | Teste |
|---|---|---|---|---|
| Alta | 352 | Uma página no navegador fazia `POST` *no-cors* para `127.0.0.1:8787/api/doctor/acp-probe?workspace=…` sem preflight; a rota subia um CLI de agente no diretório escolhido | `BrowserGuard`: `403` para request com `Origin`, mais headers de endurecimento | `tests/api/test_api_browser_guard.py` |
| Média | 352 / 350 | O bridge MCP `AskQuestion` aceitava corpo `text/plain` de qualquer origem (pergunta falsa na tela do usuário) e não checava `Host` (DNS rebinding) | Recusa `Origin` e `Host` não local, como exige a spec MCP | `tests/infra/test_http_bridge.py` |
| Alta | 1327 | `pulse-engine --host 0.0.0.0` punha a API sem autenticação na rede | `--host` só aceita loopback; senão sai com código 2 | `tests/api/test_daemon_loopback.py` |

Decisão registrada em [ADR 0003](adr/0003-listeners-locais-recusam-navegador.md).

### Corrigido depois (branch `fix/tcp-daemon-token`)

| Sev. | CWE | Achado | Correção | Teste |
|---|---|---|---|---|
| Alta | 306 | **F1 — outro usuário do SO alcançava o TCP.** O UDS é `0600`, mas `127.0.0.1:8787` atendia qualquer processo local: dava para trocar `permission_policy` e iniciar uma run | Token por daemon no meta `0600`; `TokenGuard` cobra `Authorization: Bearer` só no TCP (`401`); `ENGINE_PROTOCOL` 8 | `tests/api/test_api_token_guard.py`, `tests/infra/test_daemon_meta.py`, `tests/client/test_engine_client_transport.py` |

Decisão registrada em [ADR 0005](adr/0005-tcp-exige-token-do-daemon.md).

## 4. Qualidade — `python-quality`

| Verificação | Resultado |
|---|---|
| `ruff check .` / `ruff format --check .` | Limpo / 313 arquivos formatados |
| `mypy` (estrito) | Nenhum problema em 131 arquivos |
| `vulture` | Nenhum código morto |
| `lint-imports` | 8 contratos mantidos, 0 quebrados (2 novos neste PR) |
| `pytest --cov` | Verde; cobertura por branch 93,45 % (piso 93 %) |
| `coverage … pulse/domain/*` | 97,86 % (piso 90 %) |
| `mutmut` + `mutation_gate.py --min 80` | 98,1 % (1 059 mortos de 1 079) |

### Corrigidos neste PR

- **Teste dependente de ordem.** `importlinter.cli.lint_imports` chama
  `dictConfig` com `disable_existing_loggers=True` e desligava todo logger já
  criado; um teste com `caplog` falhava conforme a semente aleatória (ex.
  `--randomly-seed=9575794`). A fixture `loggers_left_enabled` restaura o estado.
- **Probe ACP travava com adapter verboso.** `AcpClient` passava `stderr=PIPE`
  e nunca lia; mais de 64 KiB de log do `npx` bloqueava o adapter e o
  `pulse doctor` acusava timeout num runtime saudável. Agora `stderr=DEVNULL` e
  `cwd` explícito (§6.1). Teste: `tests/infra/test_acp_client_process.py`.
- **500 não deixava rastro (§4.4).** O handler genérico agora registra o
  traceback no log do daemon. Teste:
  `test_an_unexpected_failure_leaves_its_traceback_in_the_daemon_log`.

## 5. O que mudou neste PR, por skill

| Skill | Mudança |
|---|---|
| security-audit | `pulse/api/browser_guard.py`; guarda `Origin`/`Host` em `pulse/mcp/http_bridge.py` (e o parâmetro `host`, nunca usado, saiu); `--host` só loopback em `pulse/daemon/server.py` |
| python-quality | `stderr=DEVNULL` e `cwd` em `pulse/acp/client.py`; log do 500 em `pulse/api/app.py`; fixture contra vazamento de logging |
| software-architect | Contratos "A TUI só chega à persistência pelo daemon" e "Adapters dependem do domínio, não uns dos outros", com baseline explícito; teto por contrato em `test_import_contracts.py` (baseline só encolhe); ADR 0003 |
| tactical-ddd | `PhaseStatus` é `StepStatus` (some a tabela de tradução); `PhaseItem` com métodos de intenção; `ApprovalOutcome` (`StrEnum`); invariante de `Loop`; `parse_outcome` uma vez só em `_judge_turn` |

## 6. Follow-ups (fora do escopo desta fase)

Os itens 2–5 e 8 da lista anterior, mais "migrações sem versão" (seção D) e o
texto de tela em `domain/ui_text.py`, foram fechados na fase 10 (§7). Em ordem
de prioridade, o que segue aberto (o F1 foi fechado pelo
[ADR 0005](adr/0005-tcp-exige-token-do-daemon.md)):

1. **`ResolvedConfig`**: `Sourced(valor, fonte)` + `ConfigSource` (`StrEnum`);
   coleções imutáveis; config do agente parseada na borda do store.
2. **Vocabulários duplicados**: `HistoryStatus` × `RunStatus`; política de
   permissão em três lugares, com fallbacks `or "ask"`.
3. **`RunRecord.created_at`/`updated_at`** como `datetime`, como nos steps.

## 7. Fase 10 — dívidas apontadas por este scorecard, fechadas

Branch `refactor/close-audit-gaps`. Cada item tem o teste que o prende.

| Dívida | Antes | Depois | Prova |
|---|---|---|---|
| TUI não é cliente fino | 18 imports tolerados no contrato da TUI + 3 no do cliente; cadeias indiretas não checadas | Telas falam só com `/api/*` (`tui/engine.py`); contrato da TUI checa cadeias indiretas e proíbe também `vcs`, `mcp`, `api`; única entrada é o layout de `~/.pulse` (regra, não dívida); cliente sem entrada | `test_import_contracts.py` (tetos 0 e 1), `tests/api/test_settings_routes.py`, `tests/tui/test_engine_gateway.py`, `tests/tui/test_screens_without_daemon.py` |
| Adapters importam uns aos outros | 12 imports tolerados | 0, com cadeias indiretas; `acp/` recebe `RuntimeDialect`, `QuestionChannel` e `SessionLog` do daemon | `test_import_contracts.py`, `tests/domain/test_ports.py`, `tests/api/test_run_engine.py` |
| SIGTERM não cancela runs nem encerra ACP | Runs ficavam `running`, agentes órfãos | `GracefulServer` para as runs (caminho do cancelamento), recusa runs novas (`503`) e loga a que não parou no prazo | `tests/api/test_daemon_shutdown.py`; fumaça manual: daemon ocioso sai com 0 e limpa meta/socket |
| Observabilidade quase nula | Um `logging` no pacote | Log operacional com `run_id`: início, fim, falha, stop, fases, status de step, espera do usuário; sem prompt nem env | `tests/api/test_daemon_logs.py`, `docs/logs.md` |
| Migrações sem versão | `ALTER` idempotente a cada abertura | `PRAGMA user_version` + `MIGRATIONS` em ordem, cada uma numa transação; banco mais novo é recusado | `tests/infra/test_schema_migrations.py` |
| Texto de UI no domínio | `domain/ui_text.py` importado por todas as camadas | Texto com o dono que o compõe; modelo e turno de fase viajam como dado (`ENGINE_PROTOCOL` 7) | ADR 0004, três contratos `protected`, `test_the_domain_holds_no_screen_copy_module` |

Qualidade ao fim da fase: 8 → 11 contratos do import-linter, 0 exceções de
dívida; cobertura por branch 93,5 % (domínio 97,5 %); mutação dos parsers
97,5 %; `sast-lite` e `secret-scanner` limpos. Um bug real apareceu nos testes
novos e foi corrigido: preferência de modelo só com espaços escolhia o primeiro
modelo da lista em vez de "auto".

