"""The prompt port as the runner hands it out: every question is a user wait.

Lives outside [pulse.acp.session_runner] because it is not ACP transport: it
decides what the permission policy already answers and times what a person must.
"""

from __future__ import annotations

from collections.abc import Callable

from pulse.replies.permission import decide_permission_call

AnswerRecorder = Callable[[str, tuple[object, ...], dict[str, object], object], None]
"""Receives each prompt-port call with its result, to record the dialog."""


class WatchedPrompts:
    """Prompt port proxy that signals when a question is on screen.

    While the user decides, the agent is silent, which the `session/prompt` idle
    clock would otherwise count as a timeout. Every question passes through here,
    so it is also where the dialog is recorded to the run log (`on_answer`).
    """

    def __init__(
        self,
        inner: object,
        *,
        on_enter: Callable[[], None],
        on_exit: Callable[[], None],
        on_answer: AnswerRecorder | None = None,
    ) -> None:
        self._inner = inner
        self._on_enter = on_enter
        self._on_exit = on_exit
        self._on_answer = on_answer

    def __getattr__(self, name: str) -> object:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def watched(*args: object, **kwargs: object) -> object:
            if name == "respond_to_permission":
                decided = decide_permission_call(args, kwargs)
                if decided is not None:
                    return decided
            self._on_enter()
            try:
                result = attr(*args, **kwargs)
                self._record(name, args, kwargs, result)
                return result
            finally:
                self._on_exit()

        return watched

    def _record(
        self, name: str, args: tuple[object, ...], kwargs: dict[str, object], result: object
    ) -> None:
        if self._on_answer is not None:
            self._on_answer(name, args, kwargs, result)
