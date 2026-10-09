from __future__ import annotations

from dataclasses import dataclass

from pulse.runtimes import RuntimeCheck, all_runtimes, get_runtime


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    message: str
    detail: str | None = None


def _as_result(check: RuntimeCheck) -> CheckResult:
    return CheckResult(
        name=check.name,
        status=check.status,
        message=check.message,
        detail=check.detail,
    )


def check_agent_in_path(runtime: str = "cursor") -> CheckResult:
    return _as_result(get_runtime(runtime).check_binary())


def check_auth(runtime: str = "cursor") -> CheckResult:
    return _as_result(get_runtime(runtime).check_auth())


def run_agent_checks(runtime: str) -> list[CheckResult]:
    """Environment checks for the given runtime."""
    return [_as_result(check) for check in get_runtime(runtime).checks()]


def check_runtime_ready(runtime: str) -> CheckResult | None:
    """First blocking check of the runtime, or None when it is ready.

    Only `fail` blocks: a `warn` (e.g. inconclusive `claude auth status`) must
    not prevent the workflow from starting.
    """
    for check in run_agent_checks(runtime):
        if check.status == "fail":
            return check
    return None


def active_runtime_id() -> str:
    """Runtime Pulse would use now, according to the resolved config."""
    from pulse.config.resolved import resolve_config

    return resolve_config().runtime.id


def other_runtimes_summary(active: str) -> list[CheckResult]:
    """Availability of the other runtimes as warnings; never fails the doctor."""
    results: list[CheckResult] = []
    for runtime in all_runtimes():
        if runtime.id == active:
            continue
        failures = [check for check in run_agent_checks(runtime.id) if check.status == "fail"]
        if failures:
            results.append(
                CheckResult(
                    name=f"Runtime {runtime.id}",
                    status="warn",
                    message=f"Runtime `{runtime.id}` unavailable",
                    detail=failures[0].detail or failures[0].message,
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"Runtime {runtime.id}",
                    status="ok",
                    message=f"Runtime `{runtime.id}` ready",
                    detail="available to workflows",
                )
            )
    return results


def run_doctor_checks(active: str | None = None) -> list[CheckResult]:
    """Checks for the active runtime plus a summary of the others.

    Only the active runtime can fail, so a machine with only Claude does not
    fail the doctor for lacking Cursor.
    """
    runtime_id = active or active_runtime_id()
    return [*run_environment_checks([runtime_id]), *other_runtimes_summary(runtime_id)]


def check_git() -> CheckResult:
    """Git on PATH. Never `fail`: per-run worktrees are optional."""
    from pulse import vcs

    if vcs.git_available():
        return CheckResult(
            name="Git",
            status="ok",
            message="git available",
            detail="a worktree per run can be turned on in the project settings",
        )
    return CheckResult(
        name="Git",
        status="warn",
        message="git not found on PATH",
        detail="without it, runs always work in the project's working tree",
    )


def run_environment_checks(runtimes: list[str] | None = None) -> list[CheckResult]:
    """Checks for the given runtimes; all registered ones when omitted."""
    names = runtimes if runtimes is not None else [runtime.id for runtime in all_runtimes()]
    results: list[CheckResult] = []
    seen: set[str] = set()
    for name in names:
        for check in run_agent_checks(name):
            if check.name in seen:
                continue
            seen.add(check.name)
            results.append(check)
    results.append(check_git())
    return results
