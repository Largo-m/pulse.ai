from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StreamSink(Protocol):
    def handle_update(self, params: dict[str, Any]) -> None: ...

    def begin_phase(self, title: str) -> None: ...

    def reset_capture(self) -> None: ...

    def agent_text(self) -> str: ...

    def finish(self) -> None: ...

    def finish_question_prompt(self) -> None: ...


@runtime_checkable
class PromptPort(Protocol):
    def respond_to_ask_question(self, params: dict[str, Any]) -> dict[str, Any]: ...

    def respond_to_create_plan(self, params: dict[str, Any]) -> dict[str, Any]: ...

    def respond_to_permission(
        self,
        params: dict[str, Any],
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> dict[str, Any]: ...

    def run_parsed_questionnaire(self, questionnaire: Any) -> str | None: ...

    def run_text_questionnaire(self, text: str) -> str | None: ...

    def ask_text(self, prompt: str, *, title: str = "") -> str | None: ...


class NullStreamSink:
    def __init__(self) -> None:
        self._agent_text = ""
        self.cockpit = False

    def handle_update(self, params: dict[str, Any]) -> None:
        update = params.get("update", {})
        if not isinstance(update, dict):
            return
        if update.get("sessionUpdate") != "agent_message_chunk":
            return
        content = update.get("content", {})
        if isinstance(content, dict) and content.get("type") == "text":
            self._agent_text += str(content.get("text", ""))

    def begin_phase(self, title: str) -> None:
        return None

    def reset_capture(self) -> None:
        self._agent_text = ""

    def agent_text(self) -> str:
        return self._agent_text

    def finish(self) -> None:
        return None

    def finish_question_prompt(self) -> None:
        return None

    def info(self, title: str) -> None:
        return None

    def error(self, title: str, reason: str = "") -> None:
        return None

    def apply_phase_statuses(self, **kwargs: Any) -> None:
        return None

    def apply_routed_flow(self, flow: str) -> None:
        return None

    def set_tasks(self, items: list[tuple[str, str, str]]) -> None:
        return None

    def set_session_id(self, session_id: str) -> None:
        return None


class NullPromptPort:
    def respond_to_ask_question(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"outcome": {"outcome": "cancelled"}}

    def respond_to_create_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"outcome": {"outcome": "cancelled"}}

    def respond_to_permission(
        self,
        params: dict[str, Any],
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> dict[str, Any]:
        return {"outcome": {"outcome": "cancelled"}}

    def run_parsed_questionnaire(self, questionnaire: Any) -> str | None:
        return None

    def run_text_questionnaire(self, text: str) -> str | None:
        return None

    def ask_text(self, prompt: str, *, title: str = "") -> str | None:
        return None

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Any]],
        *,
        title: str = "",
    ) -> Any | None:
        return None
