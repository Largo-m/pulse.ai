from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import httpx

from pulse.client.engine_client import EngineClient
from pulse.client.protocol import PING, REPLAY_END

DETACHED = -1


class EngineRunSession:
    def __init__(
        self,
        *,
        stream: Any,
        prompt_handler: Any,
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
        self._replayed_prompts: dict[str, dict[str, Any]] = {}

    def run(
        self,
        *,
        workflow_id: str,
        user_prompt: str,
        workspace: str | Path | None = None,
        resume_run_id: str | None = None,
    ) -> int:
        self.start(
            workflow_id=workflow_id,
            user_prompt=user_prompt,
            workspace=workspace,
            resume_run_id=resume_run_id,
        )
        return self.listen()

    def start(
        self,
        *,
        workflow_id: str,
        user_prompt: str,
        workspace: str | Path | None = None,
        resume_run_id: str | None = None,
    ) -> str:
        """Create the run in the daemon and return its id, without listening."""
        self._client.ensure_daemon()
        created = self._client.start_run(
            workflow_id,
            prompt=user_prompt,
            workspace=str(workspace) if workspace is not None else None,
            resume_run_id=resume_run_id,
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

    def _dispatch(self, event: dict[str, Any]) -> None:
        kind = str(event.get("type", ""))
        if kind == PING:
            if self._replaying:
                self._finish_replay()
            return
        if kind == REPLAY_END:
            if self._replaying:
                self._finish_replay()
            return
        if kind == "prompt.answered":
            self._forget_prompt(str(event.get("id", "")))
            return
        if kind == "session.update":
            params = event.get("params")
            if isinstance(params, dict):
                self._stream.handle_update(params)
            return
        if kind == "phase.begin":
            self._stream.begin_phase(str(event.get("title", "")))
            return
        if kind == "phase.info":
            info = getattr(self._stream, "info", None)
            if callable(info):
                info(str(event.get("title", "")))
            return
        if kind == "phase.error":
            error = getattr(self._stream, "error", None)
            if callable(error):
                error(str(event.get("title", "Erro")), str(event.get("reason", "")))
            return
        if kind == "phases.sync":
            apply = getattr(self._stream, "apply_phase_statuses", None)
            if callable(apply):
                payload = {key: value for key, value in event.items() if key != "type"}
                apply(**payload)
            return
        if kind == "run.context":
            setter = getattr(self._stream, "set_context", None)
            if callable(setter):
                setter(
                    cwd=str(event.get("cwd", "")),
                    branch=str(event.get("branch", "")),
                )
            return
        if kind == "session.id":
            setter = getattr(self._stream, "set_session_id", None)
            if callable(setter):
                setter(str(event.get("session_id", "")))
            return
        if kind == "run.awaiting":
            handler = getattr(self._stream, "mark_awaiting", None)
            if callable(handler):
                since = event.get("since")
                handler(
                    bool(event.get("waiting")),
                    since=float(since) if isinstance(since, (int, float)) else None,
                )
            return
        if kind == "run.stopped":
            handler = getattr(self._stream, "mark_stopped", None)
            if callable(handler):
                handler()
            return
        if kind == "stream.finish":
            self._stream.finish()
            return
        if kind == "stream.finish_question":
            self._stream.finish_question_prompt()
            return
        if kind == "prompt.request":
            if self._replaying:
                self._replayed_prompts[str(event.get("id", ""))] = event
                return
            self._handle_prompt(event)
            return
        if kind == "run.finished":
            code = event.get("exit_code")
            self._exit_code = 0 if code is None else int(code)
            message = event.get("error")
            if message:
                error = getattr(self._stream, "error", None)
                if callable(error):
                    error("Workflow falhou", str(message))
            self._stream.finish()
            return

    def _finish_replay(self) -> None:
        """Replay is over; any prompt still unanswered is live."""
        self._replaying = False
        pending = list(self._replayed_prompts.values())
        self._replayed_prompts.clear()
        replay_end = getattr(self._stream, "replay_finished", None)
        if callable(replay_end):
            replay_end()
        for event in pending:
            self._handle_prompt(event)

    def _forget_prompt(self, prompt_id: str) -> None:
        """A prompt was resolved; during replay this drops it from the pending queue.

        Live, this only arrives when another attached window answered; the
        blocked window learns via the 404 when it answers.
        """
        if prompt_id:
            self._replayed_prompts.pop(prompt_id, None)

    def _handle_prompt(self, event: dict[str, Any]) -> None:
        prompt_id = str(event.get("id", ""))
        prompt_kind = str(event.get("kind", ""))
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        self._stream.finish_question_prompt()
        answer: Any
        if prompt_kind == "ask_question":
            answer = self._prompt_handler.respond_to_ask_question(payload)
        elif prompt_kind == "create_plan":
            answer = self._prompt_handler.respond_to_create_plan(payload)
        elif prompt_kind == "permission":
            answer = self._prompt_handler.respond_to_permission(
                payload.get("params") or {},
                policy=str(payload.get("policy") or "ask"),
                allow_terminal=bool(payload.get("allow_terminal")),
            )
        elif prompt_kind == "questionnaire":
            answer = self._handle_questionnaire(payload)
        elif prompt_kind == "text":
            ask_text = getattr(self._prompt_handler, "ask_text", None)
            answer = (
                ask_text(
                    str(payload.get("prompt") or ""),
                    title=str(payload.get("title") or ""),
                )
                if callable(ask_text)
                else None
            )
        elif prompt_kind == "choice":
            select = getattr(self._prompt_handler, "select_choice", None)
            choices_raw = payload.get("choices") or []
            choices = [
                (str(item.get("label", "")), int(item.get("index", 0)))
                for item in choices_raw
                if isinstance(item, dict)
            ]
            if callable(select):
                picked = select(
                    str(payload.get("prompt") or ""),
                    choices,
                    title=str(payload.get("title") or ""),
                )
                answer = {"index": picked} if isinstance(picked, int) else picked
            else:
                answer = None
        else:
            answer = {"outcome": {"outcome": "cancelled"}}
        if self._detached:
            return
        self._client.answer_prompt(prompt_id, answer)

    def _handle_questionnaire(self, payload: dict[str, Any]) -> Any:
        from pulse.replies.text_questionnaire import (
            parse_text_questionnaire,
            questionnaire_from_payload,
        )

        parsed = questionnaire_from_payload(payload)
        if parsed is None:
            getter = getattr(self._stream, "agent_text", None)
            text = getter() if callable(getter) else ""
            parsed = parse_text_questionnaire(str(text or ""))
        run_parsed = getattr(self._prompt_handler, "run_parsed_questionnaire", None)
        if parsed is not None and callable(run_parsed):
            return run_parsed(parsed)
        self._emit_error(
            "Questionário inválido",
            "O agente pediu um questionário, mas as perguntas não puderam ser abertas.",
        )
        return None

    def _emit_error(self, title: str, reason: str) -> None:
        emit = getattr(self._stream, "error", None)
        if callable(emit):
            emit(title, reason)
