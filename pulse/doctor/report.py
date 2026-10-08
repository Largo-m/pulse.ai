from __future__ import annotations

from pulse.acp.client import probe_acp_connection
from pulse.config import (
    global_config_exists,
    load_global_config,
    load_project_config,
)
from pulse.config.resolved import resolve_config
from pulse.doctor.checks import CheckResult, run_doctor_checks
from pulse.runtimes import get_runtime
from pulse.store.paths import GLOBAL_DB_FILE, safe_cwd


def _status_icon(status: str) -> str:
    if status == "ok":
        return "✓"
    if status == "warn":
        return "!"
    return "✗"


def print_doctor_report(
    checks: list[CheckResult],
    *,
    acp_probe_message: str | None = None,
) -> None:
    for check in checks:
        detail = f" — {check.detail}" if check.detail else ""
        print(f"{_status_icon(check.status)} {check.message}{detail}")
    if acp_probe_message:
        print(f"  ACP test: {acp_probe_message}")


def run_doctor(*, test_acp: bool = False) -> int:
    resolved = resolve_config()
    active = resolved.runtime.id
    checks = run_doctor_checks(active)
    acp_message: str | None = None

    if global_config_exists():
        config = load_global_config()
        if config:
            global_detail = f"model={config.model}, permissions={config.permission_policy}"
            if config.agents:
                global_detail += f", agents={len(config.agents)}"
            if config.workflows:
                global_detail += f", workflows={len(config.workflows)}"
            checks.append(
                CheckResult(
                    name="Global config",
                    status="ok",
                    message=f"Config in {GLOBAL_DB_FILE}",
                    detail=global_detail,
                )
            )

    project = load_project_config()
    if project is not None:
        overrides = []
        if project.default_agent:
            overrides.append(f"agent={project.default_agent}")
        if project.model:
            overrides.append(f"model={project.model}")
        if project.permission_policy:
            overrides.append(f"permissions={project.permission_policy}")
        if project.workspace:
            overrides.append(f"workspace={project.workspace}")
        if project.workflows:
            overrides.append(f"workflows={len(project.workflows)}")
        checks.append(
            CheckResult(
                name="Project config",
                status="ok",
                message=f"Config in {project.source_file}",
                detail=", ".join(overrides) or "no overrides",
            )
        )

    if test_acp:
        if not any(check.status == "fail" for check in checks):
            print(f"Testing the ACP connection with `{active}`…")
            probe = probe_acp_connection(
                command=list(resolved.acp_command),
                cwd=str(safe_cwd()),
            )
            acp_message = probe.message if probe.success else probe.error or probe.message
            checks.append(
                CheckResult(
                    name="ACP",
                    status="ok" if probe.success else "fail",
                    message=probe.message,
                    detail=probe.response_text[:120] if probe.response_text else None,
                )
            )
        else:
            checks.append(
                CheckResult(
                    name="ACP",
                    status="warn",
                    message="ACP test skipped",
                    detail=f"Fix the `{active}` runtime and its authentication first",
                )
            )

    print_doctor_report(checks, acp_probe_message=acp_message)
    failed = any(check.status == "fail" for check in checks)
    return 1 if failed else 0


def run_agent_login(runtime: str = "cursor") -> int:
    """Start the runtime login flow (`agent login`, `claude /login`, ...)."""
    return get_runtime(runtime).login()
