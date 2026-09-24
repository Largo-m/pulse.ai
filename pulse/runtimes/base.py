from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeCheck:
    """Resultado de uma verificação de ambiente de um runtime."""

    name: str
    status: str  # "ok" | "warn" | "fail"
    message: str
    detail: str | None = None


@dataclass(frozen=True)
class ModelRequest:
    """Chamada JSON-RPC que aplica um modelo na sessão.

    Nem todo agente ACP implementa `session/set_model`: o Claude expõe o modelo
    como config option. Cada runtime devolve a chamada certa.
    """

    method: str
    params: dict[str, Any]
    model_id: str


def run_cli(command: list[str], *, timeout: float = 15.0) -> subprocess.CompletedProcess[str] | None:
    """Executa um CLI capturando a saída; None quando o binário falha ou trava."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


class AgentRuntime:
    """Como um agente concreto fala ACP.

    Os defaults desta classe seguem o protocolo ACP puro e são derivados do que o
    agente anuncia em `initialize`/`session/new`. Cada runtime sobrescreve apenas
    o que diverge — binário, autenticação e preferências de modo.
    """

    id: str = "generic"
    label: str = "Agente ACP"
    binary: str = ""
    acp_args: tuple[str, ...] = ("acp",)
    #: Comando completo; quando vazio, é `[binary, *acp_args]`.
    acp_override: tuple[str, ...] = ()
    default_models: tuple[str, ...] = ()
    #: Binários extras que o runtime precisa além do principal (ex.: `npx`).
    required_binaries: tuple[str, ...] = ()
    auth_env_var: str = ""
    #: `methodId` do `authenticate` do ACP; None quando o agente não autentica por ali.
    auth_method_id: str | None = None
    auth_method_label: str = ""
    install_hint: str = ""
    login_command: tuple[str, ...] = ()
    login_label: str = ""
    #: Ordem de preferência de modo na fase de análise e na de execução.
    interview_modes: tuple[str, ...] = ("agent", "plan", "default")
    execute_modes: tuple[str, ...] = ("agent", "default", "acceptEdits")

    # ------------------------------------------------------------------ ambiente

    @property
    def acp_command(self) -> list[str]:
        if self.acp_override:
            return list(self.acp_override)
        return [self.binary, *self.acp_args]

    def find_binary(self) -> str | None:
        return shutil.which(self.binary)

    def run_cli(
        self, command: list[str], *, timeout: float = 15.0
    ) -> subprocess.CompletedProcess[str] | None:
        """Ponto único de execução de CLI do runtime (sobrescrevível e testável)."""
        return run_cli(command, timeout=timeout)

    def is_available(self) -> bool:
        """Binário principal e dependências presentes no PATH.

        Checagem barata (só PATH, sem subprocesso): serve para decidir fallback
        de runtime na resolução de config, que roda a cada workflow.
        """
        if self.find_binary() is None:
            return False
        return all(shutil.which(dependency) for dependency in self.required_binaries)

    def check_binary(self) -> RuntimeCheck:
        name = f"{self.label} CLI"
        found = self.find_binary()
        if found is None:
            return RuntimeCheck(
                name=name,
                status="fail",
                message=f"Binário `{self.binary}` não encontrado no PATH",
                detail=self.install_hint or None,
            )
        completed = self.run_cli([found, "--version"])
        if completed is None:
            return RuntimeCheck(
                name=name,
                status="fail",
                message=f"Falha ao executar `{self.binary} --version`",
                detail=self.install_hint or None,
            )
        version = (completed.stdout or completed.stderr).strip()
        return RuntimeCheck(
            name=name,
            status="ok",
            message=f"Encontrado em {found}",
            detail=version or None,
        )

    def check_dependencies(self) -> list[RuntimeCheck]:
        results: list[RuntimeCheck] = []
        for dependency in self.required_binaries:
            found = shutil.which(dependency)
            if found is None:
                results.append(
                    RuntimeCheck(
                        name=dependency,
                        status="fail",
                        message=f"`{dependency}` não encontrado no PATH",
                        detail=self.install_hint or None,
                    )
                )
            else:
                results.append(
                    RuntimeCheck(name=dependency, status="ok", message=f"Encontrado em {found}")
                )
        return results

    @property
    def auth_check_name(self) -> str:
        return f"Autenticação {self.label}"

    def check_auth(self) -> RuntimeCheck:
        if self.auth_env_var and os.environ.get(self.auth_env_var, "").strip():
            return RuntimeCheck(
                name=self.auth_check_name,
                status="ok",
                message=f"{self.auth_env_var} definida no ambiente",
                detail="api_key",
            )
        if self.find_binary() is None:
            return RuntimeCheck(
                name=self.auth_check_name,
                status="fail",
                message=f"Sem {self.auth_env_var} e `{self.binary}` indisponível",
                detail=self.auth_hint,
            )
        return self._check_auth_cli()

    def _check_auth_cli(self) -> RuntimeCheck:
        return RuntimeCheck(
            name=self.auth_check_name,
            status="warn",
            message="Autenticação não verificável",
            detail=self.auth_hint,
        )

    @property
    def auth_hint(self) -> str:
        parts = []
        if self.login_command:
            parts.append(f"Execute `{' '.join(self.login_command)}`")
        if self.auth_env_var:
            parts.append(f"ou exporte {self.auth_env_var}")
        return " ".join(parts)

    def checks(self) -> list[RuntimeCheck]:
        results = [self.check_binary(), *self.check_dependencies()]
        results.append(self.check_auth())
        return results

    def login(self) -> int:
        if not self.login_command:
            return 1
        try:
            return subprocess.run(list(self.login_command), check=False).returncode
        except OSError:
            return 1

    # -------------------------------------------------------------------- sessão

    def auth_method(self, advertised: Sequence[str]) -> str | None:
        """`methodId` para o `authenticate`, ou None para pular a chamada.

        Agentes que já vêm autenticados do próprio CLI anunciam `authMethods: []`;
        mandar `authenticate` neles só gera erro.
        """
        if not advertised:
            return None
        if self.auth_method_id and self.auth_method_id in advertised:
            return self.auth_method_id
        return str(advertised[0])

    def available_modes(self, session: dict[str, Any]) -> list[str]:
        modes = session.get("modes")
        if not isinstance(modes, dict):
            return []
        available = modes.get("availableModes")
        if not isinstance(available, list):
            return []
        return [str(item.get("id")) for item in available if isinstance(item, dict) and item.get("id")]

    def resolve_mode(self, session: dict[str, Any], *, execute: bool) -> str | None:
        """Primeiro modo preferido que o agente realmente suporta."""
        preferences = self.execute_modes if execute else self.interview_modes
        ids = self.available_modes(session)
        if not ids:
            # Agente não anuncia modos: mantém o comportamento histórico.
            return preferences[0] if preferences else None
        for preference in preferences:
            if preference in ids:
                return preference
        modes = session.get("modes")
        current = modes.get("currentModeId") if isinstance(modes, dict) else None
        return str(current) if current else None

    def model_request(
        self,
        session: dict[str, Any],
        preferred_model: str | None,
        *,
        session_id: str,
    ) -> ModelRequest | None:
        from pulse.acp.models import resolve_model_id

        model_id = resolve_model_id(session, preferred_model)
        if not model_id:
            return None
        return ModelRequest(
            method="session/set_model",
            params={"sessionId": session_id, "modelId": model_id},
            model_id=model_id,
        )
