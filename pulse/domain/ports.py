from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypeAlias, TypedDict, TypeVar, runtime_checkable

from pulse.domain.run import RunRecord, StepRecord

JsonObject: TypeAlias = dict[str, object]
"""An ACP JSON-RPC payload. Its shape belongs to the runtime, so adapters narrow it at the edge."""

Choice = TypeVar("Choice")


class StepRow(TypedDict):
    """One step as the panel lists it; fan-out changes the list mid-run."""

    id: str
    label: str
    rounds: int


class Questionnaire(Protocol):
    """A questionnaire parsed from the agent's text; `pulse.replies` owns the concrete shape."""

    @property
    def title(self) -> str: ...

    @property
    def raw(self) -> str: ...


@runtime_checkable
class StreamSink(Protocol):
    """Where a run shows its progress: the cockpit over SSE, or a plain console.

    The engine calls every method unconditionally; an adapter with nothing to
    show for one implements it as a no-op instead of leaving it out.
    """

    def handle_update(self, params: JsonObject) -> None: ...

    def begin_phase(self, title: str) -> None: ...

    def reset_capture(self) -> None: ...

    def agent_text(self) -> str: ...

    def finish(self) -> None: ...

    def finish_question_prompt(self) -> None: ...

    def begin_user_wait(self) -> None: ...

    def end_user_wait(self) -> None: ...

    def set_context(self, *, cwd: str, branch: str) -> None: ...

    def set_session_id(self, session_id: str) -> None: ...

    def info(self, title: str) -> None: ...

    def error(self, title: str, reason: str = "") -> None: ...

    def apply_phase_statuses(
        self,
        *,
        steps: Sequence[StepRow] = (),
        done_ids: Sequence[str] = (),
        skipped_ids: Sequence[str] = (),
        failed_ids: Sequence[str] = (),
        blocked_ids: Sequence[str] = (),
    ) -> None: ...


@runtime_checkable
class PromptPort(Protocol):
    def respond_to_ask_question(self, params: JsonObject) -> JsonObject: ...

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject: ...

    def respond_to_permission(
        self,
        params: JsonObject,
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> JsonObject: ...

    def run_parsed_questionnaire(self, questionnaire: Questionnaire) -> str | None: ...

    def run_text_questionnaire(self, text: str) -> str | None: ...

    def ask_text(self, prompt: str, *, title: str = "") -> str | None: ...

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Choice]],
        *,
        title: str = "",
    ) -> Choice | None: ...


@runtime_checkable
class RunRepository(Protocol):
    """Where a run lives between steps, so a stopped or crashed run can be resumed."""

    def create(
        self,
        *,
        run_id: str,
        workflow_id: str,
        workspace: Path,
        user_prompt: str,
        steps: Sequence[StepRecord],
    ) -> RunRecord:
        """A new running run whose steps are all pending, stored before it is returned."""
        ...

    def load(self, run_id: str) -> RunRecord | None: ...

    def save(self, run: RunRecord) -> None:
        """Store the whole aggregate at once: the run and its steps never disagree."""
        ...

    def artifacts(self, run_id: str) -> list[str]:
        """Paths the agents wrote during the run, relative to where it worked."""
        ...


@runtime_checkable
class UserWaitListener(Protocol):
    """Told when a question to the user opens and closes, so the run can pause its clock."""

    def user_wait_began(self) -> None: ...

    def user_wait_ended(self, step_id: str, seconds: float) -> None: ...


class NullStreamSink:
    def __init__(self) -> None:
        self._agent_text = ""

    def handle_update(self, params: JsonObject) -> None:
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

    def begin_user_wait(self) -> None:
        return None

    def end_user_wait(self) -> None:
        return None

    def info(self, title: str) -> None:
        return None

    def error(self, title: str, reason: str = "") -> None:
        return None

    def apply_phase_statuses(
        self,
        *,
        steps: Sequence[StepRow] = (),
        done_ids: Sequence[str] = (),
        skipped_ids: Sequence[str] = (),
        failed_ids: Sequence[str] = (),
        blocked_ids: Sequence[str] = (),
    ) -> None:
        return None

    def set_session_id(self, session_id: str) -> None:
        return None

    def set_context(self, *, cwd: str, branch: str) -> None:
        return None


class NullUserWaitListener:
    def user_wait_began(self) -> None:
        return None

    def user_wait_ended(self, step_id: str, seconds: float) -> None:
        return None


class NullPromptPort:
    def respond_to_ask_question(self, params: JsonObject) -> JsonObject:
        return {"outcome": {"outcome": "cancelled"}}

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject:
        return {"outcome": {"outcome": "cancelled"}}

    def respond_to_permission(
        self,
        params: JsonObject,
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> JsonObject:
        return {"outcome": {"outcome": "cancelled"}}

    def run_parsed_questionnaire(self, questionnaire: Questionnaire) -> str | None:
        return None

    def run_text_questionnaire(self, text: str) -> str | None:
        return None

    def ask_text(self, prompt: str, *, title: str = "") -> str | None:
        return None

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Choice]],
        *,
        title: str = "",
    ) -> Choice | None:
        return None
