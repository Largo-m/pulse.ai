# AGENTS.md — Pulse project rules

Rules for any AI agent (Claude Code, Cursor, Codex…) or human changing this
repository. They condense [`ARCHITECTURE.md`](ARCHITECTURE.md) and the skills in
[`.claude/skills/`](.claude/skills/) into what must hold on every change.

When a rule here conflicts with a direct instruction from the user, the user
wins — but say which rule you are breaking and why.

---

## 1. What Pulse is (and is not)

Pulse is a terminal-first **orchestrator of AI agents over ACP**. Its single
responsibility: **decide which agent runs now, and when.**

- It does **not** know what an agent does, does not read what the agent
  produced, and does not expect files with known names.
- Workflows, steps and agents are **data in SQLite** (`~/.pulse/pulse.db`),
  never code.
- The only text Pulse interprets from an agent is the three fenced blocks it
  specified itself: the approval questionnaire, `pulse:outcome`, and the fan-out
  item list.

If a change makes the engine aware of a specific workflow, phase, artifact name
or domain term, it is the wrong change.

---

## 2. Architecture rules

### 2.1 Layers and allowed dependencies

```
CLI / TUI  --HTTP/UDS-->  Engine daemon  --ACP-->  runtime (cursor | claude)
(thin client)             (composition root)
```

| Layer | Packages | May depend on | Must NOT depend on |
|---|---|---|---|
| Entry | `cli.py`, `cli_daemon.py`, `__main__.py` | `client/`, `tui/`, `config/`, `doctor/` | `orchestrator/` to execute runs |
| UI | `tui/` | `client/`, `ports.py`, `history/` (read) | `orchestrator/`, `acp/` to execute |
| Client | `client/` | HTTP contract only | domain internals |
| Composition root | `daemon/`, `api/` | everything | — |
| Domain | `orchestrator/`, `prompts/`, `ports.py`, `runcontrol.py` | `store/`, `config/`, `acp/` via ports | Textual, FastAPI, widgets |
| Infra / adapters | `acp/`, `runtimes/`, `store/`, `vcs/`, `mcp/` | stdlib, third-party libs | `tui/` |

- **The daemon is the single source of truth** for runs, effective config and
  state. Only `daemon/` wires the service graph.
- **The TUI is a thin client**: it talks to `/api/*`, never runs a workflow in
  its own process. `tui/` and `client/` never import `orchestrator/`, `acp/` or
  `daemon/`; shared constants go to a neutral module (`runcontrol.py`,
  `protocol.py`, `paths.py`). The import-linter contracts in `pyproject.toml`
  enforce this; their `ignore_imports` baseline only shrinks.
- **Ports & Adapters**: the domain depends on `StreamSink` / `PromptPort`
  ([`pulse/ports.py`](pulse/ports.py)), not on Textual or HTTP. New I/O needs a
  port first, then adapters (TUI, API, `Null*`).
- **One contract, two transports**: the same `/api/*` routes over UDS and TCP.
  Any route change updates [`contracts/openapi.yaml`](contracts/openapi.yaml)
  (enforced by `tests/architecture/test_openapi_contract.py`). Breaking changes to the
  client↔daemon protocol bump `ENGINE_PROTOCOL` in
  [`pulse/protocol.py`](pulse/protocol.py).

### 2.2 Data-driven invariants (never break)

1. **No domain content in the package outside the factory seed.** Non-Python
   files and domain vocabulary live only in `pulse/store/factory/`, and only
   `store/db.py` imports it. Check after touching the package:

   ```bash
   find pulse -type f ! -name "*.py" -not -path "*__pycache__*" -not -path "pulse/store/factory/*"
   grep -rniE "\bprd\b|techspec|new-issue|quick-fix|setup-project|analyze-codebase" \
     --include="*.py" pulse/ | grep -v "^pulse/store/factory/"
   ```

   Both must print nothing. `tests/architecture/test_factory_seed.py` enforces
   the same in `pytest` and CI.
2. **No `if workflow_id == ...`** (or step/agent id) anywhere in the engine or UI.
   Behavior comes from columns in `workflow_steps` / `agent_defs`.
3. **Unknown id does not exist.** No fallback catalogs: `get_workflow` returns
   `None` → `UnknownWorkflow` → HTTP 404.
4. **Seeding is `INSERT OR IGNORE`.** Never overwrite user edits on upgrade.
5. **Definition is mutable, state is immutable.** `run_steps` copies label and
   position at run start; editing a workflow never rewrites history.
