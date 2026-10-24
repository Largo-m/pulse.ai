from __future__ import annotations

import contextlib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx

from pulse.client.engine_client import EngineClient
from pulse.client.protocol import PING, REPLAY_END, RunForm
from pulse.domain.ports import JsonObject, StepRow, StreamSink
from pulse.replies.permission import PermissionPolicy, parse_policy
from pulse.replies.text_questionnaire import (
    TextQuestionnaire,
    parse_text_questionnaire,
    questionnaire_from_payload,
)

DETACHED = -1
# Error entries this session adds to the run's screen, titled like the TUI's own.
ERROR_TITLE = "Erro"
WORKFLOW_FAILED_TITLE = "Workflow falhou"
INVALID_QUESTIONNAIRE_TITLE = "Invalid questionnaire"
INVALID_QUESTIONNAIRE_REASON = (
    "The agent asked for a questionnaire, but its questions could not be parsed."
)


class RunView(StreamSink, Protocol):
    """The screen a run streams into: the engine's sink plus what only an attached client sees."""

    def replay_finished(self) -> None: ...

    def mark_awaiting(self, waiting: bool, *, since: float | None = None) -> None: ...

    def mark_stopped(self) -> None: ...


class RunPrompts(Protocol):
    """Who answers the questions the daemon forwards, one method per prompt kind."""

    def respond_to_ask_question(self, params: JsonObject) -> JsonObject: ...

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject: ...

    def respond_to_permission(
        self,
        params: JsonObject,
        *,
        policy: PermissionPolicy,
        allow_terminal: bool = False,
    ) -> JsonObject: ...

    def run_parsed_questionnaire(self, questionnaire: TextQuestionnaire) -> str | None: ...

    def ask_text(self, prompt: str, *, title: str = "") -> str | None: ...

    def select_choice(
        self, prompt: str, choices: list[tuple[str, int]], *, title: str = ""
    ) -> int | None: ...


def _text(event: JsonObject, key: str, default: str = "") -> str:
    return str(event.get(key, default))


