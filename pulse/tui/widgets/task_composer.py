from __future__ import annotations

from textual import events, on
from textual.message import Message
from textual.widgets import TextArea

from pulse.tui.widgets.file_mention import MENTION_SIGN, FileMentionList, mention_at

SUBMIT_KEY = "enter"
LINE_BREAK = "\n"
LINE_CONTINUATION = "\\"
# Shift+Enter only reaches the app on terminals with the kitty keyboard
# protocol and Alt+Enter needs Option-as-Meta on macOS; Ctrl+J and a trailing
# backslash work on every terminal, so the hint advertises those two.
LINE_BREAK_KEYS = frozenset({"shift+enter", "alt+enter", "ctrl+j"})
PICK_KEYS = frozenset({SUBMIT_KEY, "tab"})
PICKER_KEYS = frozenset({*PICK_KEYS, "up", "down", "escape"})


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

    _mentions: FileMentionList | None = None

    def bind_mentions(self, picker: FileMentionList) -> None:
        """Offer workspace files on `@`; while the list shows, Enter picks instead of sending."""
        self._mentions = picker
        picker.on_pick(self.insert_mention)

    def insert_mention(self, path: str) -> None:
        """Replace the mention being typed with `path` and a space that closes it."""
        query = self._open_mention()
        if query is None:
            return
        row, column = self.cursor_location
        start = (row, column - len(MENTION_SIGN) - len(query))
        self.replace(
            f"{MENTION_SIGN}{path} ", start, (row, column), maintain_selection_offset=False
        )
        if self._mentions is not None:
            self._mentions.close()

    async def _on_key(self, event: events.Key) -> None:
        if self._mentions is not None and self._mentions.display and event.key in PICKER_KEYS:
            self._consume(event)
            self._drive_mentions(self._mentions, event.key)
            return
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

    def _drive_mentions(self, picker: FileMentionList, key: str) -> None:
        if key == "up":
            picker.action_cursor_up()
        elif key == "down":
            picker.action_cursor_down()
        elif key in PICK_KEYS and picker.chosen is not None:
            self.insert_mention(picker.chosen)
        else:
            picker.close()

    @on(TextArea.SelectionChanged)
    @on(TextArea.Changed)
    def _follow_mention(self) -> None:
        if self._mentions is None:
            return
        query = self._open_mention()
        if query is None:
            self._mentions.close()
        else:
            self._mentions.show_for(query)

    def _open_mention(self) -> str | None:
        if not self.selection.is_empty:
            return None
        row, column = self.cursor_location
        return mention_at(self.document[row][:column])

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
