"""The run log an agent session leaves in the database: what the cockpit showed, kept for history.

The `SessionLog` adapter the daemon hands the ACP session runner. It is not ACP
transport: it turns `session/update` into `run_events` rows and run artifacts,
labelled exactly as the live screen labels them, so a past run reopens the same.
"""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path

from pulse.config.project_config import load_project_config
from pulse.domain import ui_text
from pulse.domain.ports import JsonObject
from pulse.history.events import LogKind
from pulse.history.prompt_detail import build_prompt_qa
from pulse.history.tool_detail import build_tool_labels, extract_paths, merge_tool_update
from pulse.replies.text_questionnaire import strip_questionnaire_block
from pulse.store import runs as run_store
from pulse.store.sessions import persist_runtime_session

_PATH_KEYS = ("path", "file_path", "target_file", "filePath", "abs_path")
_WRITE_KINDS = frozenset({"edit", "write", "create"})
_TOOL_UPDATES = frozenset({"tool_call", "tool_call_update", "tool_result"})


class RecordedSessionLog:
    """Records into the Pulse database; nothing happens until a run is bound."""

    def __init__(self) -> None:
        self._run_id = ""
        self._step_id = ""
        self._session_id = ""
        self._cwd = ""
        self._text: list[str] = []
        self._tool_payloads: dict[str, JsonObject] = {}
        self._tool_kinds: dict[str, str] = {}
        self._tool_labeled: set[str] = set()

    def bind_run(self, run_id: str) -> None:
        self._run_id = run_id

    def enter_step(self, step_id: str) -> None:
        self._step_id = step_id

    def enter_session(
        self, session_id: str, *, pulse_session_id: str, cwd: str, agent_id: str | None
    ) -> None:
        """A new session has its own tool ids; the pointer to it goes to `agent_sessions`."""
        self._tool_payloads.clear()
        self._tool_kinds.clear()
        self._tool_labeled.clear()
        self._session_id = session_id
        self._cwd = cwd
        try:
            project = load_project_config(Path(cwd))
            if project is not None:
                persist_runtime_session(
                    project.project_id,
                    pulse_session_id=pulse_session_id,
                    acp_session_id=session_id,
                    agent_id=agent_id,
                )
        except (sqlite3.Error, OSError) as error:
            self.notice("Runtime session not recorded", f"{type(error).__name__}: {error}")

    def update(self, params: JsonObject) -> None:
        """Persist to the Pulse database what the cockpit is showing.

        The runtime's own log is not usable: only Cursor has one, and Pulse is
        agent-agnostic. Rows use the same labels as the live screen
        ([pulse.history.tool_detail.build_tool_labels]) so history matches it.
        """
        if not self._run_id:
            return
        update = params.get("update", params)
        if not isinstance(update, dict):
            return
        kind = str(update.get("sessionUpdate") or "")
        if kind == "agent_message_chunk":
            content = update.get("content")
            if isinstance(content, dict) and content.get("type") == "text":
                text = str(content.get("text") or "")
                if text:
                    self._text.append(text)
            return
        if kind not in _TOOL_UPDATES:
            return
        self.flush()
        tool_id = str(update.get("toolCallId") or "")
        merged = self._merge_tool_payload(tool_id, update)
        log_kind, title, detail = self._tool_labels(tool_id, merged)
        if title.strip() in {"", "…", "..."} and not detail.strip():
            if tool_id in self._tool_labeled:
                return
            title = "…"
        elif tool_id:
            self._tool_labeled.add(tool_id)
        self._save(kind=log_kind, title=title, detail=detail, tool_id=tool_id)
        self._record_artifacts(merged, log_kind)

    def phase(self, label: str) -> None:
        self._save(kind="Info", title=label, detail=label)

    def dialog(
        self, name: str, args: tuple[object, ...], kwargs: dict[str, object], result: object
    ) -> None:
        """Record the question asked and the answer given.

        The live screen draws both bubbles ([pulse.tui.state.CockpitState.add_qa])
        but does not write to the database, so history relies on this.
        """
        if not self._run_id:
            return
        try:
            pairs = build_prompt_qa(name, args, kwargs, result)
        # The answer already reached the agent; a dialog shape the builder does
        # not know must not undo that.
        except Exception as error:  # noqa: BLE001
            self.notice("Dialog not recorded", f"{name}: {type(error).__name__}: {error}")
            return
        for question, answer in pairs:
            if not question.strip():
                continue
            self.flush()
            self._save(kind="Question", title=ui_text.QUESTION_TITLE, detail=question)
            self._save(kind="Answer", title=ui_text.ANSWER_TITLE, detail=answer)

    def notice(self, title: str, detail: str) -> None:
        self._save(kind="Info", title=title, detail=detail)

    def flush(self) -> None:
        """Flush the agent's accumulated speech into a single log row.

        The questionnaire block is stripped (it is already recorded as
        question/answer rows) and replaced by the same notice the cockpit shows.
        """
        text = "".join(self._text).strip()
        self._text.clear()
        if not text:
            return
        spoken, had_questionnaire = strip_questionnaire_block(text)
        if spoken:
            self._save(kind="Assistant", title=spoken[:160], detail=spoken)
        if had_questionnaire:
            notice = ui_text.QUESTIONNAIRE_NOTICE
            self._save(kind="Info", title=notice, detail=notice)

    def _merge_tool_payload(self, tool_id: str, update: JsonObject) -> JsonObject:
        if not tool_id:
            return update
        merged = merge_tool_update(self._tool_payloads.get(tool_id, {}), update)
        self._tool_payloads[tool_id] = merged
        return merged

    def _tool_labels(self, tool_id: str, update: JsonObject) -> tuple[str, str, str]:
        """(kind, title, detail) of a tool call, as the live screen builds them.

        Labeling is incidental: any failure falls back to the raw ACP `title`
        instead of breaking the run.
        """
        try:
            previous = self._tool_kinds.get(tool_id)
            fallback = LogKind(previous) if previous else None
            log_kind, title, detail = build_tool_labels(
                update, cwd=self._cwd, fallback_kind=fallback
            )
            if tool_id and log_kind != LogKind.TOOL:
                self._tool_kinds[tool_id] = log_kind.value
            return log_kind.value, title, detail
        # The classifier walks an untrusted agent payload inside the ACP read
        # loop; a shape it does not expect must not end the session.
        except Exception as error:  # noqa: BLE001
            self.notice("Tool call not labeled", f"{type(error).__name__}: {error}")
            return "Tool", _fallback_title(update), _fallback_detail(update)

    def _record_artifacts(self, update: JsonObject, log_kind: str = "") -> None:
        """Record the files the tool call wrote.

        The ACP `kind` is not always sent, so the `build_tool_labels`
        classification (the same one the live artifacts tab uses) also counts.
        """
        writes = str(update.get("kind") or "").lower() in _WRITE_KINDS
        if not writes and log_kind not in {"Write", "Edit"}:
            return
        for path in self._artifact_paths(update):
            try:
                run_store.record_artifact(self._run_id, path, step_id=self._step_id)
            except (sqlite3.Error, OSError) as error:
                self.notice("Artifact not recorded", f"{path}: {type(error).__name__}: {error}")

    def _artifact_paths(self, update: JsonObject) -> list[str]:
        """Paths touched by the tool call, relative to the workspace.

        Same extraction as the live screen, so recorded artifacts open from the
        history tab.
        """
        paths = extract_paths(update, cwd=self._cwd)
        if paths:
            return paths
        found: list[str] = []
        locations = update.get("locations")
        if isinstance(locations, list):
            for item in locations:
                if isinstance(item, dict):
                    value = item.get("path")
                    if isinstance(value, str) and value.strip():
                        found.append(value.strip())
        raw = update.get("rawInput")
        if isinstance(raw, dict):
            for key in _PATH_KEYS:
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
                    break
        return list(dict.fromkeys(found))

    def _save(self, *, kind: str, title: str, detail: str, tool_id: str = "") -> None:
        if not self._run_id:
            return
        # The run log is the record of last resort: with the database failing
        # there is nowhere left to write, and the agent's session must go on.
        with suppress(sqlite3.Error, OSError):
            run_store.record_event(
                self._run_id,
                step_id=self._step_id,
                acp_session_id=self._session_id,
                kind=kind,
                title=title,
                detail=detail,
                tool_id=tool_id,
            )


def _fallback_title(update: JsonObject) -> str:
    return str(update.get("title") or update.get("kind") or "tool").strip()


def _fallback_detail(update: JsonObject) -> str:
    raw = update.get("rawInput")
    if isinstance(raw, dict):
        for key in (*_PATH_KEYS, "command", "pattern", "query"):
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""
