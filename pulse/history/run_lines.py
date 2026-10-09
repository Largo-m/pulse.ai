"""How a live run is named on one line: its loop, its step, and how long it waits.

The home screen's alerts and `pulse daemon status` print the same line, so a run
reads the same in the TUI and in the terminal.
"""

from __future__ import annotations

import time
from typing import Any

from pulse.history.status_labels import AWAITING_YOU, RUNNING


def waiting_since(held: str) -> str:
    """`há 3min`: how long a run has been waiting for its user."""
    return f"há {held}"


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
    return waiting_since(held) if held else ""


def describe(run: dict[str, Any]) -> str:
    """A menu line: the loop, its current step and whether it awaits someone."""
    if run.get("awaiting_prompt"):
        held = waiting_for(run)
        if held:
            return run_line(run, tail=f"{AWAITING_YOU} {waiting_since(held)}")
        return run_line(run, tail=AWAITING_YOU)
    return run_line(run, tail=RUNNING)
