from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from queue import Empty, Queue
from pathlib import Path
from collections.abc import Callable
from typing import Any

from pulse.acp.capabilities import PULSE_CLIENT_CAPABILITIES, PULSE_CLIENT_INFO
from pulse.acp.logger import AcpLogger
from pulse.acp.models import resolve_interview_model_id
from pulse.mcp.config import pulse_ask_mcp_server
from pulse.mcp.http_bridge import AskQuestionHttpServer
from pulse.plan.analyze_codebase_prompt import build_analyze_codebase_artifact_prompt
from pulse.plan.new_issue_prompt import (
    build_phase_continuation_prompt,
    classify_phase_questionnaire_outcome,
)
from pulse.plan.quick_prompt import (
    build_quick_continuation_prompt,
    build_quick_implement_prompt,
    classify_quick_questionnaire_outcome,
)
from pulse.plan.setup_project_prompt import build_setup_project_artifact_prompt
from pulse.presentation.prompt.handler import PermissionPolicy, PromptHandler
from pulse.presentation.prompt.text_questionnaire import parse_text_questionnaire
from pulse.presentation.stream_renderer import StreamRenderer

INTERVIEW_MODE = "agent"
AGENT_MODE = "agent"
MAX_QUICK_PLAN_TURNS = 4
MAX_PHASE_APPROVAL_TURNS = 4


