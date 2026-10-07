"""Execution state: runs, steps, log and artifacts.

Everything the orchestrator needs to know where a run stopped lives here. Of
the files the agent writes to the workspace, Pulse only stores the path
(`run_artifacts`).

Tables are keyed by `run_id` and `workspace_root`, not `project_id`:
registering the project to satisfy an FK would mark the workspace as
initialized and skip onboarding.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pulse.domain.run import (
    SETTLED,
    InvalidTransition,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
    fan_out_child_id,
    utc_now,
)
from pulse.store.db import connect, default_db_path

__all__ = [
    "AWAITING_INPUT",
    "BLOCKED",
    "DONE",
    "FAILED",
    "PENDING",
    "RUNNING",
    "SETTLED",
    "SKIPPED",
    "InvalidTransition",
    "RunRecord",
    "RunStatus",
    "StepRecord",
    "StepStatus",
    "fan_out_child_id",
    "utc_now",
]

MAX_DETAIL = 20_000

PENDING = StepStatus.PENDING
RUNNING = StepStatus.RUNNING
DONE = StepStatus.DONE
SKIPPED = StepStatus.SKIPPED
FAILED = StepStatus.FAILED
BLOCKED = StepStatus.BLOCKED
AWAITING_INPUT = RunStatus.AWAITING_INPUT


def _root(workspace: str | Path) -> str:
    return str(Path(workspace).resolve())


def _now_text() -> str:
    return utc_now().isoformat()


def _stamp(value: Any) -> datetime | None:
    """Stamp read from storage; empty or unreadable is no stamp, naive is UTC.

    Older rows were written by hand-rolled code; a bad value must not break history.
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _stamp_text(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _step(row: Any) -> StepRecord:
    return StepRecord(
        step_id=str(row["step_id"]),
        position=int(row["position"] or 0),
        label=str(row["label"] or ""),
        agent_id=str(row["agent_id"] or ""),
        status=StepStatus.parse(str(row["status"] or "")),
        summary=str(row["summary"] or ""),
        acp_session_id=str(row["acp_session_id"] or ""),
        started_at=_stamp(row["started_at"]),
        ended_at=_stamp(row["ended_at"]),
        waiting_seconds=float(row["waiting_seconds"] or 0.0),
        rounds=int(row["rounds"] or 1),
        carried_seconds=float(row["carried_seconds"] or 0.0),
    )


def _run(row: Any, steps: list[StepRecord]) -> RunRecord:
    return RunRecord(
        id=str(row["id"]),
        workflow_id=str(row["workflow_id"]),
        workspace_root=str(row["workspace_root"]),
        user_prompt=str(row["user_prompt"] or ""),
        status=RunStatus.parse(str(row["status"] or "")),
        current_step=str(row["current_step"] or ""),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
        worktree_path=str(row["worktree_path"] or ""),
        branch=str(row["branch"] or ""),
        steps=steps,
    )


def _steps_for(connection: Any, run_id: str) -> list[StepRecord]:
    rows = connection.execute(
        "SELECT * FROM run_steps WHERE run_id = ? ORDER BY position, step_id",
        (run_id,),
    ).fetchall()
    return [_step(row) for row in rows]


def create_run(
    *,
    run_id: str,
    workflow_id: str,
    workspace: str | Path,
    user_prompt: str,
    steps: list[StepRecord],
    db_path: Path | None = None,
) -> RunRecord:
    now = _now_text()
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO runs
              (id, workflow_id, workspace_root, user_prompt, status, current_step,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                workflow_id,
                _root(workspace),
                user_prompt,
                RunStatus.RUNNING,
                steps[0].step_id if steps else "",
                now,
                now,
            ),
        )
        connection.executemany(
            """
            INSERT INTO run_steps
              (run_id, step_id, position, label, agent_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (run_id, item.step_id, item.position or index, item.label, item.agent_id, PENDING)
                for index, item in enumerate(steps, start=1)
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return RunRecord(
        id=run_id,
        workflow_id=workflow_id,
        workspace_root=_root(workspace),
        user_prompt=user_prompt,
        status=RunStatus.RUNNING,
        current_step=steps[0].step_id if steps else "",
        created_at=now,
        updated_at=now,
        steps=steps,
    )


def load_run(run_id: str, *, db_path: Path | None = None) -> RunRecord | None:
    connection = connect(db_path or default_db_path())
    try:
        row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return _run(row, _steps_for(connection, run_id))
    finally:
        connection.close()


def list_runs(
    workspace: str | Path,
    *,
    limit: int = 200,
    db_path: Path | None = None,
) -> list[RunRecord]:
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            "SELECT * FROM runs WHERE workspace_root = ? ORDER BY updated_at DESC LIMIT ?",
            (_root(workspace), limit),
        ).fetchall()
        return [_run(row, _steps_for(connection, str(row["id"]))) for row in rows]
    finally:
        connection.close()


def find_resumable(workspace: str | Path, *, db_path: Path | None = None) -> list[RunRecord]:
    """Runs that stopped midway and can resume from their pending step.

    Failed runs are included. Only `completed` runs with no pending step are
    excluded.
    """
    return [
        run
        for run in list_runs(workspace, db_path=db_path)
        if run.status != RunStatus.COMPLETED and run.is_incomplete()
    ]


def save(run: RunRecord, *, db_path: Path | None = None) -> None:
    """Persist the whole aggregate in one transaction.

    Writes the run row, deletes the steps it dropped and upserts every step, so
    a crash never leaves the run and its steps out of step with each other.
    """
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            UPDATE runs
            SET status = ?, current_step = ?, worktree_path = ?, branch = ?, updated_at = ?
            WHERE id = ?
            """,
            (run.status, run.current_step, run.worktree_path, run.branch, _now_text(), run.id),
        )
        connection.executemany(
            "DELETE FROM run_steps WHERE run_id = ? AND step_id = ?",
            [(run.id, step_id) for step_id in run.removed_step_ids()],
        )
        for step in run.steps:
            _upsert_step(connection, run.id, step)
        connection.commit()
    finally:
        connection.close()
    run.forget_removed_steps()


