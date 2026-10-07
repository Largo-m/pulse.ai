from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from queue import Empty, Queue
from collections.abc import Callable
from typing import Any

from pulse.acp.capabilities import PULSE_CLIENT_CAPABILITIES, PULSE_CLIENT_INFO
from pulse.acp.models import resolve_model_display_name
from pulse.acp.run_events import RunEventRecorder
from pulse.runtimes import AgentRuntime, runtime_for_command
from pulse.mcp.config import pulse_ask_mcp_server
from pulse.mcp.http_bridge import AskQuestionHttpServer
from pulse.ports import NullPromptPort, NullStreamSink, NullUserWaitListener, UserWaitListener
from pulse.prompts.approval import APPROVE, CANCEL, SKIP, classify_outcome
from pulse.prompts.permission import PermissionPolicy, decide_permission
from pulse.prompts.text_questionnaire import parse_text_questionnaire
from pulse.runcontrol import RunControl

# An agent that asks until no doubt is left needs room; the cap only stops an
# endless question loop, and hitting it sends the step to the retry menu.
MAX_PHASE_APPROVAL_TURNS = 12

# The work plus one continuation, the agent's chance to unblock itself. An agent
# that repeats the block after one nudge needs a person; more turns only burn
# tokens to reach the same menu.
MAX_PROMPT_TURNS = 2

CANCEL_GRACE_SECONDS = 10.0
CLOSE_TIMEOUT_SECONDS = 10.0

_IDLE_CLOCK_METHODS = frozenset({"session/prompt"})


class _WatchedPrompts:
    """Prompt port proxy that signals when a question is on screen.

    While the user decides, the agent is silent, which the `session/prompt` idle
    clock would otherwise count as a timeout. Every question passes through here,
    so it is also where the dialog is recorded to the run log (`on_answer`).
    """

    def __init__(self, inner: Any, *, on_enter, on_exit, on_answer=None) -> None:
        self._inner = inner
        self._on_enter = on_enter
        self._on_exit = on_exit
        self._on_answer = on_answer

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def watched(*args: Any, **kwargs: Any) -> Any:
            if name == "respond_to_permission":
                decided = _policy_decision(args, kwargs)
                if decided is not None:
                    return decided
            self._on_enter()
            try:
                result = attr(*args, **kwargs)
                self._record(name, args, kwargs, result)
                return result
            finally:
                self._on_exit()

        return watched

    def _record(self, name: str, args: tuple[Any, ...], kwargs: dict[str, Any], result: Any) -> None:
        if self._on_answer is None:
            return
        try:
            self._on_answer(name, args, kwargs, result)
        except Exception:
            pass


def _policy_decision(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any] | None:
    """Answer to `respond_to_permission(params, *, policy, allow_terminal)` decided by policy alone.

    `None` means only a person can decide."""
    params = args[0] if args else kwargs.get("params")
    if not isinstance(params, dict):
        return None
    return decide_permission(
        params,
        policy=kwargs.get("policy", "ask"),
        allow_terminal=bool(kwargs.get("allow_terminal", False)),
    )


