from __future__ import annotations

import time
from typing import Any

from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.prompts.permission import decide_permission
from pulse.prompts.text_questionnaire import parse_text_questionnaire, serialize_questionnaire


class ApiStreamSink:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._agent_text = ""
        self.cockpit = True

    def handle_update(self, params: dict[str, Any]) -> None:
        update = params.get("update", {})
        if isinstance(update, dict) and update.get("sessionUpdate") == "agent_message_chunk":
            content = update.get("content", {})
            if isinstance(content, dict) and content.get("type") == "text":
                self._agent_text += str(content.get("text", ""))
        self._bus.publish({"type": "session.update", "params": params})

    def begin_phase(self, title: str) -> None:
        self._bus.publish({"type": "phase.begin", "title": title})

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
        self._bus.publish({"type": "run.awaiting", "waiting": True, "since": time.time()})

    def end_user_wait(self) -> None:
        self._bus.publish({"type": "run.awaiting", "waiting": False})

    def info(self, title: str) -> None:
        self._bus.publish({"type": "phase.info", "title": title})

    def error(self, title: str, reason: str = "") -> None:
        self._bus.publish({"type": "phase.error", "title": title, "reason": reason})

    def apply_phase_statuses(self, **kwargs: Any) -> None:
        self._bus.publish({"type": "phases.sync", **kwargs})

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

    def respond_to_ask_question(self, params: dict[str, Any]) -> dict[str, Any]:
        answer = self._correlator.request("ask_question", params)
        if answer is None:
            return {"outcome": {"outcome": "cancelled"}}
        return answer

    def respond_to_create_plan(self, params: dict[str, Any]) -> dict[str, Any]:
        answer = self._correlator.request("create_plan", params)
        if answer is None:
            return {"outcome": {"outcome": "cancelled"}}
        return answer

    def respond_to_permission(
        self,
        params: dict[str, Any],
        *,
        policy: str,
        allow_terminal: bool = False,
    ) -> dict[str, Any]:
        decided = decide_permission(params, policy=policy, allow_terminal=allow_terminal)
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
        if answer is None:
            return {"outcome": {"outcome": "cancelled"}}
        return answer

    def run_parsed_questionnaire(self, questionnaire: Any) -> str | None:
        if hasattr(questionnaire, "questions"):
            payload = serialize_questionnaire(questionnaire)
        else:
            payload = {
                "title": getattr(questionnaire, "title", ""),
                "raw": getattr(questionnaire, "raw", ""),
            }
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
        choices: list[tuple[str, Any]],
        *,
        title: str = "",
    ) -> Any | None:
        serializable = []
        for index, (label, value) in enumerate(choices):
            serializable.append({"index": index, "label": label, "value_repr": repr(value)})
        answer = self._correlator.request(
            "choice",
            {"prompt": prompt, "title": title, "choices": serializable},
        )
        if answer is None:
            return None
        if isinstance(answer, dict) and "index" in answer:
            idx = int(answer["index"])
            if 0 <= idx < len(choices):
                return choices[idx][1]
        if isinstance(answer, int) and 0 <= answer < len(choices):
            return choices[answer][1]
        return answer
