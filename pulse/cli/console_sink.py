"""[pulse.domain.ports.StreamSink] for a plain terminal.

Prints from the same calls the cockpit receives over SSE, so the engine has a
single path: where it would branch on "is there a screen?", the adapter decides
what a console shows instead.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pulse.domain.ports import NullStreamSink, StepRow

Write = Callable[[str], None]


def _print(line: str) -> None:
    print(line, flush=True)


class ConsoleStreamSink(NullStreamSink):
    """Banner on `set_context`, one line per settled step, notices and errors.

    Agent text is captured (the engine reads it back) but not echoed: a console
    has no room for a live tool log, which is what the cockpit is for.
    """

    def __init__(self, title: str, *, write: Write = _print) -> None:
        super().__init__()
        self._title = title
        self._write = write
        self._reported: set[str] = set()

    def set_context(self, *, cwd: str, branch: str) -> None:
        self._write("")
        self._write(f"=== {self._title} ===")
        self._write(f"Workspace: {cwd}")
        if branch:
            self._write(f"Branch: {branch}")
        self._write("")

    def info(self, title: str) -> None:
        self._write(f"[pulse] {title}")

    def error(self, title: str, reason: str = "") -> None:
        self._write(f"[pulse] {title}: {reason}" if reason else f"[pulse] {title}")

    def apply_phase_statuses(
        self,
        *,
        steps: Sequence[StepRow] = (),
        done_ids: Sequence[str] = (),
        skipped_ids: Sequence[str] = (),
        failed_ids: Sequence[str] = (),
        blocked_ids: Sequence[str] = (),
    ) -> None:
        """Report each step once, when it first settles; the engine resends the whole list."""
        labels = {row["id"]: row["label"] for row in steps}
        for step_id in done_ids:
            self._report(step_id, f"✓ {labels.get(step_id, step_id)}")
        for step_id in skipped_ids:
            self._report(step_id, f"⏭  {labels.get(step_id, step_id)} skipped")

    def _report(self, step_id: str, line: str) -> None:
        if step_id in self._reported:
            return
        self._reported.add(step_id)
        self._write(line)
