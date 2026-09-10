from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str
    detail: str | None = None


def find_agent_binary() -> str | None:
    return shutil.which("agent")


def check_agent_in_path() -> CheckResult:
    binary = find_agent_binary()
    if binary is None:
        return CheckResult(
            name="Agent CLI",
            status="fail",
            message="Binário `agent` não encontrado no PATH",
            detail="Instale o Cursor CLI: https://cursor.com/docs/cli",
        )

    try:
        completed = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        version = (completed.stdout or completed.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as error:
        return CheckResult(
            name="Agent CLI",
            status="fail",
            message=f"Falha ao executar `agent`: {error}",
        )

    return CheckResult(
        name="Agent CLI",
        status="ok",
        message=f"Encontrado em {binary}",
        detail=version or None,
    )


def _parse_logged_in(output: str) -> bool:
    lowered = output.lower()
    if "not logged in" in lowered or "não está logado" in lowered:
        return False
    return "logged in" in lowered or "logado" in lowered


def check_auth() -> CheckResult:
    if os.environ.get("CURSOR_API_KEY", "").strip():
        return CheckResult(
            name="Autenticação",
            status="ok",
            message="CURSOR_API_KEY definida no ambiente",
            detail="api_key",
        )

    binary = find_agent_binary()
    if binary is None:
        return CheckResult(
            name="Autenticação",
            status="fail",
            message="Sem CURSOR_API_KEY e `agent` indisponível",
            detail="Execute `agent login` ou exporte CURSOR_API_KEY",
        )

    for command in (["status"], ["whoami"]):
        try:
            completed = subprocess.run(
                [binary, *command],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue

        output = f"{completed.stdout}\n{completed.stderr}".strip()
        if _parse_logged_in(output):
            email_match = re.search(r"as\s+(\S+@\S+)", output, re.IGNORECASE)
            detail = email_match.group(1) if email_match else "cursor_login"
            return CheckResult(
                name="Autenticação",
                status="ok",
                message="Sessão Cursor ativa (`agent login`)",
                detail=detail,
            )

    return CheckResult(
        name="Autenticação",
        status="fail",
        message="Não autenticado",
        detail="Execute `agent login` ou exporte CURSOR_API_KEY",
    )


def run_environment_checks() -> list[CheckResult]:
    return [check_agent_in_path(), check_auth()]
