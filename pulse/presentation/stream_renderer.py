from __future__ import annotations

import re
from typing import Any

from rich.console import Console

from pulse.presentation.prompt.text_questionnaire import extract_questionnaire_block

_SILENT_TOOL_KINDS = frozenset({"tool_call", "tool_call_update", "tool_result"})
_QUESTIONNAIRE_START = re.compile(
    r"```(?:text)?|Preciso de algumas informações|I need some information before continuing|Apresentando todas as perguntas",
    re.IGNORECASE,
)
_SETUP_READY = re.compile(r"SETUP_READY\s*", re.IGNORECASE)


class StreamRenderer:
    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console(highlight=False, soft_wrap=True)
        self._streaming_message = False
        self._agent_text = ""
        self._questionnaire_mode = False
        self._questionnaire_announced = False

    def reset_capture(self) -> None:
        self._agent_text = ""
        self._questionnaire_mode = False
        self._questionnaire_announced = False

    def agent_text(self) -> str:
        return self._agent_text

    def has_text_questionnaire(self) -> bool:
        return extract_questionnaire_block(self._agent_text) is not None

    def handle_update(self, params: dict[str, Any]) -> None:
        update = params.get("update", {})
        kind = update.get("sessionUpdate")

        if kind == "agent_message_chunk":
            content = update.get("content", {})
            if content.get("type") == "text":
                text = str(content.get("text", ""))
                if text:
                    self._agent_text += text
                    self._maybe_enter_questionnaire_mode()
                    if self._questionnaire_mode:
                        self._announce_questionnaire_once()
                        return
                    visible = _SETUP_READY.sub("", text)
                    if not visible:
                        return
                    self._console.print(visible, end="")
                    self._streaming_message = True
            return

        if kind == "agent_thought_chunk":
            return

        if kind in _SILENT_TOOL_KINDS:
            title = update.get("title") or update.get("toolName")
            if not title:
                return
            self._finish_message_line()
            self._console.print(f"[dim]{title}[/dim]")
            return

        if kind == "session_info_update":
            title = update.get("title")
            if title:
                self._finish_message_line()
                self._console.print(f"[cyan]{title}[/cyan]")

    def _maybe_enter_questionnaire_mode(self) -> None:
        if self._questionnaire_mode:
            return
        if _QUESTIONNAIRE_START.search(self._agent_text):
            self._questionnaire_mode = True
            self._finish_message_line()

    def _announce_questionnaire_once(self) -> None:
        if self._questionnaire_announced:
            return
        self._questionnaire_announced = True
        self._console.print()
        self._console.print(
            "[bold cyan]↳ Questionário interativo[/bold cyan] "
            "[dim]· use ↑ ↓ para navegar, Enter para confirmar, Esc para cancelar[/dim]"
        )

    def _finish_message_line(self) -> None:
        if self._streaming_message:
            self._console.print()
            self._streaming_message = False

    def begin_phase(self, title: str) -> None:
        self.finish()
        self._console.print()
        self._console.print(f"[bold cyan]▸ {title}[/bold cyan]")
        self._console.print()

    def finish(self) -> None:
        self._finish_message_line()

    def finish_question_prompt(self) -> None:
        self._finish_message_line()
        self._console.print()
