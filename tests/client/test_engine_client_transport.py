"""The engine client's contract with the daemon: requests made, transport chosen, SSE decoded.

Routes go through `httpx.MockTransport`; transport selection is checked against
real in-process servers on 127.0.0.1 and on a Unix socket, so the request truly
travels the path the client picked.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import tempfile
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

import pulse.client.engine_client as engine_client_module
from pulse.client.engine_client import EngineClient
from pulse.client.protocol import ENGINE_PROTOCOL

Handler = Callable[[httpx.Request], httpx.Response]


class _Recorder:
    """A fake daemon: records each request and answers from a route table."""

    def __init__(self, routes: dict[tuple[str, str], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._routes = routes or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._routes.get(
            (request.method, request.url.path), httpx.Response(200, json={"ok": True})
        )

    def body(self, index: int = -1) -> Any:
        return json.loads(self.requests[index].content)


def _client(handler: Handler) -> EngineClient:
    return EngineClient(transport=httpx.MockTransport(handler))


def test_get_sends_query_params_and_returns_the_json_body():
    recorder = _Recorder({("GET", "/api/x"): httpx.Response(200, json={"value": 3})})

    assert _client(recorder).get("/api/x", params={"a": "1"}) == {"value": 3}
    assert recorder.requests[0].url.params["a"] == "1"


def test_post_without_a_body_sends_an_empty_object():
    """The daemon's routes parse a JSON body; an empty POST must still be valid JSON."""
    recorder = _Recorder()

    _client(recorder).post("/api/x")

    assert recorder.body() == {}
    assert recorder.requests[0].method == "POST"


def test_patch_sends_its_body():
    recorder = _Recorder()

    _client(recorder).patch("/api/config", {"model": "opus"})

    assert recorder.requests[0].method == "PATCH"
    assert recorder.body() == {"model": "opus"}


@pytest.mark.parametrize("method", ["get", "post", "patch"])
def test_an_error_status_raises_with_the_status_code(method: str):
    client = _client(lambda _request: httpx.Response(500, json={"detail": "boom"}))

    with pytest.raises(httpx.HTTPStatusError) as raised:
        getattr(client, method)("/api/x")

    assert raised.value.response.status_code == 500


def test_a_malformed_json_body_raises_value_error():
    """Callers treat `ValueError` as an unusable engine; it must not pass as data."""
    client = _client(lambda _request: httpx.Response(200, text="{not json"))

    with pytest.raises(ValueError, match="Expecting"):
        client.get("/api/runs")


def test_start_run_sends_prompt_workspace_and_resume_id():
    recorder = _Recorder(
        {("POST", "/api/workflows/wf/runs"): httpx.Response(200, json={"id": "r"})}
    )

    result = _client(recorder).start_run(
        "wf", prompt="do it", workspace="/repo", resume_run_id="old"
    )

    assert result == {"id": "r"}
    assert recorder.body() == {"prompt": "do it", "workspace": "/repo", "resume_run_id": "old"}


def test_start_run_omits_workspace_and_resume_when_not_given():
    """An absent workspace lets the daemon resolve it; sending null would override that."""
    recorder = _Recorder()

    _client(recorder).start_run("wf", prompt="go")

    assert recorder.body() == {"prompt": "go"}


def test_run_queries_hit_their_routes():
    recorder = _Recorder(
        {
            ("GET", "/api/runs"): httpx.Response(200, json={"runs": [{"id": "a"}]}),
            ("GET", "/api/runs/a"): httpx.Response(200, json={"id": "a", "status": "done"}),
            ("GET", "/api/workflows"): httpx.Response(200, json={"workflows": [{"id": "wf"}]}),
            ("GET", "/api/doctor"): httpx.Response(200, json={"checks": []}),
        }
    )
    client = _client(recorder)

    assert client.list_runs() == [{"id": "a"}]
    assert client.get_run("a") == {"id": "a", "status": "done"}
    assert client.workflows() == [{"id": "wf"}]
    assert client.doctor() == {"checks": []}
    assert client.cancel_run("a") == {"ok": True}
    assert recorder.requests[-1].url.path == "/api/runs/a/cancel"


def test_listings_without_their_key_are_empty():
    client = _client(lambda _request: httpx.Response(200, json={}))

    assert client.list_runs() == []
    assert client.workflows() == []


