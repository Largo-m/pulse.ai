"""The daemon as the screens see it: typed reads and writes over `/api/*`.

The TUI is a thin client (AGENTS.md §2.1): it never opens SQLite, resolves
config or runs a doctor check itself. Each call parses the response at this
boundary into the values the screens use. A daemon that cannot be reached
raises `EngineUnavailable` and one that answers with an error `EngineRefused`;
a screen catches their base `EngineError` and shows it instead of crashing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar

import httpx

from pulse.client.engine_client import SCREEN_TIMEOUT_SECONDS, EngineClient
from pulse.history.models import HistoryItem
from pulse.history.run_log import RunLog
from pulse.tui import strings

T = TypeVar("T")
AgentField = Literal["runtime", "model", "permission_policy"]
NOT_FOUND = 404
CONFLICT = 409
# Doctor checks, the ACP probe and the model list spawn agents; removing a worktree runs git.
PROBE_TIMEOUT_SECONDS = 30.0


class EngineError(RuntimeError):
    """The daemon did not do what the screen asked; `describe` says why, on screen."""

    template = strings.ENGINE_UNAVAILABLE
    headline = strings.ENGINE_UNAVAILABLE_HEADLINE

    def describe(self) -> str:
        return self.template.format(error=self)


class EngineUnavailable(EngineError):
    """The daemon could not be started or did not answer."""


class EngineRefused(EngineError):
    """The daemon answered with an error; its `detail` is the reason."""

    template = strings.ENGINE_REFUSED
    headline = strings.ENGINE_REFUSED_HEADLINE


class RunInUse(Exception):
    """The daemon still executes the run, so its agent works in its worktree."""


@dataclass(frozen=True)
class SetupState:
    configured: bool
    onboarded: bool
    ready: bool
    workspace_dir: str
    database: str


@dataclass(frozen=True)
class RuntimeInfo:
    id: str
    label: str
    binary: str
    install_hint: str
    login_command: tuple[str, ...]
    auth_env_var: str
    auth_method_label: str


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    message: str
    detail: str


@dataclass(frozen=True)
class Fields:
    runtime: str
    model: str
    permission_policy: str


@dataclass(frozen=True)
class AgentRow:
    id: str
    label: str
    fields: Fields


@dataclass(frozen=True)
class ProjectSettings:
    is_repo: bool
    use_worktree: bool
    atomic_commits: bool
    auto_pull_request: bool
    defaults: Fields
    agents: tuple[AgentRow, ...]
    runtimes: tuple[tuple[str, str], ...]
    permission_policies: tuple[str, ...]

    def agent(self, agent_id: str) -> AgentRow | None:
        return next((agent for agent in self.agents if agent.id == agent_id), None)


@dataclass(frozen=True)
class WorkspaceFiles:
    tracked: tuple[str, ...] = ()
    untracked: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowShape:
    """A workflow as the sidebar draws it before the run reports its own steps."""

    id: str
    label: str
    description: str = ""
    default_prompt: str = ""
    is_default: bool = False
    steps: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class WorktreeState:
    path: str
    exists: bool
    dirty: bool
    active: bool


def _call(request: Callable[[EngineClient], T], *, timeout: float = SCREEN_TIMEOUT_SECONDS) -> T:
    # No `ensure_daemon`: screens call this on the event loop, and starting a
    # daemon polls for up to 20s. The CLI starts it before the first screen.
    client = EngineClient(timeout=timeout)
    try:
        return request(client)
    except httpx.HTTPStatusError as error:
        raise EngineRefused(_detail(error.response)) from error
    except httpx.HTTPError as error:
        raise EngineUnavailable(str(error)) from error
    finally:
        client.close()


def start_daemon() -> None:
    """Start the daemon and wait until it answers.

    Only from a thread worker: it polls for up to 20s.
    """
    client = EngineClient()
    try:
        client.ensure_daemon()
    except (RuntimeError, OSError) as error:
        raise EngineUnavailable(str(error)) from error
    finally:
        client.close()


def optional(read: Callable[[], T | None]) -> T | None:
    """A read that only enriches a screen: without an answer the screen draws without it."""
    try:
        return read()
    except EngineError:
        return None


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    detail = body.get("detail") if isinstance(body, dict) else None
    return str(detail) if detail else f"HTTP {response.status_code}"


def _probe(request: Callable[[EngineClient], T]) -> T:
    return _call(request, timeout=PROBE_TIMEOUT_SECONDS)


def _found(
    request: Callable[[EngineClient], T], *, timeout: float = SCREEN_TIMEOUT_SECONDS
) -> T | None:
    """`None` for a 404: an unknown id does not exist, it is not a failure."""

    def guarded(client: EngineClient) -> T | None:
        try:
            return request(client)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == NOT_FOUND:
                return None
            raise

    return _call(guarded, timeout=timeout)


def _fields(data: Mapping[str, Any]) -> Fields:
    return Fields(
        runtime=str(data.get("runtime") or ""),
        model=str(data.get("model") or ""),
        permission_policy=str(data.get("permission_policy") or ""),
    )


def _strings(values: object) -> tuple[str, ...]:
    return tuple(str(value) for value in values or ()) if isinstance(values, list) else ()


# Setup and settings.


def setup_state(workspace: Path) -> SetupState:
    data = _call(lambda client: client.get("/api/setup", params={"workspace": str(workspace)}))
    return SetupState(
        configured=bool(data.get("configured")),
        onboarded=bool(data.get("onboarded")),
        ready=bool(data.get("ready")),
        workspace_dir=str(data.get("workspace_dir") or ""),
        database=str(data.get("database") or ""),
    )


def runtimes() -> tuple[str, tuple[RuntimeInfo, ...]]:
    """The default runtime id and every registered runtime."""
    data = _call(lambda client: client.get("/api/runtimes"))
    return str(data.get("default") or ""), tuple(
        RuntimeInfo(
            id=str(item["id"]),
            label=str(item.get("label") or item["id"]),
            binary=str(item.get("binary") or ""),
            install_hint=str(item.get("install_hint") or ""),
            login_command=_strings(item.get("login_command")),
            auth_env_var=str(item.get("auth_env_var") or ""),
            auth_method_label=str(item.get("auth_method_label") or ""),
        )
        for item in data.get("runtimes") or ()
    )


def _checks(data: Mapping[str, Any]) -> list[Check]:
    return [
        Check(
            name=str(item.get("name") or ""),
            status=str(item.get("status") or ""),
            message=str(item.get("message") or ""),
            detail=str(item.get("detail") or ""),
        )
        for item in data.get("checks") or ()
    ]


def runtime_checks(runtime_id: str) -> list[Check]:
    return _checks(_probe(lambda client: client.get(f"/api/runtimes/{runtime_id}/checks")))


def doctor_checks() -> list[Check]:
    return _checks(_probe(lambda client: client.doctor()))


def models(workspace: Path, runtime_id: str) -> list[str]:
    data = _probe(
        lambda client: client.get(
            "/api/models", params={"workspace": str(workspace), "runtime": runtime_id}
        )
    )
    return list(_strings(data.get("models")))


def acp_probe(workspace: Path, runtime_id: str) -> dict[str, Any]:
    return _probe(lambda client: client.acp_probe(workspace=workspace, runtime=runtime_id))


def complete_onboarding(
    *,
    runtime_id: str,
    workspace: Path,
    model: str,
    permission_policy: str,
    auth_method: str,
    acp_test_passed: bool,
) -> str:
    body = {
        "runtime": runtime_id,
        "workspace": str(workspace),
        "model": model,
        "permission_policy": permission_policy,
        "auth_method": auth_method,
        "acp_test_passed": acp_test_passed,
    }
    return str(_call(lambda client: client.post("/api/setup/onboarding", body)).get("path") or "")


def open_project(workspace: Path) -> None:
    _call(lambda client: client.post("/api/config/project", {"workspace": str(workspace)}))


def config(workspace: Path) -> dict[str, Any]:
    return _call(lambda client: client.get("/api/config", params={"workspace": str(workspace)}))


def project_settings(workspace: Path) -> ProjectSettings:
    data = _call(lambda client: client.get("/api/settings", params={"workspace": str(workspace)}))
    return ProjectSettings(
        is_repo=bool(data.get("is_repo")),
        use_worktree=bool(data.get("use_worktree")),
        atomic_commits=bool(data.get("atomic_commits")),
        auto_pull_request=bool(data.get("auto_pull_request")),
        defaults=_fields(data.get("defaults") or {}),
        agents=tuple(
            AgentRow(id=str(item["id"]), label=str(item.get("label") or ""), fields=_fields(item))
            for item in data.get("agents") or ()
        ),
        runtimes=tuple(
            (str(item["id"]), str(item.get("binary") or "")) for item in data.get("runtimes") or ()
        ),
        permission_policies=_strings(data.get("permission_policies")),
    )


def save_default(workspace: Path, field: AgentField, value: str) -> None:
    body = {"workspace": str(workspace), "field": field, "value": value}
    _call(lambda client: client.patch("/api/settings/defaults", body))


def save_agent_field(workspace: Path, agent_id: str, field: AgentField, value: str) -> None:
    body = {"workspace": str(workspace), "field": field, "value": value}
    _call(lambda client: client.patch(f"/api/settings/agents/{agent_id}", body))


def set_worktree(workspace: Path, *, enabled: bool) -> None:
    _put_flag(workspace, "/api/settings/worktree", enabled=enabled)


def set_atomic_commits(workspace: Path, *, enabled: bool) -> None:
    _put_flag(workspace, "/api/settings/atomic-commits", enabled=enabled)


def set_pull_request(workspace: Path, *, enabled: bool) -> None:
    _put_flag(workspace, "/api/settings/pull-request", enabled=enabled)


def branch_check(workspace: Path, name: str) -> tuple[bool, bool]:
    data = _call(
        lambda client: client.get(
            "/api/git/branch", params={"workspace": str(workspace), "name": name}
        )
    )
    return bool(data.get("valid")), bool(data.get("exists"))


def workspace_files(workspace: Path) -> WorkspaceFiles:
    data = _call(
        lambda client: client.get("/api/workspace/files", params={"workspace": str(workspace)})
    )
    return WorkspaceFiles(
        tracked=tuple(str(path) for path in data.get("files") or []),
        untracked=tuple(str(path) for path in data.get("untracked") or []),
    )


def _put_flag(workspace: Path, path: str, *, enabled: bool) -> None:
    body = {"workspace": str(workspace), "enabled": enabled}
    _call(lambda client: client.put(path, body))


# Workflows and history.


def workflows() -> list[WorkflowShape]:
    return [
        WorkflowShape(
            id=str(item["id"]),
            label=str(item.get("label") or item["id"]),
            description=str(item.get("description") or ""),
            default_prompt=str(item.get("default_prompt") or ""),
            is_default=bool(item.get("is_default")),
            steps=tuple(
                (str(step["id"]), str(step.get("label") or step["id"]))
                for step in item.get("steps") or ()
            ),
        )
        for item in _call(lambda client: client.workflows())
    ]


def workflow(workflow_id: str) -> WorkflowShape | None:
    return next((item for item in workflows() if item.id == workflow_id), None)


def history(workspace: Path, query: str = "") -> list[HistoryItem]:
    params = {"workspace": str(workspace), "query": query}
    data = _call(lambda client: client.get("/api/history", params=params))
    return [HistoryItem.from_dict(item) for item in data.get("items") or ()]


def history_item(workspace: Path, item_id: str) -> HistoryItem | None:
    params = {"workspace": str(workspace)}
    data = _found(lambda client: client.get(f"/api/history/{item_id}", params=params))
    return HistoryItem.from_dict(data) if data is not None else None


def _refused_while_running(
    item_id: str, path: str, params: dict[str, str]
) -> Callable[[EngineClient], dict[str, Any]]:
    def delete(client: EngineClient) -> dict[str, Any]:
        try:
            return client.delete(path, params=params)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == CONFLICT:
                raise RunInUse(item_id) from error
            raise

    return delete


def delete_history_item(workspace: Path, item_id: str) -> bool:
    """`False` when the run is already gone; raises `RunInUse` while the daemon executes it."""
    params = {"workspace": str(workspace)}
    delete = _refused_while_running(item_id, f"/api/history/{item_id}", params)
    return _found(delete) is not None


def worktree_state(workspace: Path, item_id: str) -> WorktreeState | None:
    params = {"workspace": str(workspace)}
    data = _found(lambda client: client.get(f"/api/history/{item_id}/worktree", params=params))
    if data is None:
        return None
    return WorktreeState(
        path=str(data.get("path") or ""),
        exists=bool(data.get("exists")),
        dirty=bool(data.get("dirty")),
        active=bool(data.get("active")),
    )


def remove_worktree(workspace: Path, item_id: str) -> bool:
    """`False` when git refused; raises `RunInUse` while the daemon executes the run."""
    params = {"workspace": str(workspace)}
    delete = _refused_while_running(item_id, f"/api/history/{item_id}/worktree", params)
    data = _found(delete, timeout=PROBE_TIMEOUT_SECONDS)
    return bool(data and data.get("removed"))


def run_log(run_id: str) -> RunLog | None:
    data = _found(lambda client: client.get(f"/api/runs/{run_id}/log"))
    return RunLog.from_dict(data) if data is not None else None
