from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pulse.config.project_config import load_project_config
from pulse.store.db import connect, default_db_path


def start_agent_session(
    *,
    project_id: str,
    agent_id: str | None,
    workflow_id: str | None = None,
    pulse_session_id: str | None = None,
    db_path: Path | None = None,
) -> str:
    session_id = pulse_session_id or str(uuid.uuid4())
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO agent_sessions (
              id, project_id, workflow_id, agent_id, acp_session_id, status, started_at
            ) VALUES (?, ?, ?, ?, NULL, 'running', ?)
            """,
            (
                session_id,
                project_id,
                workflow_id,
                agent_id,
                datetime.now(UTC).replace(microsecond=0).isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return session_id


def set_acp_session_id(pulse_session_id: str, acp_session_id: str, *, db_path: Path | None = None) -> None:
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            "UPDATE agent_sessions SET acp_session_id = ? WHERE id = ?",
            (acp_session_id, pulse_session_id),
        )
        connection.commit()
    finally:
        connection.close()


def persist_runtime_session(cwd: str, *, pulse_session_id: str, acp_session_id: str, agent_id: str | None) -> None:
    project = load_project_config(Path(cwd))
    if project is None:
        return
    connection = connect(default_db_path())
    try:
        row = connection.execute(
            "SELECT id FROM agent_sessions WHERE id = ?",
            (pulse_session_id,),
        ).fetchone()
        now = datetime.now(UTC).replace(microsecond=0).isoformat()
        if row is None:
            connection.execute(
                """
                INSERT INTO agent_sessions (
                  id, project_id, workflow_id, agent_id, acp_session_id, status, started_at
                ) VALUES (?, ?, NULL, ?, ?, 'running', ?)
                """,
                (pulse_session_id, project.project_id, agent_id, acp_session_id, now),
            )
        else:
            connection.execute(
                "UPDATE agent_sessions SET acp_session_id = ?, agent_id = COALESCE(?, agent_id) WHERE id = ?",
                (acp_session_id, agent_id, pulse_session_id),
            )
        connection.commit()
    finally:
        connection.close()
