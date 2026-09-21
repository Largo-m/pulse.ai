from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from pulse.client.engine_client import EngineClient
from pulse.daemon.paths import clear_daemon_meta, read_daemon_meta
from pulse.daemon.server import is_daemon_alive


def run_daemon_command(action: str) -> int:
    if action == "status":
        return _status()
    if action == "start":
        return _start()
    if action == "stop":
        return _stop()
    print(f"[pulse] Ação de daemon desconhecida: {action}")
    return 2


def _status() -> int:
    meta = read_daemon_meta() or {}
    alive = is_daemon_alive()
    if alive:
        print("pulse-engine: running")
        if meta.get("pid"):
            print(f"  pid: {meta['pid']}")
        if meta.get("socket"):
            print(f"  socket: {meta['socket']}")
        print(f"  http: {meta.get('http_host', '127.0.0.1')}:{meta.get('http_port', 8787)}")
        return 0
    print("pulse-engine: stopped")
    return 1


def _start() -> int:
    if is_daemon_alive():
        print("pulse-engine já está em execução")
        return 0
    client = EngineClient()
    try:
        client.ensure_daemon()
        print("pulse-engine iniciado")
        return 0
    except Exception as error:
        print(f"[pulse] Falha ao iniciar engine: {error}")
        return 1
    finally:
        client.close()


def _stop() -> int:
    meta = read_daemon_meta() or {}
    pid = meta.get("pid")
    if isinstance(pid, int):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.1)
    clear_daemon_meta()
    print("pulse-engine parado")
    return 0