6. **Nothing on disk except artifacts** (and per-run git worktrees under
   `~/.pulse/worktrees/`). Config and state go to SQLite; for artifacts Pulse
   stores only the path, relative to where the run worked.
7. **A missing template key is an error, not a blank** (`prompts/render.py`).
8. **One ACP session per step.** The next step receives only
   `{{previous_summary}}`, never the previous context.
9. **Policy is not a question.** Decisions resolved by `permission_policy` are
   applied in the daemon (`decide_permission`); only real questions reach a
   user, and closing a screen must never freeze a run.
10. **`workspace_root` ≠ `worktree_path`.** Config and history resolve by the
    project root; the agent's `cwd`, `{{workspace}}` and artifact paths use the
    worktree.

### 2.3 Extending Pulse

- **New runtime**: subclass `AgentRuntime` in `pulse/runtimes/` and register it
  in `RUNTIMES`. Config, doctor, onboarding and session runner must pick it up
  with no other change — if they don't, fix the abstraction, not the callers.
- **New workflow behavior**: add a column to the definition tables and read it
  generically in the engine. Never special-case a workflow.
- **New event**: add it to the event bus, document it in the SSE list of
  `ARCHITECTURE.md`, and make sure replay (`stream.replay_end`) still rebuilds
  the screen correctly.
- **Architectural decisions** that change a principle above: write an ADR
  (MADR format, see `software-architect` skill) under `docs/` and update
  `ARCHITECTURE.md` in the same PR.

Default to the simplest design: modular monolith, ports & adapters, explicit
contracts. Add distribution, threads, caches or new abstractions only with
evidence of need.

---

## 3. Design and domain modeling

Apply tactical DDD where there is real domain logic (`orchestrator/`,
`prompts/`, `runcontrol.py`, `history/`, `config/resolved.py`) — not in DTOs,
routes or adapters.

- **Behavior with data.** Prefer methods that express intent
  (`outcome.delivered`, `control.checkpoint()`) over setter chains or services
  that poke at fields.
- **Value objects first.** Immutable `@dataclass(frozen=True)` for values
  without identity; parse at the boundary into a typed object instead of
  passing raw `dict[str, Any]` deep into the domain.
- **Make invalid states unrepresentable.** Use enums / `Literal` / constants for
  statuses (`done`, `blocked`, `skipped`, `pending`, `failed`), never ad-hoc
  strings scattered in code.
- **Ubiquitous language**: use the glossary in `ARCHITECTURE.md` (workflow,
  step, run, agent, runtime, artifact, worktree). Don't invent synonyms.
- **Reference by id** across aggregates (run ↔ workflow ↔ agent), never by
  holding live objects.
- **Fail safe on ambiguity.** When the engine can't confirm delivery, treat it
  as not delivered (see `parse_outcome`): one extra question is cheaper than a
  cascade built on a delivery that never happened.

---

## 4. Clean code

### 4.1 Language and style

- **Code, identifiers, comments, docstrings, test names and log/error messages
  are in English.** User-facing docs (`README.md`, `ARCHITECTURE.md`, `docs/`)
  and factory playbooks may stay in Portuguese.
- Python ≥ 3.11, `from __future__ import annotations`, full type hints on public
  functions. Use `X | None`, `list[str]`, `Protocol` — not `Optional`, `List`,
  `ABC` when a protocol suffices.
- Match the surrounding file: naming, idiom, comment density. Reuse the
  canonical helper that already exists before writing a new one.

### 4.2 Comments

A comment explains **why** (a constraint, a trade-off, a non-obvious reason) —
never **what** the next line does. Delete on sight:

- comments restating the code, changelog/narration comments
  ("changed from X", "new function"), commented-out code;
- docstring walls on trivial private helpers;
- `TODO` without owner or issue link.

Good docstrings state the contract and the reason, like the ones in
`tests/test_outcome_block.py`.

### 4.3 Structure

- **Code judo over rearranging.** Prefer the reframing that deletes branches,
  flags or layers over one that moves complexity around.
- **File size**: no file crosses **1000 lines**. `orchestrator/engine.py`,
  `tui/state.py` and `acp/session_runner.py` are close — extract a focused
  module (as `loops.py` / `fanout.py` were) before adding to them.
  `tests/architecture/test_file_size.py` enforces it; its exception list caps
  each oversized file at its current size and only shrinks.
- **No spaghetti growth**: no one-off booleans, nullable modes or special cases
  bolted onto an unrelated flow. Introduce a policy object, dispatcher or
  state model instead.
- **Early returns** over deep nesting. Small functions with one reason to change.
- **No speculative code (YAGNI)**: no parameters, config or abstractions "for
  later", no wrapper with a single pass-through implementation.
