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

### Em aberto

- **F1 — outro usuário do SO alcança o TCP.** O UDS é `0600`, mas
  `127.0.0.1:8787` atende qualquer processo local: dá para trocar
  `permission_policy` e iniciar uma run. Correção: token por daemon no meta
  `0600` (muda `ENGINE_PROTOCOL`), ou TCP opt-in.

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

Em ordem de prioridade:

1. **F1: autenticação no TCP** (token por daemon ou TCP opt-in). Bump de `ENGINE_PROTOCOL`.
2. **"Daemon = verdade única"**: Settings e onboarding escrevem SQLite direto
   (`tui/screens/settings.py`, `onboarding.py`). Rotas `/api/agents` e
   `/api/models`; cada import removido baixa o teto do contrato da TUI (hoje 18).
3. **Desligamento gracioso**: no SIGTERM, cancelar as runs via `RunControl` e
   encerrar os processos ACP; hoje ficam órfãos e a run fica `running`.
4. **Portas no adapter ACP**: `acp/run_events.py` e `session_runner.py` gravam
   no store direto; mover para `daemon/adapters.py` (teto de adapters, hoje 12).
5. **Ciclo `acp` ↔ `runtimes`**: parsing de model-id para dentro de `AgentRuntime`.
6. **`ResolvedConfig`**: `Sourced(valor, fonte)` + `ConfigSource` (`StrEnum`);
   coleções imutáveis; config do agente parseada na borda do store.
7. **Vocabulários duplicados**: `HistoryStatus` × `RunStatus`; política de
   permissão em três lugares, com fallbacks `or "ask"`.
8. **Observabilidade**: logger do daemon com `run_id` para início/fim/falha de run.
9. **`RunRecord.created_at`/`updated_at`** como `datetime`, como nos steps.
