from __future__ import annotations

import json
from typing import Any

from pulse.runtimes.base import AgentRuntime, ModelRequest, RuntimeCheck

#: O Claude Code não fala ACP nativamente; o adapter oficial vem por npm.
CLAUDE_ACP_PACKAGE = "@agentclientprotocol/claude-agent-acp"

MODEL_CONFIG_ID = "model"


class ClaudeRuntime(AgentRuntime):
    """Claude Code — fala ACP pelo adapter npm, que herda o login do `claude` CLI.

    Três divergências em relação ao Cursor, tratadas aqui:

    - os modos são `default`/`acceptEdits`/`plan`/`auto`/`bypassPermissions`,
      não `agent`;
    - o modelo se troca por `session/set_config_option`, não `session/set_model`;
    - `authMethods` vem vazio: o adapter já está autenticado pelo CLI.
    """

    id = "claude"
    label = "Claude Code"
    binary = "claude"
    acp_override = ("npx", "-y", CLAUDE_ACP_PACKAGE)
    default_models = ("default", "opus[1m]", "claude-fable-5-1", "sonnet", "haiku")
    required_binaries = ("npx",)
    auth_env_var = "ANTHROPIC_API_KEY"
    auth_method_id = None
    auth_method_label = "claude_login"
    install_hint = (
        "Instale o Claude Code (https://claude.com/claude-code) e o Node.js 18+ (`npx`)."
    )
    login_command = ("claude", "/login")
    login_label = "Executar `claude /login`"
    # NÃO usar o modo `plan` aqui: as fases de "planejamento" do Pulse
    # (prd/techspec/tasks) são justamente as que escrevem os artefatos. Em
    # `plan` o Claude não escreve o arquivo pedido — ele grava um plano em
    # ~/.claude/plans e espera aprovação, e o artefato nunca aparece na sessão.
    # Quem limita escrita é a permission_policy do Pulse, como no Cursor.
    interview_modes = ("default", "acceptEdits", "agent")
    execute_modes = ("default", "acceptEdits", "agent")

    def _check_auth_cli(self) -> RuntimeCheck:
        binary = self.find_binary() or self.binary
        completed = self.run_cli([binary, "auth", "status"], timeout=20.0)
        if completed is None:
            return RuntimeCheck(
                name=self.auth_check_name,
                status="warn",
                message="Não foi possível confirmar a sessão Claude",
                detail="`claude auth status` não respondeu; rode `claude` e confira o login",
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
                    message="Sessão Claude ativa",
                    detail=str(payload.get("authMethod") or "claude_login"),
                )
            return RuntimeCheck(
                name=self.auth_check_name,
                status="fail",
                message="Não autenticado no Claude Code",
                detail=self.auth_hint,
            )
        return RuntimeCheck(
            name=self.auth_check_name,
            status="warn",
            message="Não foi possível confirmar a sessão Claude",
            detail="`claude auth status` não respondeu; rode `claude` e confira o login",
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
            # Adapter novo que já implemente `session/set_model`.
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
    """Config option que carrega a lista de modelos."""
    options = session.get("configOptions")
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("id") == MODEL_CONFIG_ID or option.get("category") == MODEL_CONFIG_ID:
            return option
    return None
