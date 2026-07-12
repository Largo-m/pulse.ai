from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pulse.presentation.prompt.text_questionnaire import extract_questionnaire_block
from pulse.tui.state import CockpitState, LogKind
from pulse.tui.tool_detail import build_tool_labels, extract_tool_target, is_generic_title

_TOOL_KINDS = frozenset({"tool_call", "tool_call_update", "tool_result"})
_QUESTIONNAIRE_START = re.compile(
    r"```(?:text)?|Preciso de algumas informações|I need some information before continuing|Apresentando todas as perguntas",
    re.IGNORECASE,
)
_SETUP_READY = re.compile(r"SETUP_READY\s*", re.IGNORECASE)
_MODEL_RE = re.compile(r"^Modelo:\s*(.+)$", re.IGNORECASE)

NotifyFn = Callable[[], None]


class CockpitSink:
    cockpit = True

    def __init__(
        self,
        state: CockpitState,
        *,
        on_change: NotifyFn | None = None,
        cwd: str | None = None,
    ) -> None:
        self._state = state
        self._on_change = on_change
        self._cwd = cwd
        self._streaming_message = False
        self._agent_text = ""
        self._questionnaire_mode = False
        self._questionnaire_announced = False
        self._tool_ids: set[str] = set()

    def set_cwd(self, cwd: str | None) -> None:
        self._cwd = cwd

    def reset_capture(self) -> None:
        self._agent_text = ""
        self._questionnaire_mode = False
        self._questionnaire_announced = False
        self._streaming_message = False

    def agent_text(self) -> str:
        return self._agent_text

    def has_text_questionnaire(self) -> bool:
        return extract_questionnaire_block(self._agent_text) is not None

    def handle_update(self, params: dict[str, Any]) -> None:
        update = params.get("update", params)
        if not isinstance(update, dict):
            return
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
                    self._state.append_assistant(visible)
                    self._streaming_message = True
                    self._emit()
            return

        if kind == "agent_thought_chunk":
            return

        if kind in _TOOL_KINDS:
            self._handle_tool(update, kind=str(kind))
            return

        if kind == "session_info_update":
            title = update.get("title")
            if title:
                self._finish_message_line()
                title_text = str(title)
                match = _MODEL_RE.match(title_text)
                if match:
                    self._state.set_model(match.group(1).strip())
                if not is_generic_title(title_text):
                    self._state.add_info(title_text)
                    self._emit()

    def begin_phase(self, title: str) -> None:
        self.finish()
        self._tool_ids.clear()
        self._state.begin_phase(title)
        self._state.add_info(title)
        self._emit()

    def finish(self) -> None:
        self._finish_message_line()

    def finish_question_prompt(self) -> None:
        self._finish_message_line()
        self._state.finish_assistant()
        self._emit()

    def _handle_tool(self, update: dict[str, Any], *, kind: str) -> None:
        tool_id = str(update.get("toolCallId") or "")
        log_kind, target, detail = build_tool_labels(update, cwd=self._cwd)

        if kind == "tool_call":
            if tool_id and tool_id in self._tool_ids:
                return
            if tool_id:
                self._tool_ids.add(tool_id)
            self._finish_message_line()
            self._state.add_tool_entry(
                log_kind,
                target,
                detail,
                tool_id=tool_id,
            )
            self._emit()
            return

        if kind in {"tool_call_update", "tool_result"}:
            target = extract_tool_target(update, cwd=self._cwd)
            if tool_id and tool_id in self._tool_ids:
                if not target or target == "…":
                    return
                existing_kind = None
                for entry in self._state.entries:
                    if entry.tool_id == tool_id:
                        existing_kind = entry.kind
                        break
                updated = self._state.update_tool_entry(
                    tool_id,
                    kind=existing_kind,
                    title=target,
                    detail=target,
                )
                if updated is not None:
                    self._emit()
                return

            if not target and not update.get("title"):
                return
            if tool_id:
                self._tool_ids.add(tool_id)
            self._finish_message_line()
            self._state.add_tool_entry(
                log_kind,
                target or log_kind.value,
                target or log_kind.value,
                tool_id=tool_id,
            )
            self._emit()

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
        self._state.add_info("Questionário interativo")
        self._emit()

    def _finish_message_line(self) -> None:
        if self._streaming_message:
            self._streaming_message = False
            self._state.finish_assistant()

    def _emit(self) -> None:
        if self._on_change is not None:
            self._on_change()
