from __future__ import annotations

from pulse.client.active_runs import active_runs
from pulse.client.daemon_process import is_daemon_alive, stop_daemon
from pulse.client.engine_client import EngineClient
from pulse.history.run_lines import describe
from pulse.store.paths import read_daemon_meta


def run_daemon_command(action: str) -> int:
    if action == "status":
        return _status()
    if action == "start":
        return _start()
    if action == "stop":
        return _stop()
    print(f"[pulse] Unknown daemon action: {action}")
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
    print(f"[pulse] Warning: {count} {noun} running — stopping the engine ends:")
    for run in running:
        print(f"  - {describe(run)}")


def _start() -> int:
    if is_daemon_alive():
        print("pulse-engine is already running")
        return 0
    client = EngineClient()
    try:
        client.ensure_daemon()
        print("pulse-engine started")
        return 0
    except (RuntimeError, OSError) as error:
        print(f"[pulse] Failed to start the engine: {error}")
        return 1
    finally:
        client.close()


def _stop() -> int:
    _warn_about_live_runs()
    if not stop_daemon():
        print("[pulse] pulse-engine did not exit after SIGTERM; it is still running")
        return 1
    print("pulse-engine stopped")
    return 0
