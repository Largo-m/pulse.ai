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
from pulse.acp.logger import AcpLogger
from pulse.acp.models import resolve_model_display_name
from pulse.runtimes import AgentRuntime, runtime_for_command
from pulse.mcp.config import pulse_ask_mcp_server
from pulse.mcp.http_bridge import AskQuestionHttpServer
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.prompts.approval import APPROVE, CANCEL, SKIP, classify_outcome
from pulse.prompts.permission import PermissionPolicy
from pulse.prompts.text_questionnaire import parse_text_questionnaire
from pulse.runcontrol import RunControl

#: Teto de rodadas de pergunta/resposta dentro de um step. Um agente que
#: pergunta até não sobrar dúvida precisa de folga; o teto existe só para não
#: deixar um agente em loop infinito — ao estourar, o step cai no retry.
MAX_PHASE_APPROVAL_TURNS = 12

#: Depois de pedir `session/cancel`, quanto esperamos o agente fechar o turno
#: por conta própria antes de considerar cancelado mesmo assim.
CANCEL_GRACE_SECONDS = 10.0

#: `session/prompt` é o único pedido sem prazo previsível: implementar uma task
#: leva o tempo que levar. Para ele o relógio é de *silêncio* — ver `_request`.
_IDLE_CLOCK_METHODS = frozenset({"session/prompt"})


class _WatchedPrompts:
    """Proxy do prompt port que avisa quando há uma pergunta na tela.

    Enquanto o usuário decide, o agente fica calado — e silêncio é justamente o
    que o relógio de `session/prompt` mede. Sem isto, uma aprovação que demorou
    mais que o timeout derrubava o step por "timeout", culpando o agente por
    uma espera que era nossa.
    """

    def __init__(self, inner: Any, *, on_enter, on_exit) -> None:
        self._inner = inner
        self._on_enter = on_enter
        self._on_exit = on_exit

    def __getattr__(self, name: str) -> Any:
        # AttributeError vaza de propósito: quem pergunta por `select_choice`
        # num port que não tem precisa continuar ouvindo "não tem".
        attr = getattr(self._inner, name)
        if not callable(attr):
            return attr

        def watched(*args: Any, **kwargs: Any) -> Any:
            self._on_enter()
            try:
                return attr(*args, **kwargs)
            finally:
                self._on_exit()

        return watched