def test_acp_probe_sends_workspace_and_runtime_as_query(tmp_path: Path):
    recorder = _Recorder()

    _client(recorder).acp_probe(workspace=tmp_path, runtime="claude")

    request = recorder.requests[0]
    assert request.url.path == "/api/doctor/acp-probe"
    assert dict(request.url.params) == {"workspace": str(tmp_path), "runtime": "claude"}


def test_answer_prompt_posts_the_answer():
    recorder = _Recorder()

    assert _client(recorder).answer_prompt("p1", ["A"]) == {"ok": True}
    assert recorder.requests[0].url.path == "/api/prompts/p1/answer"
    assert recorder.body() == {"answer": ["A"]}


def test_answering_a_prompt_already_answered_elsewhere_is_stale_not_an_error():
    """Two attached windows race to answer; the loser must not crash."""
    client = _client(lambda _request: httpx.Response(404, json={"detail": "gone"}))

    assert client.answer_prompt("p1", "A") == {"ok": False, "stale": True}


def test_answering_a_prompt_with_a_server_error_raises():
    client = _client(lambda _request: httpx.Response(500, json={"detail": "boom"}))

    with pytest.raises(httpx.HTTPStatusError):
        client.answer_prompt("p1", "A")


def _sse(chunks: list[str]) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=iter(chunk.encode() for chunk in chunks))

    return handler


def test_stream_events_decodes_data_lines_across_chunk_boundaries():
    """Frames arrive split anywhere; an event is only complete at the blank line."""
    chunks = [
        'data: {"seq": 1, "ty',
        'pe": "a"}\n\n: comment\nevent: x\ndata: {"seq": 2}\n',
        '\ndata: {"seq": 3}',
    ]

    events = list(_client(_sse(chunks)).stream_events("r1"))

    assert events == [{"seq": 1, "type": "a"}, {"seq": 2}]


def test_stream_events_skips_a_malformed_data_line_and_keeps_going():
    chunks = ['data: {broken\n\ndata: {"seq": 2}\n\n']

    assert list(_client(_sse(chunks)).stream_events("r1")) == [{"seq": 2}]


def test_stream_events_resumes_after_a_sequence_number():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"")

    list(_client(handler).stream_events("r1", after=7))
    list(_client(handler).stream_events("r1"))

    assert seen[0].url.path == "/api/runs/r1/events"
    assert seen[0].url.params["after"] == "7"
    assert "after" not in seen[1].url.params


def test_stream_events_on_an_unknown_run_raises():
    client = _client(lambda _request: httpx.Response(404, json={"detail": "no run"}))

    with pytest.raises(httpx.HTTPStatusError):
        list(client.stream_events("missing"))


def test_close_is_idempotent_and_the_client_reconnects_after_it():
    recorder = _Recorder()
    client = _client(recorder)
    client.get("/api/status")

    client.close()
    client.close()

    assert client.get("/api/status") == {"ok": True}
    assert len(recorder.requests) == 2


class _FakeClock:
    """Time advances only when the client waits, so a timeout costs no real time."""

    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


class _Daemon:
    """A daemon that comes up `starts_after` status checks after being spawned."""

    def __init__(self, *, up: bool, protocol: int = ENGINE_PROTOCOL, starts_after: int = 0):
        self.up = up
        self.protocol = protocol
        self.starts_after = starts_after
        self.spawned = 0
        self._checks_since_spawn = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.spawned and not self.up:
            self._checks_since_spawn += 1
            self.up = self._checks_since_spawn > self.starts_after
        if not self.up:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json={"ok": True, "protocol": self.protocol})

    def spawn(self) -> None:
        self.spawned += 1


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    fake = _FakeClock()
    monkeypatch.setattr(engine_client_module, "time", fake)
    return fake


def _engine(daemon: _Daemon, monkeypatch: pytest.MonkeyPatch) -> EngineClient:
    client = _client(daemon.handle)
    monkeypatch.setattr(client, "_start_daemon", daemon.spawn)
    return client


def test_ensure_daemon_does_not_spawn_when_a_current_engine_answers(monkeypatch, clock):
    daemon = _Daemon(up=True)

    _engine(daemon, monkeypatch).ensure_daemon()

    assert daemon.spawned == 0


