from __future__ import annotations

from pathlib import Path

from pulse.client.active_runs import active_runs, describe
from pulse.client.engine_client import EngineClient
from pulse.daemon.paths import read_daemon_meta
from pulse.daemon.server import is_daemon_alive, stop_daemon


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
        for run in active_runs():
            print(f"  run: {describe(run)}")
        return 0
    print("pulse-engine: stopped")
    return 1


def _warn_about_live_runs() -> None:
    running = active_runs()
    if not running:
        return
    count = len(running)
    noun = "run" if count == 1 else "runs"
    print(f"[pulse] Atenção: {count} {noun} em execução — parar o engine encerra:")
    for run in running:
        print(f"  - {describe(run)}")


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
    _warn_about_live_runs()
    if not stop_daemon():
        print("[pulse] pulse-engine não saiu depois do SIGTERM; continua rodando")
        return 1
    print("pulse-engine parado")
    return 0
