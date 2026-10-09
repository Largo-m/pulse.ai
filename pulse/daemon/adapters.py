from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.domain.ports import Choice, JsonObject, Questionnaire, StepRow
from pulse.domain.run import StepStatus
from pulse.replies.acp_payloads import mapping_of
from pulse.replies.permission import decide_permission, parse_policy
from pulse.replies.text_questionnaire import (
    TextQuestionnaire,
    parse_text_questionnaire,
    serialize_questionnaire,
)

_log = logging.getLogger(__name__)


class ApiStreamSink:
    def __init__(self, bus: EventBus, *, run_id: str) -> None:
        self._bus = bus
        self._run_id = run_id
        self._agent_text = ""
        self._statuses: dict[str, StepStatus] = {}

    def handle_update(self, params: JsonObject) -> None:
        update = mapping_of(params.get("update"))
        if update.get("sessionUpdate") == "agent_message_chunk":
            content = mapping_of(update.get("content"))
            if content.get("type") == "text":
                self._agent_text += str(content.get("text", ""))
        self._bus.publish({"type": "session.update", "params": params})

    def begin_phase(self, title: str, *, turn: int = 1) -> None:
        _log.info("phase.begin run_id=%s title=%r turn=%d", self._run_id, title, turn)
        self._bus.publish({"type": "phase.begin", "title": title, "turn": turn})

    def set_model(self, model: str) -> None:
        self._bus.publish({"type": "session.model", "model": model})

    def reset_capture(self) -> None:
        self._agent_text = ""

    def agent_text(self) -> str:
        return self._agent_text

    def finish(self) -> None:
        self._bus.publish({"type": "stream.finish"})

    def finish_question_prompt(self) -> None:
        self._bus.publish({"type": "stream.finish_question"})

    def begin_user_wait(self) -> None:
        """The run stopped working: an open question is waiting for someone.

        Published on the bus, so late attachers get it on replay. `since` is the
        wall-clock start of the wait, so the clock freezes there, not at attach time.
        """
        _log.info("run.awaiting run_id=%s waiting=True", self._run_id)
        self._bus.publish({"type": "run.awaiting", "waiting": True, "since": time.time()})

    def end_user_wait(self) -> None:
        _log.info("run.awaiting run_id=%s waiting=False", self._run_id)
        self._bus.publish({"type": "run.awaiting", "waiting": False})

    def info(self, title: str) -> None:
        self._bus.publish({"type": "phase.info", "title": title})

    def error(self, title: str, reason: str = "") -> None:
        self._bus.publish({"type": "phase.error", "title": title, "reason": reason})

    def apply_phase_statuses(
        self,
        *,
        steps: Sequence[StepRow] = (),
        done_ids: Sequence[str] = (),
        skipped_ids: Sequence[str] = (),
        failed_ids: Sequence[str] = (),
        blocked_ids: Sequence[str] = (),
    ) -> None:
        self._log_status_changes(
            {
                **dict.fromkeys(done_ids, StepStatus.DONE),
                **dict.fromkeys(skipped_ids, StepStatus.SKIPPED),
                **dict.fromkeys(failed_ids, StepStatus.FAILED),
                **dict.fromkeys(blocked_ids, StepStatus.BLOCKED),
            }
        )
        self._bus.publish(
            {
                "type": "phases.sync",
                "steps": list(steps),
                "done_ids": list(done_ids),
                "skipped_ids": list(skipped_ids),
                "failed_ids": list(failed_ids),
                "blocked_ids": list(blocked_ids),
            }
        )

    def _log_status_changes(self, statuses: dict[str, StepStatus]) -> None:
        """One line per step whose end status changed since the last sync.

        The engine resends every status on each sync; only the change says what happened.
        """
        for step_id, status in statuses.items():
            if self._statuses.get(step_id) != status:
                _log.info("step.status run_id=%s step=%s status=%s", self._run_id, step_id, status)
        self._statuses = statuses

    def set_session_id(self, session_id: str) -> None:
        self._bus.publish({"type": "session.id", "session_id": session_id})

    def set_context(self, *, cwd: str, branch: str) -> None:
        """Where the run works and on which branch.

        Published on the bus, so late attachers get it on replay and the
        artifacts pane can point at the worktree.
        """
        self._bus.publish({"type": "run.context", "cwd": cwd, "branch": branch})


class ApiPromptPort:
    def __init__(self, correlator: PromptCorrelator) -> None:
        self._correlator = correlator

    def respond_to_ask_question(self, params: JsonObject) -> JsonObject:
        answer = self._correlator.request("ask_question", params)
        return _acp_answer(answer)

    def respond_to_create_plan(self, params: JsonObject) -> JsonObject:
        answer = self._correlator.request("create_plan", params)
        return _acp_answer(answer)

    def respond_to_permission(
        self,
        params: JsonObject,
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> JsonObject:
        decided = decide_permission(
            params, policy=parse_policy(policy), allow_terminal=allow_terminal
        )
        if decided is not None:
            return decided

        answer = self._correlator.request(
            "permission",
            {
                "params": params,
                "policy": policy,
                "allow_terminal": allow_terminal,
            },
        )
        return _acp_answer(answer)

    def run_parsed_questionnaire(self, questionnaire: Questionnaire) -> str | None:
        payload: JsonObject = (
            serialize_questionnaire(questionnaire)
            if isinstance(questionnaire, TextQuestionnaire)
            else {"title": questionnaire.title, "raw": questionnaire.raw}
        )
        answer = self._correlator.request("questionnaire", payload)
        if answer is None:
            return None
        return str(answer)

    def run_text_questionnaire(self, text: str) -> str | None:
        questionnaire = parse_text_questionnaire(text)
        if questionnaire is None:
            return None
        return self.run_parsed_questionnaire(questionnaire)

    def ask_text(self, prompt: str, *, title: str = "") -> str | None:
        answer = self._correlator.request("text", {"prompt": prompt, "title": title})
        if answer is None:
            return None
        text = str(answer).strip()
        return text or None

    def select_choice(
        self,
        prompt: str,
        choices: list[tuple[str, Choice]],
        *,
        title: str = "",
    ) -> Choice | None:
        serializable = [
            {"index": index, "label": label, "value_repr": repr(value)}
            for index, (label, value) in enumerate(choices)
        ]
        answer = self._correlator.request(
            "choice",
            {"prompt": prompt, "title": title, "choices": serializable},
        )
        index = _choice_index(answer)
        if index is None or not 0 <= index < len(choices):
            return None
        return choices[index][1]


def _acp_answer(answer: object) -> JsonObject:
    """The client's ACP answer; no answer, or one that is not an object, cancels."""
    if isinstance(answer, dict):
        return answer
    return {"outcome": {"outcome": "cancelled"}}


def _choice_index(answer: object) -> int | None:
    """The picked position: the client answers `{"index": n}`; a bare `n` is accepted too."""
    raw = answer.get("index") if isinstance(answer, dict) else answer
    if isinstance(raw, bool) or not isinstance(raw, int):
        return None
    return raw
