from __future__ import annotations

import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS machine (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  version INTEGER NOT NULL,
  agent_binary TEXT NOT NULL,
  acp_command TEXT NOT NULL,
  auth_method TEXT NOT NULL,
  workspace_dir TEXT NOT NULL,
  model TEXT NOT NULL,
  permission_policy TEXT NOT NULL,
  completed_at TEXT,
  acp_test_passed INTEGER NOT NULL DEFAULT 0,
  default_agent TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine_agents (
  name TEXT PRIMARY KEY,
  binary TEXT NOT NULL,
  acp_command TEXT NOT NULL,
  models TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machine_workflows (
  workflow_id TEXT PRIMARY KEY,
  agent TEXT,
  model TEXT
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  root_path TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_settings (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  model TEXT,
  permission_policy TEXT,
  workspace_root TEXT,
  default_agent TEXT,
  -- 1 = cada run deste projeto abre um `git worktree` próprio, em branch nova,
  -- em vez de escrever na árvore de trabalho de quem está usando o editor. Só
  -- faz sentido com o root em repositório git. Ver [pulse.vcs].
  use_worktree INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS project_agents (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  binary TEXT NOT NULL,
  acp_command TEXT NOT NULL,
  models TEXT NOT NULL,
  PRIMARY KEY (project_id, name)
);

CREATE TABLE IF NOT EXISTS project_workflows (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  workflow_id TEXT NOT NULL,
  agent TEXT,
  model TEXT,
  PRIMARY KEY (project_id, workflow_id)
);

CREATE TABLE IF NOT EXISTS agent_settings (
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL,
  runtime TEXT,
  model TEXT,
  permission_policy TEXT,
  PRIMARY KEY (project_id, agent_id)
);

CREATE TABLE IF NOT EXISTS agent_sessions (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  workflow_id TEXT,
  agent_id TEXT,
  acp_session_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT
);

-- ---------------------------------------------------------------------------
-- Definições: o que o Pulse sabe rodar.
--
-- O Pulse não conhece nenhum workflow por código. Um workflow é uma linha em
-- `workflow_defs` mais N linhas em `workflow_steps`; um agente é uma linha em
-- `agent_defs`. Trocar o pipeline é trocar dado, não versão do pacote.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_defs (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  -- Vazio significa "use o runtime/model/policy padrão da máquina". Um default
  -- gravado aqui congelaria a escolha feita no `pulse init`.
  runtime TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  permission_policy TEXT NOT NULL DEFAULT 'ask',
  instructions TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workflow_defs (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  is_default INTEGER NOT NULL DEFAULT 0,
  -- Tarefa que este loop já sabe qual é: "analisar codebase" e "setup do
  -- projeto" olham o repositório, não um pedido do usuário. Preenchido, o menu
  -- não pede texto nenhum e entra direto na run. Vazio = o usuário descreve.
  default_prompt TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workflow_steps (
  workflow_id TEXT NOT NULL REFERENCES workflow_defs(id) ON DELETE CASCADE,
  step_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  label TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  prompt_template TEXT NOT NULL DEFAULT '{{user_prompt}}',
  requires_approval INTEGER NOT NULL DEFAULT 0,
  -- 1 = o step roda uma vez por item que o step anterior enumerou, cada um em
  -- sessão isolada e com linha própria em `run_steps`. Ver
  -- [pulse.orchestrator.fanout]. O motor não sabe o que é um item.
  fan_out INTEGER NOT NULL DEFAULT 0,
  -- 1 = o step só fecha como `done` se o agente declarar o desfecho no bloco
  -- `pulse:outcome`. Ver [pulse.orchestrator.outcome]. Vale para step sem
  -- aprovação: onde há aprovação, quem atesta a entrega é a pessoa. Desligar
  -- devolve o comportamento antigo — encerrar o turno conta como concluir.
  requires_outcome INTEGER NOT NULL DEFAULT 1,
  -- Laço: preenchido com o `step_id` de um step anterior, este step pode mandar
  -- a run voltar até lá e repetir o trecho. Quem pede a volta é o agente, no
  -- campo `next` do bloco `pulse:outcome`; quem permite é esta coluna. Serve ao
  -- caso "revisa, corrige, revisa de novo até não sobrar nada".
  repeat_from TEXT NOT NULL DEFAULT '',
  -- Teto de voltas, contando a primeira. Sem teto um agente que sempre pede
  -- mais uma rodada deixa a run sem fim, e o motor não tem como julgar se a
  -- rodada seguinte vale a pena.
  repeat_max INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (workflow_id, step_id)
);

-- ---------------------------------------------------------------------------
-- Estado de execução.
--
-- Chaveado por `workspace_root` e não por `project_id`: inserir em `projects`
-- para satisfazer a FK marcaria o workspace como inicializado e faria o
-- onboarding parar de rodar. Uma run não depende de projeto registrado.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  -- A raiz do **projeto**, sempre — nunca o worktree. É por ela que o histórico
  -- acha a run (`HistoryCatalog`), então gravar aqui o diretório onde o agente
  -- trabalhou sumiria com a run da lista do projeto.
  workspace_root TEXT NOT NULL,
  user_prompt TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  current_step TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  -- Onde o agente de fato trabalhou, quando não foi na raiz: o worktree desta
  -- run. Vazio = rodou no próprio projeto.
  worktree_path TEXT NOT NULL DEFAULT '',
  -- Branch em que a run aconteceu. Preenchida mesmo sem worktree: é a branch
  -- que o projeto tinha quando a run começou.
  branch TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS runs_by_workspace
  ON runs (workspace_root, updated_at);

-- `label` e `position` são copiados da definição no início da run: editar o
-- workflow depois não pode reescrever o que já aconteceu.
CREATE TABLE IF NOT EXISTS run_steps (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  step_id TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  label TEXT NOT NULL DEFAULT '',
  agent_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  summary TEXT NOT NULL DEFAULT '',
  acp_session_id TEXT NOT NULL DEFAULT '',
  started_at TEXT NOT NULL DEFAULT '',
  ended_at TEXT NOT NULL DEFAULT '',
  -- Segundos em que o step ficou parado esperando o usuário responder algo
  -- (permissão, questionário, aprovação, menu de retry). `ended_at - started_at`
  -- é tempo de parede; a duração que interessa é essa menos isto aqui — senão
  -- uma aprovação que demorou a noite inteira vira "trabalho do agente".
  waiting_seconds REAL NOT NULL DEFAULT 0,
  -- Quantas vezes este step rodou nesta run. Passa de 1 só dentro de um laço
  -- (`workflow_steps.repeat_from`), e é o que deixa o painel mostrar uma linha
  -- só com o contador do lado em vez de uma linha por volta.
  rounds INTEGER NOT NULL DEFAULT 1,
  -- Duração líquida das voltas anteriores do laço, já sem a espera. A volta
  -- nova reabre `started_at`/`ended_at`, e sem isto o tempo do step voltava a
  -- zero a cada rodada em vez de somar.
  carried_seconds REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (run_id, step_id)
);

-- Log da run gravado pelo próprio Pulse. Ler do store do runtime não serve:
-- só o Cursor tem um, e o Pulse é agnóstico ao agente.
CREATE TABLE IF NOT EXISTS run_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  step_id TEXT NOT NULL DEFAULT '',
  acp_session_id TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  tool_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS run_events_by_run
  ON run_events (run_id, id);

-- Arquivos que o agente escreveu, descobertos pelos tool-calls do ACP. É a
-- única coisa que o Pulse sabe sobre o disco do workspace: não há convenção de
-- pasta nem de nome de artefato.
CREATE TABLE IF NOT EXISTS run_artifacts (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  step_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, path)
);
"""

#: Configuração de fábrica: ver [pulse.store.factory]. Os loops que o Pulse já
#: nasce sabendo rodar nascem como linha no banco, na primeira abertura, e daí
#: em diante o banco manda — `INSERT OR IGNORE` nunca desfaz edição de quem já
#: usava. O motor continua sem catálogo em código: ele lê as tabelas, não o
#: pacote.


def default_db_path() -> Path:
    override = os.environ.get("PULSE_DB")
    if override:
        return Path(override)
    # Import tardio: `pulse.config.paths` puxa `pulse/config/__init__.py`, que
    # importa `global_config`, que importa este módulo. No topo do arquivo o
    # ciclo fecha e quebra quem importar `pulse.store.db` antes de `pulse.config`.
    from pulse.config.paths import GLOBAL_DB_FILE

    return GLOBAL_DB_FILE


#: Coluna acrescentada depois que já havia banco na rua. `CREATE TABLE IF NOT
#: EXISTS` não altera tabela existente, então é `ALTER` explícito — e uma lista,
#: porque a próxima também vai passar por aqui.
ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("workflow_steps", "fan_out", "INTEGER NOT NULL DEFAULT 0"),
    ("workflow_defs", "default_prompt", "TEXT NOT NULL DEFAULT ''"),
    # Nasce ligada também para quem já tinha banco: o step que vinha fechando
    # como `done` por encerrar o turno é exatamente o que precisa passar a
    # declarar o desfecho.
    ("workflow_steps", "requires_outcome", "INTEGER NOT NULL DEFAULT 1"),
    # Zero para o que já existia: run antiga não tem como saber quanto do tempo
    # dela foi espera, e zero é o que ela vinha mostrando.
    ("run_steps", "waiting_seconds", "REAL NOT NULL DEFAULT 0"),
    # Desligado para quem já tinha banco: isolar a run em worktree muda onde o
    # agente escreve, e isso não pode passar a valer por conta de um upgrade.
    ("project_settings", "use_worktree", "INTEGER NOT NULL DEFAULT 0"),
    # Vazio para run antiga, que é a verdade: ela rodou na raiz do projeto, e o
    # Pulse não tinha como saber a branch.
    ("runs", "worktree_path", "TEXT NOT NULL DEFAULT ''"),
    ("runs", "branch", "TEXT NOT NULL DEFAULT ''"),
    # Vazio/zero para quem já tinha banco: nenhum step repetia antes, e um laço
    # que passasse a valer por conta de um upgrade mudaria o custo de toda run.
    ("workflow_steps", "repeat_from", "TEXT NOT NULL DEFAULT ''"),
    ("workflow_steps", "repeat_max", "INTEGER NOT NULL DEFAULT 0"),
    # 1 para o que já existia, que é a verdade: nenhum step repetia antes.
    ("run_steps", "rounds", "INTEGER NOT NULL DEFAULT 1"),
    # Zero para o que já existia: run antiga não guardou o tempo das voltas
    # anteriores, e zero é o que ela vinha mostrando.
    ("run_steps", "carried_seconds", "REAL NOT NULL DEFAULT 0"),
)


def _apply_added_columns(connection: sqlite3.Connection) -> set[tuple[str, str]]:
    """Aplica os `ALTER` que faltam e devolve o que foi acrescentado agora.

    Quem chama precisa saber: uma coluna nova nasce com o default do `ALTER` nas
    linhas que já existiam, e a semeadura de fábrica não roda de novo num banco
    já semeado — então o valor de fábrica dela tem de ser preenchido aqui.
    """
    added: set[tuple[str, str]] = set()
    for table, column, declaration in ADDED_COLUMNS:
        existing = {
            str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
            added.add((table, column))
    return added


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    added = _apply_added_columns(connection)
    # Import tardio: `factory` lê os `.md` de fábrica e não precisa existir para
    # quem só abre o banco para ler uma run.
    from pulse.store import factory

    if not factory.is_seeded(connection):
        factory.seed(connection)
    else:
        # Banco já semeado não recebe `seed` de novo: mudança em linha que já
        # existe chega por estes, cada um com o seu próprio guarda.
        if ("workflow_defs", "default_prompt") in added:
            factory.backfill_default_prompts(connection)
        factory.drop_approval_from_unattended_steps(connection)
        factory.teach_review_to_close_the_loop(connection)
    connection.commit()
    return connection


def reset_default_path_cache() -> None:
    return None