def test_ensure_daemon_spawns_and_waits_until_the_engine_answers(monkeypatch, clock):
    daemon = _Daemon(up=False, starts_after=3)

    _engine(daemon, monkeypatch).ensure_daemon(timeout=20.0)

    assert daemon.spawned == 1
    assert clock.waits == [0.25] * 3


def test_ensure_daemon_gives_up_after_the_timeout(monkeypatch, clock):
    """A daemon that never comes up must fail loudly instead of hanging the CLI."""
    daemon = _Daemon(up=False, starts_after=10_000)

    with pytest.raises(RuntimeError, match="could not connect to pulse-engine"):
        _engine(daemon, monkeypatch).ensure_daemon(timeout=1.0)

    assert daemon.spawned == 1
    assert clock.now >= 1.0


def test_ensure_daemon_replaces_an_engine_speaking_an_older_protocol(monkeypatch, clock):
    """An outdated daemon would misread the client's requests; it is stopped and respawned."""
    daemon = _Daemon(up=True, protocol=ENGINE_PROTOCOL - 1)
    stopped: list[bool] = []

    def stop() -> bool:
        stopped.append(True)
        daemon.protocol = ENGINE_PROTOCOL
        return True

    monkeypatch.setattr(engine_client_module, "stop_daemon", stop)

    _engine(daemon, monkeypatch).ensure_daemon()

    assert stopped == [True]
    assert daemon.spawned == 1


class _FakePopen:
    calls: list[dict[str, Any]] = []

    def __init__(self, cmd: list[str], **kwargs: Any) -> None:
        stderr = kwargs["stderr"]
        _FakePopen.calls.append(
            {"cmd": cmd, **kwargs, "stderr_name": getattr(stderr, "name", stderr)}
        )


