from __future__ import annotations

from textual import events
from textual.message import Message
from textual.widgets import TextArea

SUBMIT_KEY = "enter"
LINE_BREAK = "\n"
LINE_CONTINUATION = "\\"
# Shift+Enter only reaches the app on terminals with the kitty keyboard
# protocol and Alt+Enter needs Option-as-Meta on macOS; Ctrl+J and a trailing
# backslash work on every terminal, so the hint advertises those two.
LINE_BREAK_KEYS = frozenset({"shift+enter", "alt+enter", "ctrl+j"})


class TaskComposer(TextArea):
    """Multi-line task box in the style of agent CLIs: Enter sends, the rest edits.

    A task often carries a stack trace or acceptance criteria, so pasted and
    typed line breaks must survive instead of being flattened by an `Input`.
    """

    class Submitted(Message):
        def __init__(self, composer: TaskComposer, text: str) -> None:
            super().__init__()
            self.composer = composer
            self.text = text

        @property
        def control(self) -> TaskComposer:
            return self.composer

    async def _on_key(self, event: events.Key) -> None:
        if event.key in LINE_BREAK_KEYS:
            self._consume(event)
            self._break_line()
            return
        if event.key == SUBMIT_KEY:
            self._consume(event)
            if self._ends_with_continuation():
                self._break_line(replacing_continuation=True)
                return
            self.post_message(self.Submitted(self, self.text))
            return
        await super()._on_key(event)

    @staticmethod
    def _consume(event: events.Key) -> None:
        event.stop()
        event.prevent_default()

    def _ends_with_continuation(self) -> bool:
        row, column = self.cursor_location
        return self.selection.is_empty and self.document[row][:column].endswith(LINE_CONTINUATION)

    def _break_line(self, *, replacing_continuation: bool = False) -> None:
        start, end = self.selection
        if replacing_continuation:
            start = (start[0], start[1] - len(LINE_CONTINUATION))
        self.replace(LINE_BREAK, start, end, maintain_selection_offset=False)