def _upsert_step(connection: Any, run_id: str, step: StepRecord) -> None:
    connection.execute(
        """
        INSERT INTO run_steps
          (run_id, step_id, position, label, agent_id,
           status, summary, acp_session_id, started_at, ended_at, waiting_seconds,
           rounds, carried_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, step_id) DO UPDATE SET
          status = excluded.status,
          summary = excluded.summary,
          acp_session_id = excluded.acp_session_id,
          started_at = excluded.started_at,
          ended_at = excluded.ended_at,
          waiting_seconds = excluded.waiting_seconds,
          rounds = excluded.rounds,
          carried_seconds = excluded.carried_seconds
        """,
        (
            run_id,
            step.step_id,
            step.position,
            step.label,
            step.agent_id,
            step.status,
            step.summary,
            step.acp_session_id,
            _stamp_text(step.started_at),
            _stamp_text(step.ended_at),
            step.waiting_seconds,
            step.rounds,
            step.carried_seconds,
        ),
    )


def clear_worktree(run_id: str, *, db_path: Path | None = None) -> None:
    """Forget the run's worktree directory; the branch stays, it still holds the work.

    History does not own the run aggregate, so it touches this one column instead
    of saving a snapshot over steps the daemon may have moved on since.
    """
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            "UPDATE runs SET worktree_path = '', updated_at = ? WHERE id = ?",
            (_now_text(), run_id),
        )
        connection.commit()
    finally:
        connection.close()


def delete_run(run_id: str, *, db_path: Path | None = None) -> bool:
    """Delete the run and everything attached to it. `False` = it did not exist.

    Steps, events and artifacts go via `ON DELETE CASCADE`; workspace files are
    left untouched since Pulse only stores paths.
    """
    connection = connect(db_path or default_db_path())
    try:
        cursor = connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def record_event(
    run_id: str,
    *,
    kind: str,
    title: str,
    detail: str = "",
    step_id: str = "",
    acp_session_id: str = "",
    tool_id: str = "",
    db_path: Path | None = None,
) -> None:
    """Record a log row. A repeated `tool_id` updates the existing row."""
    if not run_id or not (title or detail):
        return
    connection = connect(db_path or default_db_path())
    try:
        row = None
        if tool_id:
            row = connection.execute(
                """
                SELECT id FROM run_events
                WHERE run_id = ? AND acp_session_id = ? AND tool_id = ?
                """,
                (run_id, acp_session_id, tool_id),
            ).fetchone()
        if row is not None:
            connection.execute(
                "UPDATE run_events SET title = ?, detail = ? WHERE id = ?",
                (title[:300], detail[:MAX_DETAIL], int(row["id"])),
            )
        else:
            connection.execute(
                """
                INSERT INTO run_events
                  (run_id, step_id, acp_session_id, kind, title, detail, tool_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_id,
                    acp_session_id,
                    kind,
                    title[:300],
                    detail[:MAX_DETAIL],
                    tool_id,
                    _now_text(),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def list_events(run_id: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    if not run_id:
        return []
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            """
            SELECT step_id, kind, title, detail, tool_id, acp_session_id
            FROM run_events WHERE run_id = ? ORDER BY id
            """,
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "step_id": str(row["step_id"] or ""),
            "kind": str(row["kind"] or ""),
            "title": str(row["title"] or ""),
            "detail": str(row["detail"] or ""),
            "tool_id": str(row["tool_id"] or ""),
            "acp_session_id": str(row["acp_session_id"] or ""),
        }
        for row in rows
    ]


def record_artifact(
    run_id: str,
    path: str,
    *,
    step_id: str = "",
    db_path: Path | None = None,
) -> None:
    if not run_id or not path.strip():
        return
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO run_artifacts (run_id, path, step_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id, path) DO NOTHING
            """,
            (run_id, path.strip(), step_id, _now_text()),
        )
        connection.commit()
    finally:
        connection.close()


def list_artifacts(run_id: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    if not run_id:
        return []
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            "SELECT path, step_id FROM run_artifacts WHERE run_id = ? ORDER BY created_at, path",
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {"path": str(row["path"]), "step_id": str(row["step_id"] or "")}
        for row in rows
    ]


def list_sessions(run_id: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    """ACP sessions of each step, in the order they ran."""
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            """
            SELECT step_id, label, acp_session_id FROM run_steps
            WHERE run_id = ? AND acp_session_id != '' ORDER BY position, step_id
            """,
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "step_id": str(row["step_id"]),
            "label": str(row["label"] or row["step_id"]),
            "acp_session_id": str(row["acp_session_id"]),
        }
        for row in rows
    ]
