from __future__ import annotations

import sys
from typing import TextIO


class StreamRenderer:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out = out or sys.stdout
        self._thinking_open = False
        self._output_open = False

    def status(self, message: str) -> None:
        self._close_sections()
        self._emit("[STATUS]", message)

    def thinking(self, text: str, *, delta: bool = False) -> None:
        if not text:
            return
        if not self._thinking_open:
            self._close_sections()
            self._write_line("[THINKING]")
            self._thinking_open = True
        self._write(text, end="" if delta else "\n")

    def output(self, text: str, *, delta: bool = False) -> None:
        if not text:
            return
        if not self._output_open:
            self._close_sections()
            self._write_line("[OUTPUT]")
            self._output_open = True
        self._write(text, end="" if delta else "\n")

    def question(self, text: str) -> None:
        self._close_sections()
        self._emit("[QUESTION]", text)

    def user_answer(self, text: str) -> None:
        self._emit("> resposta do usuário:", text)

    def success(self, message: str) -> None:
        self._close_sections()
        self._emit("[SUCCESS]", message)

    def error(self, message: str) -> None:
        self._close_sections()
        self._emit("[ERROR]", message, stream=sys.stderr)

    def blank(self) -> None:
        self._close_sections()
        self._write("\n")
        self._out.flush()

    def _close_sections(self) -> None:
        if self._thinking_open or self._output_open:
            self._write("\n")
        self._thinking_open = False
        self._output_open = False

    def _emit(self, prefix: str, message: str, stream: TextIO | None = None) -> None:
        target = stream or self._out
        target.write(f"{prefix} {message}\n")
        target.flush()

    def _write_line(self, line: str) -> None:
        self._out.write(f"{line}\n")
        self._out.flush()

    def _write(self, text: str, end: str = "\n") -> None:
        self._out.write(text + end)
        self._out.flush()
