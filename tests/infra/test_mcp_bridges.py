"""The two transports that carry `AskQuestion` from the agent to Pulse.

`AskQuestionHttpServer` speaks MCP over HTTP on 127.0.0.1; `AskQuestionBridgeServer`
relays raw JSON over a Unix socket. Both are driven with real sockets.
"""

from __future__ import annotations

import http.client
import json
import socket
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

from pulse.domain.ports import JsonObject, NullPromptPort
from pulse.mcp.ask_bridge import AskQuestionBridgeServer, request_ask_question_via_socket
from pulse.mcp.ask_protocol import DEFAULT_PROTOCOL_VERSION, TOOL_NAME
from pulse.mcp.config import pulse_ask_mcp_server
from pulse.mcp.http_bridge import ENDPOINT_PATH, AskQuestionHttpServer

ANSWERED: JsonObject = {
    "outcome": {
        "outcome": "answered",
        "answers": [{"questionId": "q1", "selectedOptionIds": ["py"]}],
    }
}
CANCELLED: JsonObject = {"outcome": {"outcome": "cancelled"}}


class _RecordingPrompts(NullPromptPort):
    def __init__(self, reply: JsonObject = ANSWERED) -> None:
        self.reply = reply
        self.calls: list[JsonObject] = []

    def respond_to_ask_question(self, params: JsonObject) -> JsonObject:
        self.calls.append(params)
        return self.reply


# --- HTTP ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def http_server() -> Iterator[tuple[AskQuestionHttpServer, _RecordingPrompts]]:
    """One server for the module: each shutdown waits out `serve_forever`'s poll interval."""
    prompts = _RecordingPrompts()
    server = AskQuestionHttpServer(prompt_handler=prompts)
    server.start()
    try:
        yield server, prompts
    finally:
        server.close()


def _send(
    server: AskQuestionHttpServer, method: str, body: bytes | None = None
) -> tuple[int, dict[str, str], bytes]:
    parts = urlsplit(server.url)
    assert parts.hostname is not None
    connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=5)
    try:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, parts.path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def _post(server: AskQuestionHttpServer, payload: object) -> tuple[int, dict[str, str], Any]:
    status, headers, body = _send(server, "POST", json.dumps(payload).encode("utf-8"))
    return status, headers, json.loads(body) if body else None


def test_the_url_is_unavailable_before_start_and_points_to_the_endpoint_after():
    server = AskQuestionHttpServer()
    with pytest.raises(RuntimeError):
        _ = server.url
    server.start()
    try:
        parts = urlsplit(server.url)
        assert (parts.scheme, parts.hostname, parts.path) == ("http", "127.0.0.1", ENDPOINT_PATH)
        assert parts.port
    finally:
        server.close()


def test_closing_twice_or_before_start_is_harmless():
    never_started = AskQuestionHttpServer()
    never_started.close()

    server = AskQuestionHttpServer()
    server.start()
    server.close()
    server.close()
    with pytest.raises(RuntimeError):
        _ = server.url


def test_get_is_refused_with_the_allowed_methods(http_server):
    server, _ = http_server
    status, headers, body = _send(server, "GET")
    assert (status, headers.get("Allow"), body) == (405, "POST, DELETE", b"")


def test_delete_ends_the_session_with_an_empty_ok(http_server):
    server, _ = http_server
    status, _, body = _send(server, "DELETE")
    assert (status, body) == (200, b"")


def test_initialize_echoes_the_client_version_and_opens_a_session(http_server):
    server, _ = http_server
    status, headers, reply = _post(
        server,
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "x-1"}},
    )

    assert status == 200
    assert reply["result"]["protocolVersion"] == "x-1"
    session = headers.get("Mcp-Session-Id")
    assert session is not None
    assert len(session) == 32

    _, ping_headers, ping = _post(server, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert ping == {"jsonrpc": "2.0", "id": 2, "result": {}}
    assert "Mcp-Session-Id" not in ping_headers


def test_initialize_without_a_version_uses_the_default(http_server):
    server, _ = http_server
    _, _, reply = _post(server, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": []})
    assert reply["result"]["protocolVersion"] == DEFAULT_PROTOCOL_VERSION


def test_a_body_that_is_not_json_is_a_parse_error(http_server):
    server, prompts = http_server
    calls_before = len(prompts.calls)
    status, _, body = _send(server, "POST", b"\xff{not json")

    assert status == 400
    assert json.loads(body) == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32700, "message": "Parse error"},
    }
    assert len(prompts.calls) == calls_before


@pytest.mark.parametrize(
    "payload", [42, "text", {"jsonrpc": "2.0", "method": "notifications/cancelled"}]
)
def test_messages_that_need_no_reply_are_accepted_empty(http_server, payload: object):
    server, _ = http_server
    status, _, body = _send(server, "POST", json.dumps(payload).encode("utf-8"))
    assert (status, body) == (202, b"")


def test_an_empty_body_is_accepted_without_a_reply(http_server):
    server, _ = http_server
    status, _, body = _send(server, "POST", b"")
    assert (status, body) == (202, b"")


def test_a_batch_answers_each_request_and_drops_notifications(http_server):
    server, _ = http_server
    status, _, replies = _post(
        server,
        [
            {"jsonrpc": "2.0", "id": 1, "method": "ping"},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            "not a message",
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ],
    )

    assert status == 200
    assert [reply["id"] for reply in replies] == [1, 2]
    assert [tool["name"] for tool in replies[1]["result"]["tools"]] == [TOOL_NAME]


