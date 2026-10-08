"""Live daemon runs, for screens that offer to return to them.

If the daemon does not respond, there are simply no live runs; callers never break.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from pulse.client.engine_client import EngineClient
from pulse.domain import ui_text

_TIMEOUT = 2.0


def list_runs() -> list[dict[str, Any]]:
    """Everything the daemon holds in memory, active or recently finished."""
    client = EngineClient(timeout=_TIMEOUT)
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


def waiting_for(run: dict[str, Any], *, now: float | None = None) -> str:
    """How long this run has been waiting for an answer. Empty if not waiting.

    Deliberately coarse (`3min`) rather than the sidebar's `MM:SS`.
    """
    since = run.get("awaiting_since")
    if not since:
        return ""
    elapsed = (time.time() if now is None else now) - float(since)
    if elapsed < 0:
        return ""
    if elapsed < 60:
        return f"{int(elapsed)}s"
    if elapsed < 3600:
        return f"{int(elapsed // 60)}min"
    hours, minutes = divmod(int(elapsed // 60), 60)
    return f"{hours}h{minutes:02d}"


def run_line(run: dict[str, Any], *, tail: str = "") -> str:
    """`loop · step · tail` without empty parts; the line screens use to name a live run."""
    label = str(run.get("workflow_label") or run.get("workflow_id") or "Run")
    step = str(run.get("current_step_label") or "").strip()
    return " · ".join(part for part in (label, step, tail) if part)


def held_tail(run: dict[str, Any]) -> str:
    """`há 3min` for a waiting run; empty if the wait time is unknown."""
    held = waiting_for(run)
    return ui_text.waiting_since(held) if held else ""


def describe(run: dict[str, Any]) -> str:
    """A menu line: the loop, its current step and whether it awaits someone."""
    if run.get("awaiting_prompt"):
        held = waiting_for(run)
        if held:
            return run_line(run, tail=f"{ui_text.AWAITING_YOU} {ui_text.waiting_since(held)}")
        return run_line(run, tail=ui_text.AWAITING_YOU)
    return run_line(run, tail=ui_text.RUNNING)
