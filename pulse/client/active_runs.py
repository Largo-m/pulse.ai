"""Live daemon runs, for screens that offer to return to them.

If the daemon does not respond, there are simply no live runs; callers never break.
"""

from __future__ import annotations

from typing import Any

import httpx

from pulse.client.engine_client import SCREEN_TIMEOUT_SECONDS, EngineClient


def list_runs() -> list[dict[str, Any]]:
    """Everything the daemon holds in memory, active or recently finished."""
    client = EngineClient(timeout=SCREEN_TIMEOUT_SECONDS)
    try:
        return client.list_runs()
    except (httpx.HTTPError, ValueError):
        return []
    finally:
        client.close()


def active_runs() -> list[dict[str, Any]]:
    """Only runs still running; the list that becomes menu items."""
    return [run for run in list_runs() if run.get("active")]


def active_run_ids() -> set[str]:
    return {str(run["id"]) for run in active_runs() if run.get("id")}


def awaiting_runs() -> list[dict[str, Any]]:
    """Runs stopped waiting for the user, oldest wait first."""
    waiting = [run for run in active_runs() if run.get("awaiting_prompt")]
    waiting.sort(key=lambda run: run.get("awaiting_since") or run.get("started_at") or 0.0)
    return waiting
