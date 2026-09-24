from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pulse.config.paths import GLOBAL_DB_FILE

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

CREATE TABLE IF NOT EXISTS workflows (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  prompt TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS spec_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  spec_dir TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  acp_session_id TEXT NOT NULL UNIQUE,
  task_id TEXT NOT NULL DEFAULT '',
  started_at TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    override = os.environ.get("PULSE_DB")
    if override:
        return Path(override)
    return GLOBAL_DB_FILE


def connect(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    _ensure_spec_session_task_id(connection)
    return connection


def _ensure_spec_session_task_id(connection: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(spec_sessions)")}
    if columns and "task_id" not in columns:
        connection.execute("ALTER TABLE spec_sessions ADD COLUMN task_id TEXT NOT NULL DEFAULT ''")


def reset_default_path_cache() -> None:
    return None