- **Named constants** for business values; no magic numbers or strings.
- **No `sleep` as synchronization**, no retry around a deterministic bug.

### 4.4 Errors

- Catch **specific** exceptions. `except Exception` is allowed only at a real
  boundary (thread top-level, step runner) and must carry `# noqa: BLE001` plus a
  reason, and must record the failure (step `failed`, event, exit code) — never
  swallow it silently.
- Re-raise with `raise NewError(...) from error`.
- No defensive `try` on trusted internal paths; let failures propagate.
- Run exit codes are part of the contract (`RUN_STOPPED` 130, `RUN_BLOCKED`
  131). Stopped and blocked are not failures — don't report them as errors.

### 4.5 Suppressions

Every `# noqa`, `# type: ignore` or `pytest.mark.skip` needs a rule code and a
justification on the same line or the line above. A naked suppression is a
defect. Never add `--no-verify`, `|| true`, or CI-only branches to make a check
pass.

---

## 5. Testing

Tests live in `tests/`, run with `pytest`. `tests/conftest.py` isolates the
database per test (`PULSE_DB` → `tmp_path`) and offers `make_workflow(...)` to
seed workflows — tests seed their own data; don't depend on the factory seed.

### 5.1 Rules

- **Every behavior change ships with a test that fails without it.** For bugs,
  follow red → green → refactor: write the failing regression test first. Only
  claim TDD if you actually observed the red run.
- **Test behavior through public contracts** — return values, persisted rows,
  emitted events, HTTP responses, exit codes — not private methods or call
  order.
- **Real objects over mocks**, in this order: real in-memory objects / temp
  dirs / real SQLite → purpose-built fakes implementing the port (`Null*`
  sinks, fake `PromptPort`) → stubs → `unittest.mock` as a last resort. Never
  mock what you own when a fake is cheap; never mock SQLite.
- **Deterministic**: no live network, no real agent CLI, no wall-clock
  assumptions, no `sleep` for synchronization (use events/conditions or an
  injected clock), no order dependence, no leaked env/global state (use
  `monkeypatch`).
- **Strong oracles**: assert the fields the behavior is about. A sole
  `assert result` / `is not None` / "not empty" is not a test. Derive expected
  values independently of the code under test.
- **Cover error paths**, not just invalid input: inject the downstream failure
  (runtime missing, ACP error, git failure, closed stream) and assert how the
  run degrades (step status, event, exit code).
- **Concurrency** (`daemon/runs.py`, `runcontrol.py`, event bus, prompt
  correlator): drive shared state from several threads released together and
  assert the promised invariant (no lost update, at-most-once).
- **Validators/parsers/sanitizers** (`outcome`, approval, questionnaire,
  `decide_permission`, path handling): test both directions — bad input is
  rejected *and* good input is preserved. Consider property-based tests for
  parsers.
- **Test names read as specifications** in English
  (`test_text_without_the_block_is_not_a_delivery`); the docstring says why the
  behavior matters.
- **Architecture invariants are tests.** They live in `tests/architecture/`:
  factory seed, OpenAPI contract, import contracts, file size, markdown links
  and modules cited in `ARCHITECTURE.md`. Keep them, and extend them when
  adding a rule.
- No `skip`, `xfail` or weakened assertions to make CI green.

### 5.2 Before finishing

```bash
pip install -e ".[dev]" && pre-commit install   # once per clone

pytest tests/test_<area>.py  # nearest tests first while iterating
pytest --cov                 # whole suite + coverage floor, must be green
ruff check . && ruff format --check .
mypy
lint-imports                 # import contracts with the offending chains (also run by pytest)
```

CI (`.github/workflows/ci.yml`) runs the same commands on Python 3.11–3.14,
plus `sast-lite`, `secret-scanner` and `dependency-check --online` (§6.2), and
must be green to merge. Complexity (`C901`) and `vulture` run as advisory
steps: they report, never block.

- **Coverage floor** is `fail_under` in `pyproject.toml`. Each phase raises
  it; never lower it.
- **Baseline exceptions** (ruff `per-file-ignores` and mypy `overrides` marked
  *Baseline* in `pyproject.toml`) are debt that predates the gates. Never add
  to them; fix the code or add a justified `noqa` (§4.5). Remove an entry as
  soon as its file is clean.

Report: which tests changed, the commands run, the results, and remaining gaps.
Never claim tests pass without running them.

---

## 6. Security

Pulse spawns agent processes, runs git, opens a local HTTP server and persists
user prompts — treat every boundary as such.

