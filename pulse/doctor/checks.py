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
    """Checks de ambiente do runtime pedido."""
    return [_as_result(check) for check in get_runtime(runtime).checks()]


def check_runtime_ready(runtime: str) -> CheckResult | None:
    """Primeiro check bloqueante do runtime, ou None quando está pronto.

    Só `fail` bloqueia: um `warn` (ex.: `claude auth status` inconclusivo) não
    deve impedir o workflow de começar.
    """
    for check in run_agent_checks(runtime):
        if check.status == "fail":
            return check
    return None


def active_runtime_id() -> str:
    """Runtime que o Pulse usaria agora, segundo a config resolvida."""
    from pulse.config.resolved import resolve_config

    return get_runtime(resolve_config().agent_name).id


def other_runtimes_summary(active: str) -> list[CheckResult]:
    """Disponibilidade dos demais runtimes, como aviso — não reprova o doctor."""
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
                    message=f"Runtime `{runtime.id}` indisponível",
                    detail=failures[0].detail or failures[0].message,
                )
            )
        else:
            results.append(
                CheckResult(
                    name=f"Runtime {runtime.id}",
                    status="ok",
                    message=f"Runtime `{runtime.id}` pronto",
                    detail="disponível para workflows",
                )
            )
    return results


def run_doctor_checks(active: str | None = None) -> list[CheckResult]:
    """Checks do runtime ativo + resumo dos demais.

    Só o runtime ativo reprova: uma máquina que tem só o Claude não deve falhar
    o doctor por não ter o Cursor instalado.
    """
    runtime_id = active or active_runtime_id()
    return [*run_environment_checks([runtime_id]), *other_runtimes_summary(runtime_id)]


def check_git() -> CheckResult:
    """Git no PATH. Nunca `fail`: worktree é opcional.

    Quem não liga a chave de isolamento roda perfeitamente sem git — reprovar o
    doctor por isso seria cobrar uma dependência que o Pulse não tem.
    """
    from pulse import vcs

    if vcs.git_available():
        return CheckResult(
            name="Git",
            status="ok",
            message="git disponível",
            detail="worktree por run pode ser ligado nas configurações do projeto",
        )
    return CheckResult(
        name="Git",
        status="warn",
        message="git não encontrado no PATH",
        detail="sem ele as runs rodam sempre na árvore de trabalho do projeto",
    )


def run_environment_checks(runtimes: list[str] | None = None) -> list[CheckResult]:
    """Checks do(s) runtime(s) pedido(s); sem argumento, todos os registrados."""
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
