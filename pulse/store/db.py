from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pulse.paths import GLOBAL_DB_FILE

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

CREATE TABLE IF NOT EXISTS agent_defs (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  runtime TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  permission_policy TEXT NOT NULL DEFAULT '',
  instructions TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS workflow_defs (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  is_default INTEGER NOT NULL DEFAULT 0,
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
  fan_out INTEGER NOT NULL DEFAULT 0,
  requires_outcome INTEGER NOT NULL DEFAULT 1,
  repeat_from TEXT NOT NULL DEFAULT '',
  repeat_max INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (workflow_id, step_id)
);

CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  workspace_root TEXT NOT NULL,
  user_prompt TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pending',
  current_step TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  worktree_path TEXT NOT NULL DEFAULT '',
  branch TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS runs_by_workspace
  ON runs (workspace_root, updated_at);

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
  waiting_seconds REAL NOT NULL DEFAULT 0,
  rounds INTEGER NOT NULL DEFAULT 1,
  carried_seconds REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (run_id, step_id)
);

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

CREATE TABLE IF NOT EXISTS run_artifacts (
  run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  path TEXT NOT NULL,
  step_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, path)
);
"""


def default_db_path() -> Path:
    override = os.environ.get("PULSE_DB")
    if override:
        return Path(override)
    return GLOBAL_DB_FILE


ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("workflow_steps", "fan_out", "INTEGER NOT NULL DEFAULT 0"),
    ("workflow_defs", "default_prompt", "TEXT NOT NULL DEFAULT ''"),
    # On for existing databases too: steps that settled as `done` just by ending
    # the turn are exactly the ones that must now declare their outcome.
    ("workflow_steps", "requires_outcome", "INTEGER NOT NULL DEFAULT 1"),
    # An old run cannot tell how much of its time was waiting; zero is what it showed.
    ("run_steps", "waiting_seconds", "REAL NOT NULL DEFAULT 0"),
    # Off for existing databases: a worktree changes where the agent writes, and
    # that must never start happening because of an upgrade.
    ("project_settings", "use_worktree", "INTEGER NOT NULL DEFAULT 0"),
    # Empty is the truth for an old run: it ran in the project root, branch unknown.
    ("runs", "worktree_path", "TEXT NOT NULL DEFAULT ''"),
    ("runs", "branch", "TEXT NOT NULL DEFAULT ''"),
    # No step repeated before; a loop switched on by an upgrade would change the
    # cost of every run.
    ("workflow_steps", "repeat_from", "TEXT NOT NULL DEFAULT ''"),
    ("workflow_steps", "repeat_max", "INTEGER NOT NULL DEFAULT 0"),
    ("run_steps", "rounds", "INTEGER NOT NULL DEFAULT 1"),
    ("run_steps", "carried_seconds", "REAL NOT NULL DEFAULT 0"),
)


def _apply_added_columns(connection: sqlite3.Connection) -> set[tuple[str, str]]:
    """Apply missing `ALTER`s and return the columns added now.

    A new column gets the `ALTER` default on existing rows and factory seeding
    does not rerun on a seeded DB, so callers must backfill factory values.
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
    from pulse.store import factory

    if not factory.is_seeded(connection):
        factory.seed(connection)
    else:
        if ("workflow_defs", "default_prompt") in added:
            factory.backfill_default_prompts(connection)
        factory.drop_approval_from_unattended_steps(connection)
        factory.inherit_policy_on_default_agent(connection)
    connection.commit()
    return connection


def reset_default_path_cache() -> None:
    return None