### 6.1 Code rules

- **Subprocess**: always argument lists, never `shell=True`, never a string
  built from user/agent input. Each call carries `# noqa: S603` with the
  reason. Set `cwd` explicitly; set timeouts on calls that can hang.
- **SQL**: parameterized queries (`?`) for every value. Dynamic identifiers
  (table/column names) only from a hard-coded allowlist, with `# noqa: S608`
  explaining it — never from input.
- **Paths**: paths from agents (`locations[].path`, `rawInput`) or the API are
  untrusted. Resolve and confine them to the run's workspace/worktree before
  reading, opening or deleting. Guard against `..` and symlink escape.
- **Git destructive operations**: never `--force` on `worktree remove`; a
  worktree with uncommitted changes is kept. Never delete a branch.
- **No `eval`/`exec`, `pickle`, `yaml.load` (use `safe_load`), `tempfile.mktemp`,
  `verify=False`**, or `random` for anything security-related (`secrets`).
- **Secrets**: never hardcode keys or tokens; never log or persist
  `ANTHROPIC_API_KEY`, `CURSOR_API_KEY` or env contents in `run_events`,
  errors or SSE. Read credentials from the environment / the runtime's own login.
- **Network exposure**: the TCP listener binds to `127.0.0.1` only; the UDS
  socket lives in `~/.pulse` with user-only permissions. Don't widen either
  without an explicit design decision. No permissive CORS on the API.
- **Permissions**: changes to `permission_policy` handling must keep "deny by
  default when unsure" (`deny_writes` with an unknown kind asks; it never
  allows). Terminal/`execute` stays vetoed unless explicitly allowed.
- **Prompt injection**: agent output and file contents are untrusted input to
  Pulse. Parse only the fenced blocks Pulse defined, with strict parsers; never
  let agent text change policy, config, or which agent runs.
- **Dependencies**: add only what is necessary, with a lower bound in
  `pyproject.toml`; justify every new dependency in the PR. Pin the ACP adapter
  version (`@agentclientprotocol/claude-agent-acp@x.y.z`), never `@latest`.

### 6.2 Tools — `security-audit` skill

All scanners live in one skill,
[`.claude/skills/security-audit/`](.claude/skills/security-audit/SKILL.md)
(`T=.claude/skills/security-audit/tools`):

| When | Run |
|---|---|
| Before commit / opening the repo | `python $T/secret-scanner/engine.py .` |
| Python changes touching I/O, subprocess, SQL, parsing | `python $T/sast-lite/analyzer.py pulse/` |
| Changing `pyproject.toml` | `python $T/dependency-check/checker.py . --online` |
| Changing factory prompts / agent instructions / outcome parsing | `prompt-injection-tester` + the Pulse checklist in the skill |
| Changing API routes, headers or CORS | `http-sec-audit`, `cors-auditor` |
| Adding a Dockerfile | `dockerfile-scan` |

---

## 7. Workflow for agents

1. **Read before writing**: `ARCHITECTURE.md` section of the area, the module,
   its tests. Find the canonical helper before adding one.
2. **Smallest correct change.** Stay in scope; list follow-ups instead of
   expanding the diff.
3. **Test first** for bugs and new behavior (§5).
4. **Run** the nearest tests, then `pytest`, then the two invariant checks in
   §2.2 if you touched `pulse/`.
5. **Update docs in the same change** when behavior, routes, events, tables or
   principles change: `ARCHITECTURE.md`, `docs/*.md`, `contracts/openapi.yaml`,
   `README.md`.
6. **Report honestly**: what changed, what ran, what failed, what was skipped.

### Commits and PRs

- Conventional commits: `feat(scope): …`, `fix(scope): …`, `refactor(scope): …`,
  `chore: …`, `docs: …`, in English, imperative mood.
- One logical change per commit; never commit secrets, `.venv/`, `*.egg-info`,
  or `.pulse/` runtime data.
- PRs follow [`.github/pull_request_template.md`](.github/pull_request_template.md)
  — every claim ("fixes X", "prevents race Y") points to the test that proves it.
- Branch from `main`; don't push to `main` directly.

### Useful skills

| Need | Skill |
|---|---|
| Lint, types, tests, deps in one pass | `python-quality` |
| Writing or reviewing tests | `testing-best-practices` |
| Domain model review / anemia | `tactical-ddd` |
| Architecture review, ADRs, fitness functions | `software-architect` |
| PR review | `the-judge` |
| Security scan (SAST, secrets, deps, prompt injection, …) | `security-audit` |