@pytest.fixture
def popen(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    _FakePopen.calls = []
    monkeypatch.setattr(engine_client_module.subprocess, "Popen", _FakePopen)
    return _FakePopen.calls


def test_starting_the_daemon_spawns_a_detached_module_with_its_log(
    monkeypatch, tmp_path: Path, popen
):
    log = tmp_path / "daemon.log"
    monkeypatch.setattr(engine_client_module, "DAEMON_LOG_FILE", log)
    monkeypatch.setattr(engine_client_module, "ensure_global_dir", lambda: tmp_path)
    monkeypatch.setattr(EngineClient, "ping", lambda self: True)
    monkeypatch.setattr(EngineClient, "_protocol_ok", lambda self: len(popen) > 0)

    EngineClient().ensure_daemon()

    (call,) = popen
    assert call["cmd"][1:] == ["-m", "pulse.daemon", "serve"]
    assert call["start_new_session"] is True
    assert call["stdout"] == engine_client_module.subprocess.DEVNULL
    assert call["stderr_name"] == str(log)
    assert call["stderr"].closed
    assert log.exists()


def test_a_log_that_cannot_be_opened_sends_daemon_stderr_to_devnull(monkeypatch, popen):
    """A read-only home must not stop the engine from starting."""

    def unwritable() -> Path:
        raise PermissionError("read-only")

    monkeypatch.setattr(engine_client_module, "ensure_global_dir", unwritable)
    monkeypatch.setattr(EngineClient, "ping", lambda self: True)
    monkeypatch.setattr(EngineClient, "_protocol_ok", lambda self: len(popen) > 0)

    EngineClient().ensure_daemon()

    assert popen[0]["stderr"] == engine_client_module.subprocess.DEVNULL


def test_a_spawn_failure_propagates_and_closes_the_log(monkeypatch, tmp_path: Path):
    opened: list[Any] = []
    real_open = Path.open

    def tracking_open(self: Path, *args: Any, **kwargs: Any) -> Any:
        handle = real_open(self, *args, **kwargs)
        opened.append(handle)
        return handle

    def failing_popen(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("python missing")

    monkeypatch.setattr(engine_client_module, "DAEMON_LOG_FILE", tmp_path / "daemon.log")
    monkeypatch.setattr(engine_client_module, "ensure_global_dir", lambda: tmp_path)
    monkeypatch.setattr(Path, "open", tracking_open)
    monkeypatch.setattr(engine_client_module.subprocess, "Popen", failing_popen)
    monkeypatch.setattr(EngineClient, "ping", lambda self: False)

    with pytest.raises(FileNotFoundError, match="python missing"):
        EngineClient().ensure_daemon()

    assert [handle.closed for handle in opened] == [True]


class _StatusHandler(http.server.BaseHTTPRequestHandler):
    """Answers `/api/status` with its server's tag and the credential it received."""

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        tag = self.server.tag  # type: ignore[attr-defined]  # tag is set on the server by the fixture
        body = json.dumps({"ok": True, "via": tag, "auth": self.headers.get("Authorization")})
        body = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature fixed by the base class
        return None

    def address_string(self) -> str:
        return "uds"


class _TcpServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class _UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def _serve(server: socketserver.BaseServer, tag: str) -> Iterator[socketserver.BaseServer]:
    server.tag = tag  # type: ignore[attr-defined]  # read back by _StatusHandler
    # A short poll interval keeps `shutdown()` from waiting the default half second.
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture
def tcp_server() -> Iterator[socketserver.BaseServer]:
    yield from _serve(_TcpServer(("127.0.0.1", 0), _StatusHandler), "tcp")


@pytest.fixture
def unix_socket() -> Iterator[Path]:
    # AF_UNIX paths are capped near 104 bytes on macOS; pytest's tmp_path is too long.
    with tempfile.TemporaryDirectory(dir="/tmp") as directory:  # noqa: S108 - short path for AF_UNIX
        path = Path(directory) / "d.sock"
        for _server in _serve(_UnixServer(str(path), _StatusHandler), "uds"):
            yield path


def _port(server: socketserver.BaseServer) -> int:
    return int(server.server_address[1])  # type: ignore[index]  # TCP address is (host, port)


def test_an_existing_socket_is_preferred(unix_socket: Path, monkeypatch):
    monkeypatch.setattr(engine_client_module, "read_daemon_meta", lambda: None)
    client = EngineClient(socket_path=unix_socket)

    assert client.get("/api/status")["via"] == "uds"
    client.close()


def test_without_a_socket_the_client_dials_the_meta_host_and_port(
    tcp_server, tmp_path: Path, monkeypatch
):
    """The meta file is where the daemon says it listens; a stale default port would miss it."""
    meta = {"http_host": "127.0.0.1", "http_port": _port(tcp_server)}
    monkeypatch.setattr(engine_client_module, "read_daemon_meta", lambda: meta)
    client = EngineClient(socket_path=tmp_path / "missing.sock")

    assert client.ping() is True
    assert client.get("/api/status")["via"] == "tcp"
    client.close()


def test_tcp_presents_the_token_from_the_meta(tcp_server, tmp_path: Path, monkeypatch):
    """The TCP listener refuses anyone who cannot read the daemon's private meta."""
    meta = {"http_port": _port(tcp_server), "token": "daemon-token"}
    monkeypatch.setattr(engine_client_module, "read_daemon_meta", lambda: meta)
    client = EngineClient(socket_path=tmp_path / "missing.sock")

    assert client.get("/api/status")["auth"] == "Bearer daemon-token"
    client.close()


def test_the_socket_never_carries_the_token(unix_socket: Path, monkeypatch):
    """The socket is `0600`; sending the token there would only widen where it travels."""
    monkeypatch.setattr(engine_client_module, "read_daemon_meta", lambda: {"token": "daemon-token"})
    client = EngineClient(socket_path=unix_socket)

    assert client.get("/api/status")["auth"] is None
    client.close()


def test_a_meta_without_a_token_sends_no_credential(tcp_server, tmp_path: Path, monkeypatch):
    """A pre-token daemon ignores the header; the protocol bump makes the client replace it."""
    monkeypatch.setattr(
        engine_client_module, "read_daemon_meta", lambda: {"http_port": _port(tcp_server)}
    )
    client = EngineClient(socket_path=tmp_path / "missing.sock")

    assert client.get("/api/status")["auth"] is None
    client.close()


def test_tcp_is_used_when_the_socket_is_not_preferred(unix_socket: Path, tcp_server, monkeypatch):
    meta = {"http_port": _port(tcp_server)}
    monkeypatch.setattr(engine_client_module, "read_daemon_meta", lambda: meta)
    client = EngineClient(prefer_uds=False, socket_path=unix_socket)

    assert client.get("/api/status")["via"] == "tcp"
    client.close()
