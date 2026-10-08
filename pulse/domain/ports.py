from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeAlias, TypedDict, TypeVar, runtime_checkable

from pulse.domain.run import RunRecord, StepRecord

JsonObject: TypeAlias = dict[str, object]
"""An ACP JSON-RPC payload. Its shape belongs to the runtime, so adapters narrow it at the edge."""

Choice = TypeVar("Choice")


class StepRow(TypedDict):
    """One step as the panel lists it; fan-out changes the list mid-run."""

    id: str
    label: str
    rounds: int


class Questionnaire(Protocol):
    """A questionnaire parsed from the agent's text; `pulse.replies` owns the concrete shape."""

    @property
    def title(self) -> str: ...

    @property
    def raw(self) -> str: ...


@runtime_checkable
class StreamSink(Protocol):
    """Where a run shows its progress: the cockpit over SSE, or a plain console.

    The engine calls every method unconditionally; an adapter with nothing to
    show for one implements it as a no-op instead of leaving it out.
    """

    def handle_update(self, params: JsonObject) -> None: ...

    def begin_phase(self, title: str) -> None: ...

    def reset_capture(self) -> None: ...

    def agent_text(self) -> str: ...

    def finish(self) -> None: ...

    def finish_question_prompt(self) -> None: ...

    def begin_user_wait(self) -> None: ...

    def end_user_wait(self) -> None: ...

    def set_context(self, *, cwd: str, branch: str) -> None: ...

    def set_session_id(self, session_id: str) -> None: ...

    def info(self, title: str) -> None: ...

    def error(self, title: str, reason: str = "") -> None: ...

    def apply_phase_statuses(
        self,
        *,
        steps: Sequence[StepRow] = (),
        done_ids: Sequence[str] = (),
        skipped_ids: Sequence[str] = (),
        failed_ids: Sequence[str] = (),
        blocked_ids: Sequence[str] = (),
    ) -> None: ...


@runtime_checkable
class PromptPort(Protocol):
    def respond_to_ask_question(self, params: JsonObject) -> JsonObject: ...

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject: ...

    def respond_to_permission(
        self,
        params: JsonObject,
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> JsonObject: ...

    def run_parsed_questionnaire(self, questionnaire: Questionnaire) -> str | None: ...

    def run_text_questionnaire(self, text: str) -> str | None: ...

    def ask_text(self, prompt: str, *, title: str = "") -> str | None: ...

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Choice]],
        *,
        title: str = "",
    ) -> Choice | None: ...


@runtime_checkable
class RunRepository(Protocol):
    """Where a run lives between steps, so a stopped or crashed run can be resumed."""

    def create(
        self,
        *,
        run_id: str,
        workflow_id: str,
        workspace: Path,
        user_prompt: str,
        steps: Sequence[StepRecord],
    ) -> RunRecord:
        """A new running run whose steps are all pending, stored before it is returned."""
        ...

    def load(self, run_id: str) -> RunRecord | None: ...

    def save(self, run: RunRecord) -> None:
        """Store the whole aggregate at once: the run and its steps never disagree."""
        ...

    def artifacts(self, run_id: str) -> list[str]:
        """Paths the agents wrote during the run, relative to where it worked."""
        ...


class PhaseContinuation(Protocol):
    """The prompt after the user answered the approval questionnaire with anything but approve."""

    def __call__(self, *, phase_summary: str, questionnaire_answers: str, outcome: str) -> str: ...


class PromptContinuation(Protocol):
    """The next prompt in the same ACP session, from the turn so far; empty ends the step."""

    def __call__(self, *, result: JsonObject, turn: int) -> str: ...


@dataclass(frozen=True)
class AgentProfile:
    """What a step's agent runs with: the user's config over the agent definition.

    `permission_policy` stays text here; the session parses it at its edge and
    falls back to asking, never to allowing.
    """

    agent_id: str
    model: str | None
    permission_policy: str
    instructions: str = ""


@runtime_checkable
class AgentProfiles(Protocol):
    def profile(self, agent_id: str) -> AgentProfile: ...