class AcpSessionRunner:
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
        #: Sem controle externo (CLI), o padrão nunca pausa nem para.
        self._control = control or RunControl()
        self._runtime = runtime or runtime_for_command(command)
        self._cwd = cwd
        self._permission_policy = permission_policy
        self._timeout_seconds = timeout_seconds
        self._stream = stream or NullStreamSink()
        self._prompt_handler = _WatchedPrompts(
            prompt_handler or NullPromptPort(),
            on_enter=self._begin_user_wait,
            on_exit=self._end_user_wait,
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
        #: Run a que este runner está ligado (`bind_run`). Vazio = não grava log.
        self._bound_run_id = ""
        self._phase_id = ""
        #: Texto do agente acumulado até o próximo tool call / fim do prompt.
        self._text_buffer: list[str] = []
        self._run_id = str(uuid.uuid4())
        self._auth_methods: list[str] = []
        self.ask_question_count = 0
        self._logger = AcpLogger(self._run_id)
        #: Última vez que o agente deu sinal de vida, para o relógio de silêncio.
        self._activity = time.monotonic()
        #: Perguntas abertas na tela. Enquanto houver, o silêncio é nosso.
        self._user_waits = 0

    def _begin_user_wait(self) -> None:
        self._user_waits += 1

    def _end_user_wait(self) -> None:
        self._user_waits = max(0, self._user_waits - 1)
        self._activity = time.monotonic()

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
            self._activate_session(str(session_id))
            result = self.prompt(self._session_id, prompt_text)
            self._logger.log_event("run_prompt_done", {"stop_reason": result.get("stopReason")})
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
        self._logger.log_event(
            "run_isolated_phase_start",
            {"workflow": workflow, "phase": phase_label},
        )
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
                    # Sem como retomar a conversa, insistir só repetiria o mesmo
                    # turno: devolve não-aprovado e deixa o motor decidir.
                    break
                next_prompt = build_continuation(
                    phase_summary=phase_summary,
                    questionnaire_answers=answers_text,
                    outcome=outcome,
                    **dict(continuation_kwargs or {}),
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
        phase_id: str = "",
    ) -> dict[str, Any]:
        if phase_id:
            self._phase_id = phase_id
        self._logger.log_event(
            "run_isolated_prompt_start",
            {"workflow": workflow, "phase": phase_label},
        )
        session = self.new_session(self._cwd, workflow=workflow)
        session_id = session.get("sessionId")
        if not session_id:
            raise RuntimeError("Sessão ACP não retornou sessionId")
        self._activate_session(str(session_id))

        self.apply_model(session, preferred_model)

        self.apply_mode(session, execute=agent_mode)
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

    def ensure_process(self) -> bool:
        """Reergue o processo do agente se ele não está mais de pé.

        Devolve `True` quando precisou reiniciar. Existe para o retry de um step
        que caiu junto com a sessão: sem isto, "Refazer" só repetiria a queda.
        """
        if self._process is not None and self._process.poll() is None:
            return False
        self._logger.log_event("process_revive")
        self.close()
        self._responses.clear()
        while not self._response_queue.empty():
            self._response_queue.get_nowait()
        self._session_id = None
        self.start()
        self.initialize()
        self.authenticate()
        return True

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

            # Qualquer linha serve como sinal de vida: é o que segura o relógio
            # de silêncio de um `session/prompt` longo.
            self._activity = time.monotonic()
            self._logger.log_received(message)

            if message.get("method") and message.get("id") is not None:
                self._handle_agent_request(message)
                continue

            method = message.get("method")
            if method == "session/update":
                params = message.get("params", {})
                self._logger.log_update(params)
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

        # Para `session/prompt` o prazo conta do último sinal de vida, não do
        # envio: um step que trabalha por meia hora, falando o tempo todo, não é
        # um step travado. Para o resto do protocolo, que é pergunta e resposta
        # imediata, o prazo continua sendo o total.
        idle_clock = method in _IDLE_CLOCK_METHODS
        self._activity = time.monotonic()
        deadline = self._activity + self._timeout_seconds
        cancelling = False
        while True:
            if self._user_waits:
                # A pergunta está na tela: o relógio espera o usuário.
                self._activity = time.monotonic()
            if not cancelling and idle_clock:
                deadline = self._activity + self._timeout_seconds
            if time.monotonic() >= deadline:
                break

            # Pausar/parar corta o turno em voo. Só vale para `session/prompt`:
            # o resto do protocolo é rápido e cancelar no meio deixaria a
            # sessão num estado que o agente não sabe descrever.
            if not cancelling and method == "session/prompt" and self._control.interrupted:
                self._cancel_active_session()
                cancelling = True
                deadline = time.monotonic() + CANCEL_GRACE_SECONDS

            if self._process is not None and self._process.poll() is not None:
                # Sem processo não há resposta para esperar — nem os 10 minutos
                # de timeout que `session/close` gastaria à toa no caminho.
                self._logger.log_event("process_gone", {"method": method})
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
                    # O agente reclamou do cancelamento: o corte é o que importa.
                    return {"stopReason": "cancelled"}
                raise RuntimeError(error.get("message", "Erro ACP desconhecido"))
            return response.get("result", {})

        if cancelling:
            # O agente não fechou o turno no prazo — a sessão é descartada logo
            # em seguida (`close_session`), então seguir como cancelado é seguro.
            self._logger.log_event("prompt_cancel_timeout", {"method": method})
            return {"stopReason": "cancelled"}
        raise TimeoutError(
            f"o agente ficou {int(self._timeout_seconds)}s sem dar sinal em `{method}`"
        )

    def _cancel_active_session(self) -> None:
        """Pede ao agente para abortar o turno da sessão ativa."""
        session_id = self._session_id
        if session_id is None:
            return
        self._logger.log_event("session_cancel", {"session_id": session_id})
        try:
            self._send(
                {
                    "jsonrpc": "2.0",
                    "method": "session/cancel",
                    "params": {"sessionId": session_id},
                }
            )
        except (RuntimeError, OSError, ValueError) as error:
            # Processo já caiu ou stdin fechou: o turno morre junto, tudo bem.
            self._logger.log_event("session_cancel_failed", {"error": str(error)})

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
        except (RuntimeError, TimeoutError) as error:
            self._logger.log_event(
                "authenticate_failed", {"method": method_id, "error": str(error)}
            )
            return {}

    def apply_model(self, session: dict[str, Any], preferred_model: str | None) -> None:
        """Aplica o modelo pelo dialeto do runtime, sem derrubar a sessão se falhar."""
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
            self._logger.log_event(
                "set_model_failed",
                {"method": request.method, "model": request.model_id, "error": str(error)},
            )
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
        except (RuntimeError, TimeoutError) as error:
            self._logger.log_event("set_mode_failed", {"mode": mode_id, "error": str(error)})

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

    def bind_run(self, run_id: str) -> None:
        """Liga o runner à run: log e artefatos passam a ser gravados nela."""
        self._bound_run_id = run_id

    @property
    def control(self) -> RunControl:
        """Pausa/parada desta run — o motor consulta nas barreiras."""
        return self._control

    def set_permission_policy(self, policy: PermissionPolicy) -> None:
        self._permission_policy = policy

    def use_agent(self, agent_id: str, policy: PermissionPolicy) -> None:
        self._pulse_agent = agent_id
        self._permission_policy = policy

    def _activate_session(self, session_id: str) -> None:
        self._session_id = str(session_id)
        self.last_session_id = self._session_id
        self._logger.set_session_id(self._session_id)
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

    #: Onde cada runtime põe o caminho do arquivo no `rawInput` do tool-call.
    _PATH_KEYS = ("path", "file_path", "target_file", "filePath", "abs_path")
    #: Tool-calls que produzem artefato. É assim que o Pulse descobre o que o
    #: agente escreveu — não há convenção de pasta nem de extensão.
    _WRITE_KINDS = frozenset({"edit", "write", "create"})

    def _record_run_event(self, params: dict[str, Any]) -> None:
        """Grava no banco do Pulse o que o cockpit está mostrando.

        Ler o log do runtime não serve: só o Cursor tem um, e o Pulse é
        agnóstico ao agente que está rodando.
        """
        if not self._bound_run_id:
            return
        update = params.get("update", params)
        if not isinstance(update, dict):
            return
        kind = str(update.get("sessionUpdate") or "")
        if kind == "agent_message_chunk":
            content = update.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                text = str(content.get("text") or "")
                if text:
                    self._text_buffer.append(text)
            return
        if kind not in {"tool_call", "tool_call_update"}:
            return
        self._flush_text()
        title = str(update.get("title") or update.get("kind") or "tool").strip()
        raw = update.get("rawInput")
        detail = ""
        if isinstance(raw, dict):
            for key in (*self._PATH_KEYS, "command", "pattern", "query"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    detail = value.strip()
                    break
        self._save_event(
            kind="Tool",
            title=title,
            detail=detail,
            tool_id=str(update.get("toolCallId") or ""),
        )
        self._record_artifacts(update)

    def _record_artifacts(self, update: dict[str, Any]) -> None:
        if str(update.get("kind") or "").lower() not in self._WRITE_KINDS:
            return
        for path in self._artifact_paths(update):
            try:
                from pulse.store.runs import record_artifact

                record_artifact(self._bound_run_id, path, step_id=self._phase_id)
            except Exception:
                # Registrar artefato é acessório: nunca derruba o step.
                pass

    def _artifact_paths(self, update: dict[str, Any]) -> list[str]:
        found: list[str] = []
        locations = update.get("locations")
        if isinstance(locations, list):
            for item in locations:
                if isinstance(item, dict):
                    value = item.get("path")
                    if isinstance(value, str) and value.strip():
                        found.append(value.strip())
        raw = update.get("rawInput")
        if isinstance(raw, dict):
            for key in self._PATH_KEYS:
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
                    break
        # `locations` e `rawInput` costumam trazer o mesmo arquivo.
        return list(dict.fromkeys(found))

    def _flush_text(self) -> None:
        text = "".join(self._text_buffer).strip()
        self._text_buffer.clear()
        if text:
            self._save_event(kind="Assistant", title=text[:160], detail=text)

    def _save_event(self, *, kind: str, title: str, detail: str, tool_id: str = "") -> None:
        try:
            from pulse.store.runs import record_event

            record_event(
                self._bound_run_id,
                step_id=self._phase_id,
                acp_session_id=self._session_id or "",
                kind=kind,
                title=title,
                detail=detail,
                tool_id=tool_id,
            )
        except Exception:
            # Log é acessório: falha ao gravar não pode derrubar o step.
            pass

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
