from __future__ import annotations

import json
from typing import Any

from pulse.runtimes.base import AgentRuntime, ModelRequest, RuntimeCheck

CLAUDE_ACP_PACKAGE = "@agentclientprotocol/claude-agent-acp"
CLAUDE_ACP_VERSION = "0.86.0"

MODEL_CONFIG_ID = "model"


class ClaudeRuntime(AgentRuntime):
    """Claude Code, speaking ACP through the npm adapter that reuses the `claude` CLI login.

    Differences from Cursor handled here:
    - modes are `default`/`acceptEdits`/`plan`/`auto`/`bypassPermissions`, not `agent`;
    - the model is set via `session/set_config_option`, not `session/set_model`;
    - `authMethods` is empty: the adapter is already authenticated by the CLI.
    """

    id = "claude"
    label = "Claude Code"
    binary = "claude"
    acp_override = ("npx", "-y", f"{CLAUDE_ACP_PACKAGE}@{CLAUDE_ACP_VERSION}")
    default_models = ("default", "opus[1m]", "claude-fable-5-1", "sonnet", "haiku")
    required_binaries = ("npx",)
    auth_env_var = "ANTHROPIC_API_KEY"
    auth_method_id = None
    auth_method_label = "claude_login"
    install_hint = "Install Claude Code (https://claude.com/claude-code) and Node.js 18+ (`npx`)."
    login_command = ("claude", "/login")
    interview_modes = ("default", "acceptEdits", "agent")
    execute_modes = ("default", "acceptEdits", "agent")

    def _check_auth_cli(self) -> RuntimeCheck:
        binary = self.find_binary() or self.binary
        completed = self.run_cli([binary, "auth", "status"], timeout=20.0)
        if completed is None:
            return RuntimeCheck(
                name=self.auth_check_name,
                status="warn",
                message="Could not confirm the Claude session",
                detail="`claude auth status` did not answer; run `claude` and check the login",
            )
        try:
            payload = json.loads((completed.stdout or "").strip())
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and "loggedIn" in payload:
            if payload.get("loggedIn"):
                return RuntimeCheck(
                    name=self.auth_check_name,
                    status="ok",
                    message="Claude session active",
                    detail=str(payload.get("authMethod") or "claude_login"),
                )
            return RuntimeCheck(
                name=self.auth_check_name,
                status="fail",
                message="Not authenticated in Claude Code",
                detail=self.auth_hint,
            )
        return RuntimeCheck(
            name=self.auth_check_name,
            status="warn",
            message="Could not confirm the Claude session",
            detail="`claude auth status` did not answer; run `claude` and check the login",
        )

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
        option = model_config_option(session)
        if option is None:
            return super().model_request(session, preferred_model, session_id=session_id)
        return ModelRequest(
            method="session/set_config_option",
            params={
                "sessionId": session_id,
                "configId": str(option.get("id", MODEL_CONFIG_ID)),
                "value": model_id,
            },
            model_id=model_id,
        )


def model_config_option(session: dict[str, Any]) -> dict[str, Any] | None:
    """Config option that carries the model list."""
    options = session.get("configOptions")
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("id") == MODEL_CONFIG_ID or option.get("category") == MODEL_CONFIG_ID:
            return option
    return None