def _texts(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _int(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _turn(event: JsonObject) -> int:
    """The phase's turn; a missing or bogus one is the first."""
    return max(1, _int(event.get("turn"), 1))


def _step_rows(value: object) -> list[StepRow]:
    if not isinstance(value, list):
        return []
    return [
        StepRow(
            id=str(item.get("id", "")),
            label=str(item.get("label", "")),
            rounds=_int(item.get("rounds"), 1),
        )
        for item in value
        if isinstance(item, dict)
    ]


class EngineRunSession:
    def __init__(
        self,
        *,
        stream: RunView,
        prompt_handler: RunPrompts,
        client: EngineClient | None = None,
    ) -> None:
        self._stream = stream
        self._prompt_handler = prompt_handler
        self._client = client or EngineClient()
        self._exit_code = 1
        self._owns_client = client is None
        self.run_id = ""
        self._detached = False
        self._replaying = False
        self._replayed_prompts: dict[str, JsonObject] = {}
        self._handlers: dict[str, Callable[[JsonObject], None]] = {
            PING: self._on_replay_marker,
            REPLAY_END: self._on_replay_marker,
            "prompt.answered": lambda event: self._forget_prompt(_text(event, "id")),
            "session.update": self._on_session_update,
            "phase.begin": lambda event: stream.begin_phase(
                _text(event, "title"), turn=_turn(event)
            ),
            "session.model": lambda event: stream.set_model(_text(event, "model")),
            "phase.info": lambda event: stream.info(_text(event, "title")),
            "phase.error": lambda event: stream.error(
                _text(event, "title", ERROR_TITLE), _text(event, "reason")
            ),
            "phases.sync": self._on_phases_sync,
            "run.context": lambda event: stream.set_context(
                cwd=_text(event, "cwd"), branch=_text(event, "branch")
            ),
            "session.id": lambda event: stream.set_session_id(_text(event, "session_id")),
            "run.awaiting": self._on_awaiting,
            "run.stopped": lambda _event: stream.mark_stopped(),
            "stream.finish": lambda _event: stream.finish(),
            "stream.finish_question": lambda _event: stream.finish_question_prompt(),
            "prompt.request": self._on_prompt_request,
            "run.finished": self._on_run_finished,
        }
        self._answerers: dict[str, Callable[[JsonObject], object]] = {
            "ask_question": lambda payload: self._prompt_handler.respond_to_ask_question(payload),
            "create_plan": lambda payload: self._prompt_handler.respond_to_create_plan(payload),
            "permission": self._answer_permission,
            "questionnaire": self._handle_questionnaire,
            "text": self._answer_text,
            "choice": self._answer_choice,
        }

    def run(
        self,
        *,
        workflow_id: str,
        user_prompt: str,
        workspace: str | Path | None = None,
        resume_run_id: str | None = None,
        branch: str = "",
        form: RunForm | None = None,
    ) -> int:
        self.start(
            workflow_id=workflow_id,
            user_prompt=user_prompt,
            workspace=workspace,
            resume_run_id=resume_run_id,
            branch=branch,
            form=form,
        )
        return self.listen()

    def start(
        self,
        *,
        workflow_id: str,
        user_prompt: str,
        workspace: str | Path | None = None,
        resume_run_id: str | None = None,
        branch: str = "",
        form: RunForm | None = None,
    ) -> str:
        """Create the run in the daemon and return its id, without listening."""
        self._client.ensure_daemon()
        created = self._client.start_run(
            workflow_id,
            prompt=user_prompt,
            workspace=str(workspace) if workspace is not None else None,
            resume_run_id=resume_run_id,
            branch=branch,
            form=form,
        )
        self.run_id = str(created["id"])
        return self.run_id

    def attach(self, run_id: str) -> int:
        """Listen to an already running run, from its beginning.

        The daemon replays the bus history before live events, so the same
        `stream` rebuilds the whole run.
        """
        self.run_id = run_id
        self._replaying = True
        return self.listen()

    def listen(self) -> int:
        if not self.run_id:
            return self._exit_code
        try:
            for event in self._client.stream_events(self.run_id):
                if self._detached:
                    break
                self._dispatch(event)
        except (httpx.HTTPError, httpx.StreamError):
            # `detach` closes the client under the read; that cut is the detach, not a failure.
            if not self._detached:
                raise
        finally:
            if self._owns_client:
                self._client.close()
        return DETACHED if self._detached else self._exit_code

    def detach(self) -> None:
        """Drop the stream without touching the run, which keeps going in the daemon.

        Closing the client aborts the in-flight read; `stream.ping` guarantees
        the loop wakes up even if it does not.
        """
        self._detached = True
        # Leaving must not fail on a socket that is already gone; the run is untouched.
        with contextlib.suppress(OSError):
            self._client.close()

    def stop(self) -> bool:
        """Stop requested from the UI, outside the thread running the run."""
        if not self.run_id:
            return False
        try:
            self._client.cancel_run(self.run_id)
        except httpx.HTTPError:
            return False
        return True

    def _dispatch(self, event: JsonObject) -> None:
        """Unknown event types are ignored: a newer daemon may publish more than we know."""
        handler = self._handlers.get(_text(event, "type"))
        if handler is not None:
            handler(event)

    def _on_replay_marker(self, _event: JsonObject) -> None:
        if self._replaying:
            self._finish_replay()

    def _on_session_update(self, event: JsonObject) -> None:
        params = event.get("params")
        if isinstance(params, dict):
            self._stream.handle_update(params)

    def _on_phases_sync(self, event: JsonObject) -> None:
        self._stream.apply_phase_statuses(
            steps=_step_rows(event.get("steps")),
            done_ids=_texts(event.get("done_ids")),
            skipped_ids=_texts(event.get("skipped_ids")),
            failed_ids=_texts(event.get("failed_ids")),
            blocked_ids=_texts(event.get("blocked_ids")),
        )

    def _on_awaiting(self, event: JsonObject) -> None:
        since = event.get("since")
        self._stream.mark_awaiting(
            bool(event.get("waiting")),
            since=float(since) if isinstance(since, (int, float)) else None,
        )

    def _on_prompt_request(self, event: JsonObject) -> None:
        if self._replaying:
            self._replayed_prompts[_text(event, "id")] = event
            return
        self._handle_prompt(event)

    def _on_run_finished(self, event: JsonObject) -> None:
        self._exit_code = _int(event.get("exit_code"), 0)
        message = event.get("error")
        if message:
            self._stream.error(WORKFLOW_FAILED_TITLE, str(message))
        self._stream.finish()

    def _finish_replay(self) -> None:
        """Replay is over; any prompt still unanswered is live."""
        self._replaying = False
        pending = list(self._replayed_prompts.values())
        self._replayed_prompts.clear()
        self._stream.replay_finished()
        for event in pending:
            self._handle_prompt(event)

    def _forget_prompt(self, prompt_id: str) -> None:
        """A prompt was resolved; during replay this drops it from the pending queue.

        Live, this only arrives when another attached window answered; the
        blocked window learns via the 404 when it answers.
        """
        if prompt_id:
            self._replayed_prompts.pop(prompt_id, None)

    def _handle_prompt(self, event: JsonObject) -> None:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        self._stream.finish_question_prompt()
        answerer = self._answerers.get(_text(event, "kind"))
        answer = (
            answerer(payload) if answerer is not None else {"outcome": {"outcome": "cancelled"}}
        )
        if self._detached:
            return
        self._client.answer_prompt(_text(event, "id"), answer)

    def _answer_permission(self, payload: JsonObject) -> JsonObject:
        params = payload.get("params")
        return self._prompt_handler.respond_to_permission(
            params if isinstance(params, dict) else {},
            policy=parse_policy(str(payload.get("policy") or "ask")),
            allow_terminal=bool(payload.get("allow_terminal")),
        )

    def _answer_text(self, payload: JsonObject) -> str | None:
        return self._prompt_handler.ask_text(
            str(payload.get("prompt") or ""), title=str(payload.get("title") or "")
        )

    def _answer_choice(self, payload: JsonObject) -> object:
        raw = payload.get("choices")
        choices = [
            (str(item.get("label", "")), _int(item.get("index"), 0))
            for item in (raw if isinstance(raw, list) else [])
            if isinstance(item, dict)
        ]
        picked = self._prompt_handler.select_choice(
            str(payload.get("prompt") or ""), choices, title=str(payload.get("title") or "")
        )
        return {"index": picked} if isinstance(picked, int) else picked

    def _handle_questionnaire(self, payload: JsonObject) -> str | None:
        parsed = questionnaire_from_payload(payload) or parse_text_questionnaire(
            self._stream.agent_text()
        )
        if parsed is not None:
            return self._prompt_handler.run_parsed_questionnaire(parsed)
        self._stream.error(INVALID_QUESTIONNAIRE_TITLE, INVALID_QUESTIONNAIRE_REASON)
        return None
