"""Log da spec gravado pelo Pulse, independente do runtime.

O histórico do cockpit lia o store do Cursor. Como o mesmo workflow roda no
Claude Code (e no que vier depois), o que aparece na aba precisa vir de um
lugar que o Pulse controla — é esta tabela.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pulse.config.project_config import load_project_config
from pulse.store.db import connect, default_db_path

#: Detalhe de tool pode vir com o arquivo inteiro; o cockpit só mostra o começo.
MAX_DETAIL = 2000


def record_spec_event(
    cwd: str | Path,
    *,
    spec_dir: str,
    kind: str,
    title: str,
    detail: str = "",
    phase_id: str = "",
    task_id: str = "",
    acp_session_id: str = "",
    tool_id: str = "",
    db_path: Path | None = None,
) -> None:
    """Grava uma linha do log. Um `tool_id` repetido atualiza a linha existente."""
    if not spec_dir or not (title or detail):
        return
    project = load_project_config(Path(cwd))
    if project is None:
        return
    connection = connect(db_path or default_db_path())
    try:
        row = None
        if tool_id:
            row = connection.execute(
                """
                SELECT id FROM spec_events
                WHERE project_id = ? AND spec_dir = ? AND acp_session_id = ? AND tool_id = ?
                """,
                (project.project_id, spec_dir, acp_session_id, tool_id),
            ).fetchone()
        if row is not None:
            connection.execute(
                "UPDATE spec_events SET title = ?, detail = ? WHERE id = ?",
                (title[:300], detail[:MAX_DETAIL], int(row["id"])),
            )
        else:
            connection.execute(
                """
                INSERT INTO spec_events (
                  project_id, spec_dir, phase_id, task_id, acp_session_id,
                  kind, title, detail, tool_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.project_id,
                    spec_dir,
                    phase_id,
                    task_id,
                    acp_session_id,
                    kind,
                    title[:300],
                    detail[:MAX_DETAIL],
                    tool_id,
                    datetime.now(UTC).replace(microsecond=0).isoformat(),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def list_spec_events(
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
            SELECT phase_id, task_id, kind, title, detail, tool_id
            FROM spec_events
            WHERE project_id = ? AND spec_dir = ?
            ORDER BY id
            """,
            (project.project_id, spec_dir),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "phase_id": str(row["phase_id"] or ""),
            "task_id": str(row["task_id"] or ""),
            "kind": str(row["kind"] or ""),
            "title": str(row["title"] or ""),
            "detail": str(row["detail"] or ""),
            "tool_id": str(row["tool_id"] or ""),
        }
        for row in rows
    ]
