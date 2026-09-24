from __future__ import annotations

from pulse.store.db import connect, default_db_path


def load_agent_settings(project_id: str, agent_id: str, *, db_path=None) -> dict[str, str | None]:
    connection = connect(db_path or default_db_path())
    try:
        row = connection.execute(
            """
            SELECT runtime, model, permission_policy
            FROM agent_settings
            WHERE project_id = ? AND agent_id = ?
            """,
            (project_id, agent_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return {}
    return {
        "runtime": row["runtime"],
        "model": row["model"],
        "permission_policy": row["permission_policy"],
    }


def upsert_agent_settings(
    project_id: str,
    agent_id: str,
    *,
    runtime: str | None = None,
    model: str | None = None,
    permission_policy: str | None = None,
    db_path=None,
) -> None:
    current = load_agent_settings(project_id, agent_id, db_path=db_path)
    next_runtime = runtime if runtime is not None else current.get("runtime")
    next_model = model if model is not None else current.get("model")
    next_policy = (
        permission_policy if permission_policy is not None else current.get("permission_policy")
    )
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO agent_settings (project_id, agent_id, runtime, model, permission_policy)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, agent_id) DO UPDATE SET
              runtime = excluded.runtime,
              model = excluded.model,
              permission_policy = excluded.permission_policy
            """,
            (project_id, agent_id, next_runtime, next_model, next_policy),
        )
        connection.commit()
    finally:
        connection.close()
