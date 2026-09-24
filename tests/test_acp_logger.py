from pulse.acp.logger import AcpLogger


def test_acp_logger_does_not_write_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = AcpLogger("run-1")
    logger.set_session_id("sess-1")
    logger.log_sent({"method": "session/new"})
    logger.log_received({"method": "session/update"})
    logger.log_update({"sessionUpdate": "agent_message_chunk"})
    logger.log_event("process_start")
    assert logger.path is None
    assert list(tmp_path.rglob("*.jsonl")) == []