class AcpSessionRunner:
    def __init__(
        self,
        command: list[str],
        *,
        cwd: str,
        permission_policy: PermissionPolicy = "ask",
        timeout_seconds: float = 600.0,
        stream: StreamRenderer | None = None,
        prompt_handler: PromptHandler | None = None,
        enable_mcp_ask: bool = True,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._permission_policy = permission_policy
        self._timeout_seconds = timeout_seconds
        self._stream = stream or StreamRenderer()
        self._prompt_handler = prompt_handler or PromptHandler()
        self._enable_mcp_ask = enable_mcp_ask
        self._ask_bridge: AskQuestionHttpServer | None = None
        self._process: subprocess.Popen[str] | None = None
        self._responses: dict[int, dict[str, Any]] = {}
        self._response_queue: Queue[int] = Queue()
        self._reader: threading.Thread | None = None
        self._next_id = 1
        self._session_id: str | None = None
        self._run_id = str(uuid.uuid4())
        self.ask_question_count = 0
        self._logger = AcpLogger(self._run_id)

    def run_prompt(self, prompt_text: str) -> dict[str, Any]:
        self._logger.log_event("run_prompt_start", {"cwd": self._cwd})
        self.start()
        try:
            self.initialize()
            self.authenticate()
            session = self.new_session(self._cwd)
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("Sessão ACP não retornou sessionId")
            self._session_id = str(session_id)
            self._logger.set_session_id(self._session_id)
            result = self.prompt(self._session_id, prompt_text)
            self._logger.log_event("run_prompt_done", {"stop_reason": result.get("stopReason")})
            return result
        finally:
            self._stream.finish()
            self.close()

    def run_setup_project(
        self,
        *,
        interview_prompt: str,
        workspace: Path,
        user_prompt: str,
        skill_dir: Path,
        preferred_model: str | None = None,
    ) -> dict[str, Any]:
        self._run_id = str(uuid.uuid4())
        self._logger = AcpLogger(self._run_id)
        self._logger.log_event(
            "run_setup_project_start",
            {"workspace": str(workspace), "preferred_model": preferred_model},
        )
        self.start()
        try:
            self.initialize()
            self.authenticate()
            session = self.new_session(self._cwd)
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("Sessão ACP não retornou sessionId")
            self._session_id = str(session_id)
            self._logger.set_session_id(self._session_id)

            model_id = resolve_interview_model_id(session, preferred_model)
            if model_id:
                self.set_model(self._session_id, model_id)
                self._emit_info(f"Modelo: {model_id}")

            self.set_mode(self._session_id, INTERVIEW_MODE)
            self._stream.begin_phase("Fase 1 — Análise do projeto")
            self._stream.reset_capture()
            interview_result = self.prompt(self._session_id, interview_prompt)
            if interview_result.get("stopReason") == "cancelled":
                interview_result["askQuestionCount"] = self.ask_question_count
                return interview_result

            phase1_analysis = self._stream.agent_text()
            answers_text = self._run_text_questionnaire(phase1_analysis)
            if answers_text is None:
                return {
                    "stopReason": "cancelled",
                    "interviewStopReason": interview_result.get("stopReason"),
                    "askQuestionCount": self.ask_question_count,
                }
            artifact_prompt = build_setup_project_artifact_prompt(
                workspace=workspace,
                user_prompt=user_prompt,
                skill_dir=skill_dir,
                analysis_summary=phase1_analysis,
                questionnaire_answers=answers_text,
            )

            self.set_mode(self._session_id, AGENT_MODE)
            self._stream.begin_phase("Fase 2 — Gerando .pulse/specs/project/")
            self._stream.reset_capture()
            artifact_result = self.prompt(self._session_id, artifact_prompt)
            artifact_result["interviewStopReason"] = interview_result.get("stopReason")
            artifact_result["askQuestionCount"] = self.ask_question_count
            self._logger.log_event(
                "run_setup_project_done",
                {
                    "stop_reason": artifact_result.get("stopReason"),
                    "interview_stop_reason": artifact_result.get("interviewStopReason"),
                    "ask_question_count": self.ask_question_count,
                    "log_path": str(self._logger.path),
                },
            )
            return artifact_result
        finally:
            self._stream.finish()
            self.close_session()
            self.close()

    def run_analyze_codebase(
        self,
        *,
        explore_prompt: str,
        workspace: Path,
        user_prompt: str,
        skill_dir: Path,
        preferred_model: str | None = None,
    ) -> dict[str, Any]:
        self._run_id = str(uuid.uuid4())
        self._logger = AcpLogger(self._run_id)
        self._logger.log_event(
            "run_analyze_codebase_start",
            {"workspace": str(workspace), "preferred_model": preferred_model},
        )
        self.start()
        try:
            self.initialize()
            self.authenticate()
            session = self.new_session(self._cwd, workflow="analyze-codebase")
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("Sessão ACP não retornou sessionId")
            self._session_id = str(session_id)
            self._logger.set_session_id(self._session_id)

            model_id = resolve_interview_model_id(session, preferred_model)
            if model_id:
                self.set_model(self._session_id, model_id)
                self._emit_info(f"Modelo: {model_id}")

            self.set_mode(self._session_id, INTERVIEW_MODE)
            self._stream.begin_phase("Fase 1 — Explorando codebase")
            self._stream.reset_capture()
            explore_result = self.prompt(self._session_id, explore_prompt)
            if explore_result.get("stopReason") == "cancelled":
                explore_result["askQuestionCount"] = self.ask_question_count
                return explore_result

            phase1_analysis = self._stream.agent_text()
            answers_text = self._run_text_questionnaire(phase1_analysis)
            if answers_text is None:
                return {
                    "stopReason": "cancelled",
                    "exploreStopReason": explore_result.get("stopReason"),
                    "askQuestionCount": self.ask_question_count,
                }
            artifact_prompt = build_analyze_codebase_artifact_prompt(
                workspace=workspace,
                user_prompt=user_prompt,
                skill_dir=skill_dir,
                analysis_summary=phase1_analysis,
                questionnaire_answers=answers_text,
            )

            self.set_mode(self._session_id, AGENT_MODE)
            self._stream.begin_phase("Fase 2 — Gerando .pulse/specs/codebase/")
            self._stream.reset_capture()
            artifact_result = self.prompt(self._session_id, artifact_prompt)
            artifact_result["exploreStopReason"] = explore_result.get("stopReason")
            artifact_result["askQuestionCount"] = self.ask_question_count
            self._logger.log_event(
                "run_analyze_codebase_done",
                {
                    "stop_reason": artifact_result.get("stopReason"),
                    "explore_stop_reason": artifact_result.get("exploreStopReason"),
                    "ask_question_count": self.ask_question_count,
                    "log_path": str(self._logger.path),
                },
            )
            return artifact_result
        finally:
            self._stream.finish()
            self.close_session()
            self.close()

    def run_isolated_phase(
        self,
        *,
        workflow: str,
        phase_label: str,
        initial_prompt: str,
        preferred_model: str | None = None,
        build_continuation: Callable[..., str] | None = None,
        continuation_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._logger.log_event(
            "run_isolated_phase_start",
            {"workflow": workflow, "phase": phase_label},
        )
        session = self.new_session(self._cwd, workflow=workflow)
        session_id = session.get("sessionId")
        if not session_id:
            raise RuntimeError("Sessão ACP não retornou sessionId")
        self._session_id = str(session_id)

        model_id = resolve_interview_model_id(session, preferred_model)
        if model_id:
            self.set_model(self._session_id, model_id)
            self._emit_info(f"Modelo: {model_id}")

        self.set_mode(self._session_id, INTERVIEW_MODE)
        next_prompt = initial_prompt
        phase_summary = ""
        answers_text = ""
        approved = False
        outcome = "unknown"
        phase_result: dict[str, Any] = {}

        try:
            for turn in range(MAX_PHASE_APPROVAL_TURNS):
                label = phase_label if turn == 0 else f"{phase_label} — continuação ({turn + 1})"
                self._stream.begin_phase(label)
                self._stream.reset_capture()
                phase_result = self.prompt(self._session_id, next_prompt)
                if phase_result.get("stopReason") == "cancelled":
                    phase_result["approved"] = False
                    phase_result["outcome"] = "cancelled"
                    phase_result["phaseSummary"] = phase_summary
                    return phase_result

                phase_summary = self._stream.agent_text()
                answers_text = self._run_text_questionnaire(phase_summary)
                if answers_text is None:
                    return {
                        "stopReason": "cancelled",
                        "phaseStopReason": phase_result.get("stopReason"),
                        "askQuestionCount": self.ask_question_count,
                        "approved": False,
                        "outcome": "cancelled",
                        "phaseSummary": phase_summary,
                    }

                if not answers_text.strip():
                    break

                outcome = classify_phase_questionnaire_outcome(answers_text)
                if outcome == "approve":
                    approved = True
                    break
                if outcome == "cancel":
                    return {
                        "stopReason": phase_result.get("stopReason", "end_turn"),
                        "phaseStopReason": phase_result.get("stopReason"),
                        "askQuestionCount": self.ask_question_count,
                        "approved": False,
                        "outcome": "cancel",
                        "phaseSummary": phase_summary,
                    }
                if outcome == "skip":
                    return {
                        "stopReason": phase_result.get("stopReason", "end_turn"),
                        "phaseStopReason": phase_result.get("stopReason"),
                        "askQuestionCount": self.ask_question_count,
                        "approved": False,
                        "outcome": "skip",
                        "phaseSummary": phase_summary,
                    }

                if build_continuation is not None:
                    kwargs = dict(continuation_kwargs or {})
                    next_prompt = build_continuation(
                        phase_summary=phase_summary,
                        questionnaire_answers=answers_text,
                        outcome=outcome,
                        **kwargs,
                    )
                else:
                    next_prompt = build_phase_continuation_prompt(
                        phase_summary=phase_summary,
                        questionnaire_answers=answers_text,
                        outcome=outcome,
                        **(continuation_kwargs or {}),
                    )

            phase_result["approved"] = approved
            phase_result["outcome"] = outcome if approved else outcome
            phase_result["phaseSummary"] = phase_summary
            phase_result["approvalAnswers"] = answers_text
            phase_result["askQuestionCount"] = self.ask_question_count
            self._logger.log_event(
                "run_isolated_phase_done",
                {
                    "phase": phase_label,
                    "approved": approved,
                    "outcome": outcome,
                },
            )
            return phase_result
        finally:
            self.close_session()

    def run_isolated_prompt(
        self,
        *,
        workflow: str,
        phase_label: str,
        prompt_text: str,
        preferred_model: str | None = None,
        agent_mode: bool = True,
    ) -> dict[str, Any]:
        self._logger.log_event(
            "run_isolated_prompt_start",
            {"workflow": workflow, "phase": phase_label},
        )
        session = self.new_session(self._cwd, workflow=workflow)
        session_id = session.get("sessionId")
        if not session_id:
            raise RuntimeError("Sessão ACP não retornou sessionId")
        self._session_id = str(session_id)

        model_id = resolve_interview_model_id(session, preferred_model)
        if model_id:
            self.set_model(self._session_id, model_id)
            self._emit_info(f"Modelo: {model_id}")

        mode = AGENT_MODE if agent_mode else INTERVIEW_MODE
        self.set_mode(self._session_id, mode)
        self._stream.begin_phase(phase_label)
        self._stream.reset_capture()

        try:
            result = self.prompt(self._session_id, prompt_text)
            result["phaseSummary"] = self._stream.agent_text()
            result["askQuestionCount"] = self.ask_question_count
            self._logger.log_event(
                "run_isolated_prompt_done",
                {"phase": phase_label, "stop_reason": result.get("stopReason")},
            )
            return result
        finally:
            self.close_session()

    def run_quick(
        self,
        *,
        plan_prompt: str,
        workspace: Path,
        user_prompt: str,
        skill_dir: Path,
        preferred_model: str | None = None,
    ) -> dict[str, Any]:
        self._run_id = str(uuid.uuid4())
        self._logger = AcpLogger(self._run_id)
        self._logger.log_event(
            "run_quick_start",
            {"workspace": str(workspace), "preferred_model": preferred_model},
        )
        self.start()
        try:
            self.initialize()
            self.authenticate()
            session = self.new_session(self._cwd, workflow="fix-bug")
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("Sessão ACP não retornou sessionId")
            self._session_id = str(session_id)
            self._logger.set_session_id(self._session_id)

            model_id = resolve_interview_model_id(session, preferred_model)
            if model_id:
                self.set_model(self._session_id, model_id)
                self._emit_info(f"Modelo: {model_id}")

            self.set_mode(self._session_id, INTERVIEW_MODE)
            next_prompt = plan_prompt
            plan_summary = ""
            answers_text = ""
            approved = False
            outcome = "unknown"

            for turn in range(MAX_QUICK_PLAN_TURNS):
                phase_label = (
                    "Fase 1 — Planejando quick task"
                    if turn == 0
                    else f"Fase 1 — Continuando ({turn + 1})"
                )
                self._stream.begin_phase(phase_label)
                self._stream.reset_capture()
                plan_result = self.prompt(self._session_id, next_prompt)
                if plan_result.get("stopReason") == "cancelled":
                    plan_result["askQuestionCount"] = self.ask_question_count
                    plan_result["approved"] = False
                    plan_result["outcome"] = "cancelled"
                    return plan_result

                plan_summary = self._stream.agent_text()
                answers_text = self._run_text_questionnaire(plan_summary)
                if answers_text is None:
                    return {
                        "stopReason": "cancelled",
                        "planStopReason": plan_result.get("stopReason"),
                        "askQuestionCount": self.ask_question_count,
                        "approved": False,
                        "outcome": "cancelled",
                    }

                if not answers_text.strip():
                    if turn == 0:
                        approved = False
                        outcome = "unknown"
                    break

                outcome = classify_quick_questionnaire_outcome(answers_text)
                if outcome == "approve":
                    approved = True
                    break
                if outcome == "cancel":
                    return {
                        "stopReason": plan_result.get("stopReason", "end_turn"),
                        "planStopReason": plan_result.get("stopReason"),
                        "askQuestionCount": self.ask_question_count,
                        "approved": False,
                        "outcome": "cancel",
                    }

                next_prompt = build_quick_continuation_prompt(
                    workspace=workspace,
                    user_prompt=user_prompt,
                    skill_dir=skill_dir,
                    plan_summary=plan_summary,
                    questionnaire_answers=answers_text,
                    outcome=outcome,
                )

            if not approved:
                self._logger.log_event(
                    "run_quick_not_approved",
                    {
                        "ask_question_count": self.ask_question_count,
                        "outcome": outcome,
                        "log_path": str(self._logger.path),
                    },
                )
                return {
                    "stopReason": plan_result.get("stopReason", "end_turn"),
                    "planStopReason": plan_result.get("stopReason"),
                    "askQuestionCount": self.ask_question_count,
                    "approved": False,
                    "outcome": outcome,
                }

            implement_prompt = build_quick_implement_prompt(
                workspace=workspace,
                user_prompt=user_prompt,
                skill_dir=skill_dir,
                plan_summary=plan_summary,
                approval_answers=answers_text,
            )

            self.set_mode(self._session_id, AGENT_MODE)
            self._stream.begin_phase("Fase 2 — Implementando quick task")
            self._stream.reset_capture()
            implement_result = self.prompt(self._session_id, implement_prompt)
            implement_result["planStopReason"] = plan_result.get("stopReason")
            implement_result["askQuestionCount"] = self.ask_question_count
            implement_result["approved"] = True
            self._logger.log_event(
                "run_quick_done",
                {
                    "stop_reason": implement_result.get("stopReason"),
                    "plan_stop_reason": implement_result.get("planStopReason"),
                    "ask_question_count": self.ask_question_count,
                    "log_path": str(self._logger.path),
                },
            )
            return implement_result
        finally:
            self._stream.finish()
            self.close_session()
            self.close()

    def start(self) -> None:
        self._logger.log_event("process_start", {"command": self._command, "cwd": self._cwd})
        if self._enable_mcp_ask:
            self._ask_bridge = AskQuestionHttpServer(
                prompt_handler=self._prompt_handler,
                on_question=self._record_ask_question,
            )
            self._ask_bridge.start()

        self._process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self._cwd,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def close(self) -> None:
        self._logger.log_event("process_close")
        if self._ask_bridge is not None:
            self._ask_bridge.close()
            self._ask_bridge = None

        if self._process is None:
            return
        if self._process.stdin:
            try:
                self._process.stdin.close()
            except OSError:
                pass
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
        self._process = None

    def _read_stdout(self) -> None:
        if self._process is None or self._process.stdout is None:
            return

        for line in self._process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            self._logger.log_received(message)

            if message.get("method") and message.get("id") is not None:
                self._handle_agent_request(message)
                continue

            method = message.get("method")
            if method == "session/update":
                params = message.get("params", {})
                self._logger.log_update(params)
                if self._session_id is None or params.get("sessionId") == self._session_id:
                    self._stream.handle_update(params)
                continue

            message_id = message.get("id")
            if isinstance(message_id, int):
                self._responses[message_id] = message
                self._response_queue.put(message_id)

    def _handle_agent_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method", ""))
        params = message.get("params", {})
        request_id = message.get("id")

        self._logger.log_event("agent_request", {"method": method, "id": request_id})

        try:
            if method == "cursor/ask_question":
                self.ask_question_count += 1
                self._stream.finish_question_prompt()
                result = self._prompt_handler.respond_to_ask_question(params)
            elif method == "cursor/create_plan":
                self._stream.finish_question_prompt()
                result = self._prompt_handler.respond_to_create_plan(params)
            elif method in {"session/request_permission", "cursor/request_permission"}:
                result = self._prompt_handler.respond_to_permission(
                    params,
                    policy=self._permission_policy,
                    allow_terminal=PULSE_CLIENT_CAPABILITIES.get("terminal", False),
                )
            else:
                result = {"outcome": "cancelled"}
        except Exception as error:
            error_payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(error)},
            }
            self._logger.log_event(
                "agent_request_error", {"method": method, "error": str(error)}
            )
            self._send(error_payload)
            return

        self._logger.log_event("agent_request_response", {"method": method, "result": result})
        self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Processo ACP não iniciado")
        self._logger.log_sent(payload)
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )

        deadline = time.monotonic() + self._timeout_seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                response_id = self._response_queue.get(timeout=min(1.0, remaining))
            except Empty:
                continue

            response = self._responses.pop(response_id, {})
            if response_id != request_id:
                continue

            if "error" in response:
                error = response["error"]
                raise RuntimeError(error.get("message", "Erro ACP desconhecido"))
            return response.get("result", {})

        raise TimeoutError(f"Timeout aguardando resposta de `{method}`")

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": PULSE_CLIENT_CAPABILITIES,
                "clientInfo": PULSE_CLIENT_INFO,
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return result

    def authenticate(self) -> dict[str, Any]:
        try:
            return self._request("authenticate", {"methodId": "cursor_login"})
        except RuntimeError:
            return {}

    def new_session(self, cwd: str, *, workflow: str = "setup-project") -> dict[str, Any]:
        params: dict[str, Any] = {
            "cwd": cwd,
            "mcpServers": self._mcp_servers(),
            "_meta": {
                "pulse": {
                    "runId": self._run_id,
                    "workflow": workflow,
                }
            },
        }
        return self._request("session/new", params)

    def close_session(self) -> None:
        if self._session_id is None:
            return
        try:
            self._request("session/close", {"sessionId": self._session_id})
        except (RuntimeError, TimeoutError):
            pass
        self._session_id = None

    def set_mode(self, session_id: str, mode_id: str) -> dict[str, Any]:
        return self._request(
            "session/set_mode",
            {"sessionId": session_id, "modeId": mode_id},
        )

    def set_model(self, session_id: str, model_id: str) -> dict[str, Any]:
        return self._request(
            "session/set_model",
            {"sessionId": session_id, "modelId": model_id},
        )

    def prompt(self, session_id: str, text: str) -> dict[str, Any]:
        return self._request(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": text}],
            },
        )

    def _mcp_servers(self) -> list[dict[str, Any]]:
        if not self._enable_mcp_ask or self._ask_bridge is None:
            return []
        return [pulse_ask_mcp_server(url=self._ask_bridge.url)]

    def _run_text_questionnaire(self, phase1_text: str) -> str | None:
        questionnaire = parse_text_questionnaire(phase1_text)
        if questionnaire is None:
            return ""
        answers = self._prompt_handler.run_parsed_questionnaire(questionnaire)
        if answers is None:
            return None
        self.ask_question_count += len(questionnaire.questions)
        return answers

    def _record_ask_question(self) -> None:
        self.ask_question_count += 1

    def _emit_info(self, title: str) -> None:
        self._stream.handle_update(
            {
                "update": {
                    "sessionUpdate": "session_info_update",
                    "title": title,
                }
            }
        )
