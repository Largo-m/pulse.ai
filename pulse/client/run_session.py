from __future__ import annotations

from pathlib import Path
from typing import Any

from pulse.client.engine_client import EngineClient


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
        #: Conhecido só depois que o daemon aceita a run; parar antes disso
        #: simplesmente não faz nada.
        self.run_id = ""

    def run(
        self,
        *,
        workflow_id: str,
        user_prompt: str,
        workspace: str | Path | None = None,
        resume_run_id: str | None = None,
    ) -> int:
        self._client.ensure_daemon()
        created = self._client.start_run(
            workflow_id,
            prompt=user_prompt,
            workspace=str(workspace) if workspace is not None else None,
            resume_run_id=resume_run_id,
        )
        run_id = str(created["id"])
        self.run_id = run_id
        try:
            for event in self._client.stream_events(run_id):
                self._dispatch(event)
        finally:
            if self._owns_client:
                self._client.close()
        return self._exit_code

    def stop(self) -> bool:
        """Parar vem da UI, fora da thread que roda a run."""
        if not self.run_id:
            return False
        try:
            self._client.cancel_run(self.run_id)
        except Exception:
            return False
        return True

    def _dispatch(self, event: dict[str, Any]) -> None:
        kind = str(event.get("type", ""))
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
        if kind == "session.id":
            setter = getattr(self._stream, "set_session_id", None)
            if callable(setter):
                setter(str(event.get("session_id", "")))
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
        self._client.answer_prompt(prompt_id, answer)

    def _handle_questionnaire(self, payload: dict[str, Any]) -> Any:
        from pulse.prompts.text_questionnaire import (
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