@runtime_checkable
class AgentSession(Protocol):
    """The agent process a run talks to; every step opens its own session in it.

    One step's session never carries over to the next: the next step only gets
    the summary the engine forwards.
    """

    @property
    def prompts(self) -> PromptPort:
        """Where the engine asks its own questions, so they count as user waits."""
        ...

    @property
    def last_session_id(self) -> str: ...

    def bind_run(self, run_id: str, waits: UserWaitListener) -> None: ...

    def open(self, cwd: Path) -> None:
        """Start the agent in `cwd`, known only once the run has a place to work."""
        ...

    def close(self) -> None: ...

    def revive(self) -> bool:
        """Restart a dead or hung agent; `True` when it had to."""
        ...

    def use_agent(self, profile: AgentProfile) -> None: ...

    def run_isolated_phase(
        self,
        *,
        workflow: str,
        phase_label: str,
        initial_prompt: str,
        preferred_model: str | None = None,
        build_continuation: PhaseContinuation | None = None,
        phase_id: str = "",
    ) -> JsonObject:
        """A step that ends in the approval questionnaire."""
        ...

    def run_isolated_prompt(
        self,
        *,
        workflow: str,
        phase_label: str,
        prompt_text: str,
        preferred_model: str | None = None,
        phase_id: str = "",
        build_continuation: PromptContinuation | None = None,
    ) -> JsonObject:
        """A step that ends when the agent ends its turn."""
        ...


class WorkspaceError(RuntimeError):
    """The run could not get a place to work: a worktree that would not open."""


@runtime_checkable
class Workspace(Protocol):
    """The project a run works on, and the per-run worktrees it may open from it.

    `root` stays the run's identity (config and history resolve by it); a
    worktree only changes where the agent writes.
    """

    @property
    def root(self) -> Path: ...

    def is_repo(self) -> bool: ...

    def current_branch(self) -> str:
        """Empty on a detached HEAD or outside a repository."""
        ...

    def has_branch(self, branch: str) -> bool: ...

    def worktree_exists(self, path: str) -> bool: ...

    def attach_worktree(self, run_id: str, branch: str) -> Path:
        """Reopen the run's worktree on a branch it already owns."""
        ...

    def add_worktree(self, run_id: str, branch: str) -> tuple[Path, str]:
        """Open the run's worktree on a new branch; the name gets a suffix if taken."""
        ...


@runtime_checkable
class UserWaitListener(Protocol):
    """Told when a question to the user opens and closes, so the run can pause its clock."""

    def user_wait_began(self) -> None: ...

    def user_wait_ended(self, step_id: str, seconds: float) -> None: ...


class NullStreamSink:
    def __init__(self) -> None:
        self._agent_text = ""

    def handle_update(self, params: JsonObject) -> None:
        update = params.get("update", {})
        if not isinstance(update, dict):
            return
        if update.get("sessionUpdate") != "agent_message_chunk":
            return
        content = update.get("content", {})
        if isinstance(content, dict) and content.get("type") == "text":
            self._agent_text += str(content.get("text", ""))

    def begin_phase(self, title: str) -> None:
        return None

    def reset_capture(self) -> None:
        self._agent_text = ""

    def agent_text(self) -> str:
        return self._agent_text

    def finish(self) -> None:
        return None

    def finish_question_prompt(self) -> None:
        return None

    def begin_user_wait(self) -> None:
        return None

    def end_user_wait(self) -> None:
        return None

    def info(self, title: str) -> None:
        return None

    def error(self, title: str, reason: str = "") -> None:
        return None

    def apply_phase_statuses(
        self,
        *,
        steps: Sequence[StepRow] = (),
        done_ids: Sequence[str] = (),
        skipped_ids: Sequence[str] = (),
        failed_ids: Sequence[str] = (),
        blocked_ids: Sequence[str] = (),
    ) -> None:
        return None

    def set_session_id(self, session_id: str) -> None:
        return None

    def set_context(self, *, cwd: str, branch: str) -> None:
        return None


class NullUserWaitListener:
    def user_wait_began(self) -> None:
        return None

    def user_wait_ended(self, step_id: str, seconds: float) -> None:
        return None


class NullPromptPort:
    def respond_to_ask_question(self, params: JsonObject) -> JsonObject:
        return {"outcome": {"outcome": "cancelled"}}

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject:
        return {"outcome": {"outcome": "cancelled"}}

    def respond_to_permission(
        self,
        params: JsonObject,
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> JsonObject:
        return {"outcome": {"outcome": "cancelled"}}

    def run_parsed_questionnaire(self, questionnaire: Questionnaire) -> str | None:
        return None

    def run_text_questionnaire(self, text: str) -> str | None:
        return None

    def ask_text(self, prompt: str, *, title: str = "") -> str | None:
        return None

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Choice]],
        *,
        title: str = "",
    ) -> Choice | None:
        return None