def test_a_batch_of_only_notifications_is_accepted_empty(http_server):
    server, _ = http_server
    status, _, body = _send(
        server,
        "POST",
        json.dumps([{"jsonrpc": "2.0", "method": "notifications/initialized"}]).encode(),
    )
    assert (status, body) == (202, b"")


def test_an_unknown_method_with_an_id_is_method_not_found(http_server):
    server, _ = http_server
    status, _, reply = _post(server, {"jsonrpc": "2.0", "id": 9, "method": "prompts/list"})
    assert status == 200
    assert reply["error"] == {"code": -32601, "message": "Method not supported: prompts/list"}


def test_a_cancelled_answer_is_a_tool_error_and_bad_arguments_become_empty():
    prompts = _RecordingPrompts(CANCELLED)
    server = AskQuestionHttpServer(prompt_handler=prompts)
    server.start()
    try:
        _, _, reply = _post(
            server,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": TOOL_NAME, "arguments": ["not", "an", "object"]},
            },
        )
    finally:
        server.close()

    assert prompts.calls == [{}]
    assert reply["result"]["isError"] is True
    assert json.loads(reply["result"]["content"][0]["text"]) == CANCELLED


def test_a_server_without_a_prompt_handler_cancels_every_question():
    """No screen attached must never read as an answer."""
    server = AskQuestionHttpServer()
    server.start()
    try:
        _, _, reply = _post(
            server,
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"arguments": {}}},
        )
    finally:
        server.close()
    assert reply["result"]["isError"] is True


def test_the_mcp_config_points_the_agent_at_the_http_bridge():
    assert pulse_ask_mcp_server(url="http://127.0.0.1:1/mcp") == {
        "type": "http",
        "name": "pulse-ask",
        "url": "http://127.0.0.1:1/mcp",
        "headers": [],
    }


# --- Unix socket --------------------------------------------------------------


@pytest.fixture
def socket_path() -> Iterator[Path]:
    """A short private directory: `tmp_path` can exceed the AF_UNIX path limit on macOS."""
    with tempfile.TemporaryDirectory(prefix="pulse-") as directory:
        yield Path(directory) / "ask.sock"


def _raw_exchange(path: Path, payload: bytes) -> bytes:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(path))
        if payload:
            client.sendall(payload)
        client.shutdown(socket.SHUT_WR)
        chunks = []
        while data := client.recv(4096):
            chunks.append(data)
    return b"".join(chunks)


def test_start_replaces_a_stale_socket_file_and_close_removes_it(socket_path: Path):
    """A crashed run leaves its socket behind; the next one must still bind."""
    socket_path.write_text("stale")
    prompts = _RecordingPrompts()
    server = AskQuestionBridgeServer(socket_path=socket_path, prompt_handler=prompts)
    assert server.socket_path == socket_path
    server.start()
    try:
        result = request_ask_question_via_socket({"questions": []}, socket_path=str(socket_path))
    finally:
        server.close()

    assert result == ANSWERED
    assert prompts.calls == [{"questions": []}]
    assert not socket_path.exists()
    server.close()


def test_each_question_notifies_before_the_handler_answers(socket_path: Path):
    notified = threading.Event()
    seen_notified: list[bool] = []

    class _Checking(_RecordingPrompts):
        def respond_to_ask_question(self, params: JsonObject) -> JsonObject:
            seen_notified.append(notified.is_set())
            return super().respond_to_ask_question(params)

    server = AskQuestionBridgeServer(
        socket_path=socket_path, prompt_handler=_Checking(), on_question=notified.set
    )
    server.start()
    try:
        request_ask_question_via_socket({"questions": []}, socket_path=str(socket_path))
    finally:
        server.close()
    assert seen_notified == [True]


def test_garbage_and_empty_connections_get_no_reply_and_do_not_stop_the_server(
    socket_path: Path,
):
    prompts = _RecordingPrompts()
    server = AskQuestionBridgeServer(socket_path=socket_path, prompt_handler=prompts)
    server.start()
    try:
        assert _raw_exchange(socket_path, b"") == b""
        assert _raw_exchange(socket_path, b"{not json") == b""
        assert _raw_exchange(socket_path, b"\xff\xfe") == b""
        follow_up = request_ask_question_via_socket({"x": 1}, socket_path=str(socket_path))
    finally:
        server.close()

    assert prompts.calls == [{"x": 1}]
    assert follow_up == ANSWERED


def test_a_server_without_a_prompt_handler_answers_cancelled(socket_path: Path):
    server = AskQuestionBridgeServer(socket_path=socket_path)
    server.start()
    try:
        result = request_ask_question_via_socket({}, socket_path=str(socket_path))
    finally:
        server.close()
    assert result == CANCELLED


def test_closing_a_server_that_never_started_is_harmless(socket_path: Path):
    server = AskQuestionBridgeServer(socket_path=socket_path)
    server.close()
    assert not socket_path.exists()


def test_a_closed_server_refuses_new_questions(socket_path: Path):
    server = AskQuestionBridgeServer(socket_path=socket_path, prompt_handler=_RecordingPrompts())
    server.start()
    server.close()
    with pytest.raises(FileNotFoundError):
        request_ask_question_via_socket({}, socket_path=str(socket_path))
