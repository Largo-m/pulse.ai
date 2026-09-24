from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pulse.config.project_config import load_project_config
from pulse.store.db import connect, default_db_path


def record_spec_session(
    cwd: str | Path,
    *,
    spec_dir: str,
    phase_id: str,
    acp_session_id: str,
    task_id: str = "",
    db_path: Path | None = None,
) -> None:
    if not spec_dir or not phase_id or not acp_session_id:
        return
    project = load_project_config(Path(cwd))
    if project is None:
        return
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO spec_sessions (
              project_id, spec_dir, phase_id, acp_session_id, task_id, started_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(acp_session_id) DO UPDATE SET
              spec_dir = excluded.spec_dir,
              phase_id = excluded.phase_id,
              task_id = CASE
                WHEN excluded.task_id != '' THEN excluded.task_id
                ELSE spec_sessions.task_id
              END
            """,
            (
                project.project_id,
                spec_dir,
                phase_id,
                acp_session_id,
                task_id,
                datetime.now(UTC).replace(microsecond=0).isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def list_spec_sessions(
    cwd: str | Path,
    spec_dir: str,
    *,
    db_path: Path | None = None,
) -> list[dict[str, str]]:
    project = load_project_config(Path(cwd))
    if project is None or not spec_dir:
        return []
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            """
            SELECT phase_id, acp_session_id, task_id, started_at
            FROM spec_sessions
            WHERE project_id = ? AND spec_dir = ?
            ORDER BY id
            """,
            (project.project_id, spec_dir),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "phase_id": str(row["phase_id"]),
            "acp_session_id": str(row["acp_session_id"]),
            "task_id": str(row["task_id"] or ""),
            "agent_id": "",
            "started_at": str(row["started_at"]),
        }
        for row in rows
    ]


def list_project_sessions(
    cwd: str | Path,
    *,
    db_path: Path | None = None,
) -> list[dict[str, str]]:
    project = load_project_config(Path(cwd))
    if project is None:
        return []
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            """
            SELECT agent_id, acp_session_id, started_at
            FROM agent_sessions
            WHERE project_id = ? AND acp_session_id IS NOT NULL AND acp_session_id != ''
            ORDER BY started_at
            """,
            (project.project_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "phase_id": "",
            "task_id": "",
            "acp_session_id": str(row["acp_session_id"]),
            "agent_id": str(row["agent_id"] or ""),
            "started_at": str(row["started_at"]),
        }
        for row in rows
    ]
