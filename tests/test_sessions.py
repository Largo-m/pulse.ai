from pathlib import Path

from pulse.config.project_config import init_project_config, load_project_config
from pulse.store.db import connect, default_db_path
from pulse.store.sessions import persist_runtime_session, start_agent_session


def test_start_agent_session_inserts_row(tmp_path: Path):
    init_project_config(tmp_path)
    project = load_project_config(tmp_path)
    assert project is not None
    session_id = start_agent_session(
        project_id=project.project_id,
        agent_id="prd",
        workflow_id="new-issue",
    )
    connection = connect(default_db_path())
    row = connection.execute(
        "SELECT project_id, agent_id, acp_session_id, status FROM agent_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    connection.close()
    assert row["project_id"] == project.project_id
    assert row["agent_id"] == "prd"
    assert row["acp_session_id"] is None
    assert row["status"] == "running"


def test_persist_runtime_session_creates_and_keeps_each_session(tmp_path: Path):
    init_project_config(tmp_path)
    persist_runtime_session(
        str(tmp_path),
        pulse_session_id="pulse-sess",
        acp_session_id="acp-sess",
        agent_id="prd",
    )
    persist_runtime_session(
        str(tmp_path),
        pulse_session_id="pulse-sess",
        acp_session_id="acp-sess-2",
        agent_id=None,
    )
    connection = connect(default_db_path())
    rows = connection.execute(
        "SELECT acp_session_id, agent_id FROM agent_sessions ORDER BY rowid"
    ).fetchall()
    connection.close()
    assert [row["acp_session_id"] for row in rows] == ["acp-sess", "acp-sess-2"]
    assert rows[0]["agent_id"] == "prd"
    assert rows[1]["agent_id"] is None
