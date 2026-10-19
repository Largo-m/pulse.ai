from __future__ import annotations

import json
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from typing import Any, cast

from pulse.acp.capabilities import (
    CLIENT_RUNS_TERMINAL,
    PULSE_CLIENT_CAPABILITIES,
    PULSE_CLIENT_INFO,
)
from pulse.acp.reply_clock import ReplyClock
from pulse.acp.step_turns import StepTurns
from pulse.acp.watched_prompts import WatchedPrompts
from pulse.domain.control import RunControl
from pulse.domain.ports import (
    AgentProfile,
    JsonObject,
    NullPromptPort,
    NullQuestionChannel,
    NullSessionLog,
    NullStreamSink,
    NullUserWaitListener,
    PromptPort,
    QuestionChannel,
    RuntimeDialect,
    SessionLog,
    StreamSink,
    UserWaitListener,
)
from pulse.replies.permission import PermissionPolicy, parse_policy
from pulse.replies.session_models import resolve_model_display_name
from pulse.replies.text_questionnaire import parse_text_questionnaire

CLOSE_TIMEOUT_SECONDS = 10.0


class AcpSessionRunner(StepTurns):
    """One agent process speaking ACP for a run, one session per step.

    What differs per runtime (`runtime`), where mid-turn questions arrive
    (`questions`) and where the run log goes (`session_log`) are handed in by
    the daemon; without a channel the agent gets no `AskQuestion` tool, and
    without a log nothing is recorded.
    """

    def __init__(
        self,
        command: list[str],
        *,
        cwd: str,
        runtime: RuntimeDialect,
        permission_policy: PermissionPolicy = "ask",
        timeout_seconds: float = 600.0,
        stream: StreamSink | None = None,
        prompt_handler: PromptPort | None = None,
        questions: QuestionChannel | None = None,
        session_log: SessionLog | None = None,
        pulse_agent: str | None = None,
        control: RunControl | None = None,
    ) -> None:
        self._command = command
        self._control = control or RunControl()
        self._runtime = runtime
        self._cwd = cwd
        self._permission_policy = permission_policy
        self._timeout_seconds = timeout_seconds
        self._hung = False
        self._stream: StreamSink = stream or NullStreamSink()
        # The proxy forwards every port method by name, so it is a `PromptPort`
        # for whatever the wrapped port implements.
        self._prompt_handler = cast(
            PromptPort,
            WatchedPrompts(
                prompt_handler or NullPromptPort(),
                on_enter=self._begin_user_wait,
                on_exit=self._end_user_wait,
                on_answer=self._record_dialog,
            ),
        )
        self._questions: QuestionChannel = questions or NullQuestionChannel()
        self._log: SessionLog = session_log or NullSessionLog()
        self._mcp: list[JsonObject] = []
        self._pulse_agent = pulse_agent
        self._process: subprocess.Popen[str] | None = None
        self._responses: dict[int, dict[str, Any]] = {}
        self._response_queue: Queue[int] = Queue()
        self._reader: threading.Thread | None = None
        self._next_id = 1
        self._session_id: str | None = None
        self.last_session_id = ""
        self._waits: UserWaitListener = NullUserWaitListener()
        self._phase_id = ""
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
        self._stream.begin_user_wait()

    def _end_user_wait(self) -> None:
        """Question answered (or dismissed): the step clock resumes."""
        self._user_waits = max(0, self._user_waits - 1)
        self._activity = time.monotonic()
        if self._user_waits > 0:
            return
        started, self._wait_started = self._wait_started, None
        seconds = time.monotonic() - started if started is not None else 0.0
        self._tell_waits(lambda: self._waits.user_wait_ended(self._phase_id, seconds))
        self._stream.end_user_wait()

    def _tell_waits(self, notify: Callable[[], None]) -> None:
        """Called inside the prompt handler, so a failure goes to the run log, not up."""
        try:
            notify()
        # The user's answer must reach the agent even if the wait is not recorded.
        except Exception as error:  # noqa: BLE001
            self._log.notice("User wait not recorded", f"{type(error).__name__}: {error}")

    def run_prompt(self, prompt_text: str) -> dict[str, Any]:
        self.start()
        try:
            self.initialize()
            self.authenticate()
            session = self.new_session(self._cwd)
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("ACP session returned no sessionId")
            active_session = str(session_id)
            self._activate_session(active_session)
            return self.prompt(active_session, prompt_text)
        finally:
            self._stream.finish()
            self.close()

    def start(self) -> None:
        self._mcp = self._questions.open(self._prompt_handler, self._record_ask_question)

        # argv list from the user's effective config, never from agent output.
        self._process = subprocess.Popen(  # noqa: S603
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

    def open(self, cwd: Path) -> None:
        """Start the agent where the run works, then handshake and log in."""
        self._cwd = str(cwd)
        self.start()
        self.initialize()
        self.authenticate()

    def revive(self) -> bool:
        """Restart the agent process if it is no longer alive.

        Returns `True` when a restart was needed, so retrying a step whose
        session crashed does not just repeat the crash.
        """
        alive = self._process is not None and self._process.poll() is None
        if alive and not self._hung:
            return False
        self._boot()
        return True

    def close(self) -> None:
        self._questions.close()
        self._mcp = []

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
                if self._session_id is None or session_id is None or session_id == self._session_id:
                    self._stream.handle_update(params)
                    self._log.update(params)
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
                    allow_terminal=CLIENT_RUNS_TERMINAL,
                )
            else:
                result = {"outcome": "cancelled"}
        # Any failure answering the agent becomes a JSON-RPC error reply: the
        # agent is waiting on this id, and the read loop must keep running.
        except Exception as error:  # noqa: BLE001
            self._log.notice("Agent request failed", f"{method}: {type(error).__name__}: {error}")
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
            raise RuntimeError("ACP process not started")
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

        limit = self._timeout_seconds if timeout is None else timeout
        self._activity = time.monotonic()
        clock = ReplyClock.for_request(method, limit, self._activity)
        response = self._await_response(request_id, method, clock)
        if response is None:
            if clock.cancelling:
                return {"stopReason": "cancelled"}
            self._hung = True
            raise TimeoutError(f"the agent gave no sign of life for {int(limit)}s in `{method}`")
        if "error" in response:
            if clock.cancelling:
                return {"stopReason": "cancelled"}
            raise RuntimeError(response["error"].get("message", "unknown ACP error"))
        return response.get("result", {})

    def _await_response(
        self, request_id: int, method: str, clock: ReplyClock
    ) -> dict[str, Any] | None:
        """The reply to `request_id`, or `None` once the clock runs out."""
        while True:
            if self._user_waits:
                self._activity = time.monotonic()
            clock.follow(self._activity)
            if clock.expired():
                return None
            self._cancel_if_interrupted(method, clock)
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(f"the agent process exited during `{method}`")
            response = self._next_response(request_id, clock.remaining())
            if response is not None:
                return response

    def _cancel_if_interrupted(self, method: str, clock: ReplyClock) -> None:
        """A stop cuts the turn in flight, once; protocol requests always finish."""
        if clock.cancelling or method != "session/prompt" or not self._control.interrupted:
            return
        self._cancel_active_session()
        clock.start_cancel()

    def _next_response(self, request_id: int, remaining: float) -> dict[str, Any] | None:
        """The next reply if it answers `request_id`; a stale reply is dropped."""
        try:
            response_id = self._response_queue.get(timeout=min(1.0, remaining))
        except Empty:
            return None
        response = self._responses.pop(response_id, {})
        return response if response_id == request_id else None

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
        request = self._runtime.model_request(session, preferred_model, session_id=self._session_id)
        if request is None:
            return
        try:
            self._request(request.method, request.params)
        except (RuntimeError, TimeoutError):
            return
        self._stream.set_model(resolve_model_display_name(session, request.model_id))

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
            "mcpServers": list(self._mcp),
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
        self._log.bind_run(run_id)
        self._waits = waits or NullUserWaitListener()

    @property
    def control(self) -> RunControl:
        """Stop control for this run, checked by the engine at cut points."""
        return self._control

    @property
    def prompts(self) -> PromptPort:
        """The prompt port as the engine must use it: every question it asks is a user wait."""
        return self._prompt_handler

    def _boot(self) -> None:
        """Replace the agent process and finish the handshake on the current command."""
        self.close()
        self._responses.clear()
        while not self._response_queue.empty():
            self._response_queue.get_nowait()
        self._session_id = None
        self._hung = False
        self.start()
        self.initialize()
        self.authenticate()

    def use_agent(self, profile: AgentProfile) -> None:
        self._pulse_agent = profile.agent_id
        self._permission_policy = parse_policy(profile.permission_policy)
        command = list(profile.acp_command)
        if not command or command == self._command or profile.dialect is None:
            return
        self._command = command
        self._runtime = profile.dialect
        if self._process is not None:
            self._boot()

    def _activate_session(self, session_id: str) -> None:
        self._session_id = str(session_id)
        self.last_session_id = self._session_id
        self._stream.set_session_id(self._session_id)
        self._log.enter_session(
            self._session_id,
            pulse_session_id=self._run_id,
            cwd=self._cwd,
            agent_id=self._pulse_agent,
        )

    def _enter_phase(self, phase_id: str) -> None:
        self._phase_id = phase_id
        self._log.enter_step(phase_id)

    def _begin_phase(self, label: str, *, turn: int = 1) -> None:
        """Open the phase on screen and leave the same marker in the recorded log.

        Without it, history would merge consecutive turns into a single block.
        """
        self._log.flush()
        self._stream.begin_phase(label, turn=turn)
        self._log.phase(label, turn=turn)

    def _record_dialog(
        self,
        name: str,
        args: tuple[object, ...],
        kwargs: dict[str, object],
        result: object,
    ) -> None:
        self._log.dialog(name, args, kwargs, result)

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
            self._log.flush()

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
