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
  default_agent TEXT
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
  is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS workflow_steps (
  workflow_id TEXT NOT NULL REFERENCES workflow_defs(id) ON DELETE CASCADE,
  step_id TEXT NOT NULL,
  position INTEGER NOT NULL,
  label TEXT NOT NULL,
  agent_id TEXT NOT NULL,
  prompt_template TEXT NOT NULL DEFAULT '{{user_prompt}}',
  requires_approval INTEGER NOT NULL DEFAULT 0,
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
  workspace_root TEXT NOT NULL,
  user_prompt TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  current_step TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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

#: Configuração de fábrica. Não é arquivo do pacote de propósito: o Pulse não
#: carrega nenhum `.md`/`.yaml` de domínio. O que ele sabe rodar nasce como
#: linha no banco, na primeira abertura, e daí em diante o banco manda —
#: `INSERT OR IGNORE` nunca desfaz edição de quem já usava.
SEED = """
INSERT OR IGNORE INTO agent_defs (id, label, instructions)
  VALUES ('default', 'Agente', '');

INSERT OR IGNORE INTO workflow_defs (id, label, description, is_default)
  VALUES ('default', 'Executar', 'Envia a tarefa ao agente configurado', 1);

INSERT OR IGNORE INTO workflow_steps
  (workflow_id, step_id, position, label, agent_id, prompt_template, requires_approval)
  VALUES ('default', 'run', 1, 'Executar', 'default', '{{user_prompt}}', 1);
"""


def default_db_path() -> Path:
    override = os.environ.get("PULSE_DB")
    if override:
        return Path(override)
    # Import tardio: `pulse.config.paths` puxa `pulse/config/__init__.py`, que
    # importa `global_config`, que importa este módulo. No topo do arquivo o
    # ciclo fecha e quebra quem importar `pulse.store.db` antes de `pulse.config`.
    from pulse.config.paths import GLOBAL_DB_FILE

    return GLOBAL_DB_FILE


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    connection.executescript(SEED)
    connection.commit()
    return connection


def reset_default_path_cache() -> None:
    return None
