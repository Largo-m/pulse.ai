from __future__ import annotations

import re

from pulse.runtimes.base import AgentRuntime, RuntimeCheck


def _parse_logged_in(output: str) -> bool:
    lowered = output.lower()
    if "not logged in" in lowered or "não está logado" in lowered:
        return False
    return "logged in" in lowered or "logado" in lowered


class CursorRuntime(AgentRuntime):
    """Cursor Agent, speaking ACP natively via `agent acp`."""

    id = "cursor"
    label = "Cursor"
    binary = "agent"
    acp_args = ("acp",)
    default_models = ("Auto", "gpt-5.5", "composer-2.5")
    auth_env_var = "CURSOR_API_KEY"
    auth_method_id = "cursor_login"
    auth_method_label = "cursor_login"
    install_hint = "Instale o Cursor CLI: https://cursor.com/docs/cli"
    login_command = ("agent", "login")
    login_label = "Executar `agent login`"
    interview_modes = ("agent", "plan", "default")
    execute_modes = ("agent", "default", "acceptEdits")

    def _check_auth_cli(self) -> RuntimeCheck:
        binary = self.find_binary() or self.binary
        for args in (["status"], ["whoami"]):
            completed = self.run_cli([binary, *args])
            if completed is None:
                continue
            output = f"{completed.stdout}\n{completed.stderr}".strip()
            if _parse_logged_in(output):
                email = re.search(r"as\s+(\S+@\S+)", output, re.IGNORECASE)
                return RuntimeCheck(
                    name=self.auth_check_name,
                    status="ok",
                    message="Sessão Cursor ativa (`agent login`)",
                    detail=email.group(1) if email else "cursor_login",
                )
        return RuntimeCheck(
            name=self.auth_check_name,
            status="fail",
            message="Não autenticado",
            detail=self.auth_hint,
        )
