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


GLOBAL_FIELDS = ("runtime", "model", "permission_policy")


def apply_setting_to_all_agents(
    project_id: str,
    *,
    field: str,
    value: str,
    agent_ids: list[str] | tuple[str, ...] = (),
    db_path=None,
) -> None:
    """Write a global value into every agent of the project.

    Overwrites existing per-agent values. It is a point-in-time write, not a
    layer on top, so a later per-agent change applies only to that agent.
    """
    if field not in GLOBAL_FIELDS or not value:
        return
    connection = connect(db_path or default_db_path())
    try:
        existing = [
            str(row["agent_id"])
            for row in connection.execute(
                "SELECT agent_id FROM agent_settings WHERE project_id = ?", (project_id,)
            )
        ]
        # `field` passed the GLOBAL_FIELDS allowlist above; values stay bound as `?`.
        if existing:
            connection.execute(
                f"UPDATE agent_settings SET {field} = ? WHERE project_id = ?",  # noqa: S608
                (value, project_id),
            )
        missing = [agent_id for agent_id in agent_ids if agent_id not in existing]
        for agent_id in missing:
            connection.execute(
                "INSERT INTO agent_settings (project_id, agent_id) VALUES (?, ?)",
                (project_id, agent_id),
            )
            connection.execute(
                f"UPDATE agent_settings SET {field} = ? WHERE project_id = ? AND agent_id = ?",  # noqa: S608
                (value, project_id, agent_id),
            )
        connection.commit()
    finally:
        connection.close()


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