class AcpSessionRunner(RunEventRecorder):
    def __init__(
        self,
        command: list[str],
        *,
        cwd: str,
        permission_policy: PermissionPolicy = "ask",
        timeout_seconds: float = 600.0,
        stream: Any | None = None,
        prompt_handler: Any | None = None,
        enable_mcp_ask: bool = True,
        pulse_agent: str | None = None,
        runtime: AgentRuntime | None = None,
        control: RunControl | None = None,
    ) -> None:
        self._command = command
        self._control = control or RunControl()
        self._runtime = runtime or runtime_for_command(command)
        self._cwd = cwd
        self._permission_policy = permission_policy
        self._timeout_seconds = timeout_seconds
        self._hung = False
        self._stream = stream or NullStreamSink()
        self._prompt_handler = _WatchedPrompts(
            prompt_handler or NullPromptPort(),
            on_enter=self._begin_user_wait,
            on_exit=self._end_user_wait,
            on_answer=self._record_prompt_qa,
        )
        self._enable_mcp_ask = enable_mcp_ask
        self._pulse_agent = pulse_agent
        self._ask_bridge: AskQuestionHttpServer | None = None
        self._process: subprocess.Popen[str] | None = None
        self._responses: dict[int, dict[str, Any]] = {}
        self._response_queue: Queue[int] = Queue()
        self._reader: threading.Thread | None = None
        self._next_id = 1
        self._session_id: str | None = None
        self.last_session_id = ""
        self._bound_run_id = ""
        self._waits: UserWaitListener = NullUserWaitListener()
        self._phase_id = ""
        self._text_buffer: list[str] = []
        self._tool_payloads: dict[str, dict[str, Any]] = {}
        self._tool_kinds: dict[str, str] = {}
        self._tool_labeled: set[str] = set()
        self._run_id = str(uuid.uuid4())
        self._auth_methods: list[str] = []
        self.ask_question_count = 0
        self._activity = time.monotonic()
        self._user_waits = 0
        self._wait_started: float | None = None

    def _begin_user_wait(self) -> None:
        """A question opened: the run stops working and waits for the user.

        Only the 0->1 edge counts, so nested questions are not double-counted.
        """
        self._user_waits += 1
        if self._user_waits > 1:
            return
        self._wait_started = time.monotonic()
        self._tell_waits(self._waits.user_wait_began)
        self._notify_stream("begin_user_wait")

    def _end_user_wait(self) -> None:
        """Question answered (or dismissed): the step clock resumes."""
        self._user_waits = max(0, self._user_waits - 1)
        self._activity = time.monotonic()
        if self._user_waits > 0:
            return
        started, self._wait_started = self._wait_started, None
        seconds = time.monotonic() - started if started is not None else 0.0
        self._tell_waits(lambda: self._waits.user_wait_ended(self._phase_id, seconds))
        self._notify_stream("end_user_wait")

    def _tell_waits(self, notify: Callable[[], None]) -> None:
        """Called inside the prompt handler, so a failure goes to the run log, not up."""
        try:
            notify()
        # The user's answer must reach the agent even if the wait is not recorded.
        except Exception as error:  # noqa: BLE001
            self._save_event(
                kind="Info",
                title="Espera não registrada",
                detail=f"{type(error).__name__}: {error}",
            )

    def _notify_stream(self, method: str) -> None:
        handler = getattr(self._stream, method, None)
        if callable(handler):
            handler()

    def run_prompt(self, prompt_text: str) -> dict[str, Any]:
        self.start()
        try:
            self.initialize()
            self.authenticate()
            session = self.new_session(self._cwd)
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("Sessão ACP não retornou sessionId")
            self._activate_session(str(session_id))
            result = self.prompt(self._session_id, prompt_text)
            return result
        finally:
            self._stream.finish()
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
        phase_id: str = "",
    ) -> dict[str, Any]:
        if phase_id:
            self._phase_id = phase_id
        session = self.new_session(self._cwd, workflow=workflow)
        session_id = session.get("sessionId")
        if not session_id:
            raise RuntimeError("Sessão ACP não retornou sessionId")
        self._activate_session(str(session_id))

        self.apply_model(session, preferred_model)

        self.apply_mode(session, execute=False)
        next_prompt = initial_prompt
        phase_summary = ""
        answers_text = ""
        approved = False
        outcome = "unknown"
        phase_result: dict[str, Any] = {}

        try:
            for turn in range(MAX_PHASE_APPROVAL_TURNS):
                label = phase_label if turn == 0 else f"{phase_label} — continuação ({turn + 1})"
                self._begin_phase(label)
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

                outcome = classify_outcome(answers_text)
                if outcome == APPROVE:
                    approved = True
                    break
                if outcome in {CANCEL, SKIP}:
                    return {
                        "stopReason": phase_result.get("stopReason", "end_turn"),
                        "phaseStopReason": phase_result.get("stopReason"),
                        "askQuestionCount": self.ask_question_count,
                        "approved": False,
                        "outcome": outcome,
                        "phaseSummary": phase_summary,
                    }

                if build_continuation is None:
                    break
                next_prompt = build_continuation(
                    phase_summary=phase_summary,
                    questionnaire_answers=answers_text,
                    outcome=outcome,
                    **dict(continuation_kwargs or {}),
                )

            phase_result["approved"] = approved
            phase_result["outcome"] = outcome
            phase_result["phaseSummary"] = phase_summary
            phase_result["approvalAnswers"] = answers_text
            phase_result["askQuestionCount"] = self.ask_question_count
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
        phase_id: str = "",
        build_continuation: Callable[..., str] | None = None,
        max_turns: int = MAX_PROMPT_TURNS,
    ) -> dict[str, Any]:
        """Run the step in its own session, allowing continuation turns.

        `build_continuation` receives the turn result and returns the next prompt,
        or empty to stop. Continuing in the same session preserves the agent's context.
        """
        if phase_id:
            self._phase_id = phase_id
        session = self.new_session(self._cwd, workflow=workflow)
        session_id = session.get("sessionId")
        if not session_id:
            raise RuntimeError("Sessão ACP não retornou sessionId")
        self._activate_session(str(session_id))

        self.apply_model(session, preferred_model)

        self.apply_mode(session, execute=agent_mode)

        next_prompt = prompt_text
        parts: list[str] = []
        result: dict[str, Any] = {}
        try:
            for turn in range(max(1, max_turns)):
                if turn:
                    self._begin_phase(f"{phase_label} — continuação ({turn + 1})")
                else:
                    self._begin_phase(phase_label)
                self._stream.reset_capture()
                result = self.prompt(self._session_id, next_prompt)
                text = self._stream.agent_text().strip()
                if text:
                    parts.append(text)
                result["phaseSummary"] = "\n\n".join(parts)
                result["askQuestionCount"] = self.ask_question_count
                result["turns"] = turn + 1
                if build_continuation is None or result.get("stopReason") == "cancelled":
                    break
                follow_up = str(build_continuation(result=result, turn=turn) or "").strip()
                if not follow_up:
                    break
                next_prompt = follow_up
            return result
        finally:
            self.close_session()

    def start(self) -> None:
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
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=self._cwd,
        )
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def ensure_process(self) -> bool:
        """Restart the agent process if it is no longer alive.

        Returns `True` when a restart was needed, so retrying a step whose
        session crashed does not just repeat the crash.
        """
        alive = self._process is not None and self._process.poll() is None
        if alive and not self._hung:
            return False
        self.close()
        self._responses.clear()
        while not self._response_queue.empty():
            self._response_queue.get_nowait()
        self._session_id = None
        self._hung = False
        self.start()
        self.initialize()
        self.authenticate()
        return True

    def close(self) -> None:
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
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
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

            self._activity = time.monotonic()

            if message.get("method") and message.get("id") is not None:
                self._handle_agent_request(message)
                continue

            method = message.get("method")
            if method == "session/update":
                params = message.get("params", {})
                session_id = params.get("sessionId")
                if (
                    self._session_id is None
                    or session_id is None
                    or session_id == self._session_id
                ):
                    self._stream.handle_update(params)
                    self._record_run_event(params)
                continue

            message_id = message.get("id")
            if isinstance(message_id, int):
                self._responses[message_id] = message
                self._response_queue.put(message_id)

    def _handle_agent_request(self, message: dict[str, Any]) -> None:
        method = str(message.get("method", ""))
        params = message.get("params", {})
        request_id = message.get("id")

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
            self._send(error_payload)
            return

        self._send({"jsonrpc": "2.0", "id": request_id, "result": result})

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Processo ACP não iniciado")
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()

    def _request(
        self, method: str, params: dict[str, Any], *, timeout: float | None = None
    ) -> dict[str, Any]:
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

        idle_clock = method in _IDLE_CLOCK_METHODS
        limit = self._timeout_seconds if timeout is None else timeout
        self._activity = time.monotonic()
        deadline = self._activity + limit
        cancelling = False
        while True:
            if self._user_waits:
                self._activity = time.monotonic()
            if not cancelling and idle_clock:
                deadline = self._activity + limit
            if time.monotonic() >= deadline:
                break

            if not cancelling and method == "session/prompt" and self._control.interrupted:
                self._cancel_active_session()
                cancelling = True
                deadline = time.monotonic() + CANCEL_GRACE_SECONDS

            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(f"o processo do agente encerrou durante `{method}`")

            remaining = deadline - time.monotonic()
            try:
                response_id = self._response_queue.get(timeout=min(1.0, max(0.0, remaining)))
            except Empty:
                continue

            response = self._responses.pop(response_id, {})
            if response_id != request_id:
                continue

            if "error" in response:
                error = response["error"]
                if cancelling:
                    return {"stopReason": "cancelled"}
                raise RuntimeError(error.get("message", "Erro ACP desconhecido"))
            return response.get("result", {})

        if cancelling:
            return {"stopReason": "cancelled"}
        self._hung = True
        raise TimeoutError(f"o agente ficou {int(limit)}s sem dar sinal em `{method}`")

    def _cancel_active_session(self) -> None:
        """Ask the agent to abort the active session's turn."""
        session_id = self._session_id
        if session_id is None:
            return
        try:
            self._send(
                {
                    "jsonrpc": "2.0",
                    "method": "session/cancel",
                    "params": {"sessionId": session_id},
                }
            )
        except (RuntimeError, OSError, ValueError):
            pass

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
        self._auth_methods = [
            str(method.get("id"))
            for method in result.get("authMethods", [])
            if isinstance(method, dict) and method.get("id")
        ]
        return result

    def authenticate(self) -> dict[str, Any]:
        method_id = self._runtime.auth_method(self._auth_methods)
        if method_id is None:
            return {}
        try:
            return self._request("authenticate", {"methodId": method_id})
        except (RuntimeError, TimeoutError):
            return {}

    def apply_model(self, session: dict[str, Any], preferred_model: str | None) -> None:
        """Apply the model using the runtime dialect, without failing the session on error."""
        if self._session_id is None:
            return
        request = self._runtime.model_request(
            session, preferred_model, session_id=self._session_id
        )
        if request is None:
            return
        try:
            self._request(request.method, request.params)
        except (RuntimeError, TimeoutError) as error:
            return
        self._emit_info(f"Modelo: {resolve_model_display_name(session, request.model_id)}")

    def apply_mode(self, session: dict[str, Any], *, execute: bool) -> None:
        if self._session_id is None:
            return
        mode_id = self._runtime.resolve_mode(session, execute=execute)
        if not mode_id:
            return
        try:
            self.set_mode(self._session_id, mode_id)
        except (RuntimeError, TimeoutError):
            pass

    def new_session(self, cwd: str, *, workflow: str = "") -> dict[str, Any]:
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

    def bind_run(self, run_id: str, waits: UserWaitListener | None = None) -> None:
        """Bind the runner to a run so log, artifacts and user waits are recorded on it."""
        self._bound_run_id = run_id
        self._waits = waits or NullUserWaitListener()

    @property
    def control(self) -> RunControl:
        """Stop control for this run, checked by the engine at cut points."""
        return self._control

    def set_permission_policy(self, policy: PermissionPolicy) -> None:
        self._permission_policy = policy

    def use_agent(self, agent_id: str, policy: PermissionPolicy) -> None:
        self._pulse_agent = agent_id
        self._permission_policy = policy

    def _activate_session(self, session_id: str) -> None:
        self._tool_payloads.clear()
        self._tool_kinds.clear()
        self._tool_labeled.clear()
        self._session_id = str(session_id)
        self.last_session_id = self._session_id
        if hasattr(self._stream, "set_session_id"):
            self._stream.set_session_id(self._session_id)
        try:
            from pulse.store.sessions import persist_runtime_session

            persist_runtime_session(
                self._cwd,
                pulse_session_id=self._run_id,
                acp_session_id=self._session_id,
                agent_id=self._pulse_agent,
            )
        except Exception:
            pass

    def close_session(self) -> None:
        if self._session_id is None:
            return
        try:
            self._request(
                "session/close", {"sessionId": self._session_id}, timeout=CLOSE_TIMEOUT_SECONDS
            )
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
        try:
            return self._request(
                "session/prompt",
                {
                    "sessionId": session_id,
                    "prompt": [{"type": "text", "text": text}],
                },
            )
        finally:
            self._flush_text()

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
