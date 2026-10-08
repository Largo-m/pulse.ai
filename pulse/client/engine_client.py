from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from pulse.client.daemon_process import stop_daemon
from pulse.client.protocol import ENGINE_PROTOCOL
from pulse.store.paths import (
    DAEMON_LOG_FILE,
    DAEMON_SOCKET,
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    ensure_global_dir,
    read_daemon_meta,
)


class EngineClient:
    def __init__(
        self,
        *,
        prefer_uds: bool = True,
        http_base: str | None = None,
        socket_path: Path | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._prefer_uds = prefer_uds
        self._socket_path = Path(socket_path or DAEMON_SOCKET)
        self._http_base = http_base
        self._timeout = timeout
        self._transport = transport
        self._client: httpx.Client | None = None

    def ensure_daemon(self, *, timeout: float = 20.0) -> None:
        if self.ping() and self._protocol_ok():
            return
        if self.ping():
            self._stop_daemon()
        self._start_daemon()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ping() and self._protocol_ok():
                return
            time.sleep(0.25)
        raise RuntimeError("Não foi possível conectar ao pulse-engine")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def ping(self) -> bool:
        try:
            data = self.get("/api/status")
            return bool(data.get("ok"))
        except (httpx.HTTPError, ValueError):
            # A refused socket, an error status or a non-JSON body all mean no usable engine.
            self.close()
            return False

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._http().get(path, params=params)
        response.raise_for_status()
        return response.json()

    def post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._http().post(path, json=body or {}, params=params)
        response.raise_for_status()
        return response.json()

    def patch(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self._http().patch(path, json=body or {})
        response.raise_for_status()
        return response.json()

    def stream_events(self, run_id: str, *, after: int = 0) -> Iterator[dict[str, Any]]:
        path = f"/api/runs/{run_id}/events"
        if after:
            path = f"{path}?after={int(after)}"
        with self._http().stream("GET", path, timeout=None) as response:
            response.raise_for_status()
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    for line in block.splitlines():
                        if line.startswith("data: "):
                            try:
                                yield json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

    def answer_prompt(self, prompt_id: str, answer: Any) -> dict[str, Any]:
        """Answer a prompt. A 404 is not an error: another attached window answered first."""
        try:
            return self.post(f"/api/prompts/{prompt_id}/answer", {"answer": answer})
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return {"ok": False, "stale": True}
            raise

    def cancel_run(self, run_id: str) -> dict[str, Any]:
        return self.post(f"/api/runs/{run_id}/cancel")

    def list_runs(self) -> list[dict[str, Any]]:
        return list(self.get("/api/runs").get("runs", []))

    def get_run(self, run_id: str) -> dict[str, Any]:
        return self.get(f"/api/runs/{run_id}")

    def start_run(
        self,
        workflow_id: str,
        *,
        prompt: str,
        workspace: str | None = None,
        resume_run_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"prompt": prompt}
        if workspace is not None:
            body["workspace"] = workspace
        if resume_run_id:
            body["resume_run_id"] = resume_run_id
        return self.post(f"/api/workflows/{workflow_id}/runs", body)

    def doctor(self) -> dict[str, Any]:
        return self.get("/api/doctor")

    def acp_probe(self, *, workspace: Path, runtime: str) -> dict[str, Any]:
        return self.post(
            "/api/doctor/acp-probe", params={"workspace": str(workspace), "runtime": runtime}
        )

    def workflows(self) -> list[dict[str, str]]:
        return list(self.get("/api/workflows").get("workflows", []))

    def _protocol_ok(self) -> bool:
        try:
            data = self.get("/api/status")
            return int(data.get("protocol") or 0) >= ENGINE_PROTOCOL
        except (httpx.HTTPError, ValueError):
            return False

    def _stop_daemon(self) -> None:
        self.close()
        stop_daemon()

    def _start_daemon(self) -> None:
        cmd = [sys.executable, "-m", "pulse.daemon", "serve"]
        try:
            ensure_global_dir()
            stderr: Any = DAEMON_LOG_FILE.open("a", encoding="utf-8")
        except OSError:
            stderr = subprocess.DEVNULL
        try:
            # argv is this interpreter plus a fixed module path; no user input.
            subprocess.Popen(  # noqa: S603
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                start_new_session=True,
                env=os.environ.copy(),
            )
        finally:
            if stderr is not subprocess.DEVNULL:
                stderr.close()

    def _http(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        if self._transport is not None:
            self._client = httpx.Client(
                transport=self._transport, base_url="http://pulse", timeout=self._timeout
            )
            return self._client
        if self._http_base:
            self._client = httpx.Client(base_url=self._http_base.rstrip("/"), timeout=self._timeout)
            return self._client
        if self._prefer_uds and self._socket_path.exists():
            transport = httpx.HTTPTransport(uds=str(self._socket_path))
            self._client = httpx.Client(
                transport=transport,
                base_url="http://pulse",
                timeout=self._timeout,
            )
            return self._client
        meta = read_daemon_meta() or {}
        host = str(meta.get("http_host") or DEFAULT_HTTP_HOST)
        port = int(meta.get("http_port") or DEFAULT_HTTP_PORT)
        self._client = httpx.Client(base_url=f"http://{host}:{port}", timeout=self._timeout)
        return self._client
