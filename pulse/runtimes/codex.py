from __future__ import annotations

import os
from collections.abc import Sequence

from pulse.runtimes.base import AgentRuntime, RuntimeCheck

CODEX_ACP_PACKAGE = "@agentclientprotocol/codex-acp"
CODEX_ACP_VERSION = "2.1.1"
CODEX_API_KEY_ENV_VARS = ("CODEX_API_KEY", "OPENAI_API_KEY")


class CodexRuntime(AgentRuntime):
    """OpenAI Codex CLI, speaking ACP through the official npm adapter."""

    id = "codex"
    label = "OpenAI Codex"
    binary = "codex"
    acp_override = ("npx", "-y", f"{CODEX_ACP_PACKAGE}@{CODEX_ACP_VERSION}")
    default_models = ("default",)
    required_binaries = ("npx",)
    auth_env_var = "CODEX_API_KEY"
    auth_method_id = "chat-gpt"
    auth_method_label = "codex_login"
    install_hint = "Install the Codex CLI and Node.js/npm for the ACP adapter."
    login_command = ("codex", "login")
    interview_modes = ("read-only", "workspace-write", "agent")
    execute_modes = ("workspace-write", "agent", "read-only")

    def check_auth(self) -> RuntimeCheck:
        if any(os.environ.get(name, "").strip() for name in CODEX_API_KEY_ENV_VARS):
            return RuntimeCheck(
                name=self.auth_check_name,
                status="ok",
                message="Codex API key is set in the environment",
                detail="api_key",
            )
        return self._check_auth_cli()

    def auth_method(self, advertised: Sequence[str]) -> str | None:
        if any(os.environ.get(name, "").strip() for name in CODEX_API_KEY_ENV_VARS):
            if "api-key" in advertised:
                return "api-key"
        return super().auth_method(advertised)

    def _check_auth_cli(self) -> RuntimeCheck:
        binary = self.find_binary() or self.binary
        completed = self.run_cli([binary, "login", "status"], timeout=20.0)
        if completed is None:
            return RuntimeCheck(
                name=self.auth_check_name,
                status="warn",
                message="Could not confirm the Codex session",
                detail="Run `codex login status` or `codex login` to check authentication",
            )
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        lowered = output.lower()
        if "not logged in" in lowered or "not authenticated" in lowered:
            return RuntimeCheck(
                name=self.auth_check_name,
                status="fail",
                message="Not authenticated in Codex",
                detail=self.auth_hint,
            )
        if "logged in" in lowered or "authenticated" in lowered:
            return RuntimeCheck(
                name=self.auth_check_name,
                status="ok",
                message="Codex session active",
                detail="codex_login",
            )
        return RuntimeCheck(
            name=self.auth_check_name,
            status="warn",
            message="Could not confirm the Codex session",
            detail="Run `codex login status` or `codex login` to check authentication",
        )

    @property
    def auth_hint(self) -> str:
        return "Run `codex login` or set CODEX_API_KEY / OPENAI_API_KEY"
