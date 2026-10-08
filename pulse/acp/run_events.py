"""Run log persisted in the Pulse database: what the cockpit shows, saved for history.

Lives outside [pulse.acp.session_runner] because it is not ACP transport: it
translates `session/update` into `run_events` rows and run artifacts.
"""

from __future__ import annotations

from typing import Any

from pulse.history.events import LogKind
from pulse.history.prompt_detail import build_prompt_qa
from pulse.history.tool_detail import build_tool_labels, extract_paths, merge_tool_update
from pulse.replies.text_questionnaire import QUESTIONNAIRE_NOTICE, strip_questionnaire_block


class RunEventRecorder:
    """Runner mixin.

    Reads `_bound_run_id`, `_phase_id`, `_session_id`, `_cwd` and `_stream` from
    the runner; the log state (`_text_buffer`, `_tool_payloads`, `_tool_kinds`,
    `_tool_labeled`) is also initialized by the runner.
    """

    _PATH_KEYS = ("path", "file_path", "target_file", "filePath", "abs_path")
    _WRITE_KINDS = frozenset({"edit", "write", "create"})

    def _record_run_event(self, params: dict[str, Any]) -> None:
        """Persist to the Pulse database what the cockpit is showing.

        The runtime's own log is not usable: only Cursor has one, and Pulse is
        agent-agnostic. Rows use the same labels as the live screen
        ([pulse.history.tool_detail.build_tool_labels]) so history matches it.
        """
        if not self._bound_run_id:
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
                    self._text_buffer.append(text)
            return
        if kind not in {"tool_call", "tool_call_update", "tool_result"}:
            return
        self._flush_text()
        tool_id = str(update.get("toolCallId") or "")
        merged = self._merge_tool_payload(tool_id, update)
        log_kind, title, detail = self._tool_labels(tool_id, merged)
        if title.strip() in {"", "…", "..."} and not detail.strip():
            if tool_id in self._tool_labeled:
                return
            title = "…"
        elif tool_id:
            self._tool_labeled.add(tool_id)
        self._save_event(kind=log_kind, title=title, detail=detail, tool_id=tool_id)
        self._record_artifacts(merged, log_kind)

    def _merge_tool_payload(self, tool_id: str, update: dict[str, Any]) -> dict[str, Any]:
        if not tool_id:
            return update
        merged = merge_tool_update(self._tool_payloads.get(tool_id, {}), update)
        self._tool_payloads[tool_id] = merged
        return merged

    def _tool_labels(self, tool_id: str, update: dict[str, Any]) -> tuple[str, str, str]:
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
        except Exception:
            return "Tool", self._fallback_title(update), self._fallback_detail(update)

    @staticmethod
    def _fallback_title(update: dict[str, Any]) -> str:
        return str(update.get("title") or update.get("kind") or "tool").strip()

    def _fallback_detail(self, update: dict[str, Any]) -> str:
        raw = update.get("rawInput")
        if isinstance(raw, dict):
            for key in (*self._PATH_KEYS, "command", "pattern", "query"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return ""

    def _record_artifacts(self, update: dict[str, Any], log_kind: str = "") -> None:
        """Record the files the tool call wrote.

        The ACP `kind` is not always sent, so the `build_tool_labels`
        classification (the same one the live artifacts tab uses) also counts.
        """
        writes = str(update.get("kind") or "").lower() in self._WRITE_KINDS
        if not writes and log_kind not in {"Write", "Edit"}:
            return
        for path in self._artifact_paths(update):
            try:
                from pulse.store.runs import record_artifact

                record_artifact(self._bound_run_id, path, step_id=self._phase_id)
            except Exception:
                pass

    def _artifact_paths(self, update: dict[str, Any]) -> list[str]:
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
            for key in self._PATH_KEYS:
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    found.append(value.strip())
                    break
        return list(dict.fromkeys(found))

    def _begin_phase(self, label: str) -> None:
        """Open the phase on screen and leave the same marker in the recorded log.

        Without it, history would merge consecutive turns into a single block.
        """
        self._flush_text()
        self._stream.begin_phase(label)
        self._save_event(kind="Info", title=label, detail=label)

    def _record_prompt_qa(
        self,
        name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        result: Any,
    ) -> None:
        """Record in the run log the question asked and the answer given.

        The live screen draws both bubbles ([pulse.tui.state.CockpitState.add_qa])
        but does not write to the database, so history relies on this.
        """
        if not self._bound_run_id:
            return
        try:
            pairs = build_prompt_qa(name, args, kwargs, result)
        except Exception as error:  # noqa: BLE001
            self._save_event(
                kind="Info",
                title="Diálogo não registrado",
                detail=f"{name}: {type(error).__name__}: {error}",
            )
            return
        for question, answer in pairs:
            if not question.strip():
                continue
            self._flush_text()
            self._save_event(kind="Question", title="Pergunta", detail=question)
            self._save_event(kind="Answer", title="Você", detail=answer)

    def _flush_text(self) -> None:
        """Flush the agent's accumulated speech into a single log row.

        The questionnaire block is stripped (it is already recorded as
        question/answer rows) and replaced by the same notice the cockpit shows.
        """
        text = "".join(self._text_buffer).strip()
        self._text_buffer.clear()
        if not text:
            return
        spoken, had_questionnaire = strip_questionnaire_block(text)
        if spoken:
            self._save_event(kind="Assistant", title=spoken[:160], detail=spoken)
        if had_questionnaire:
            self._save_event(
                kind="Info",
                title=QUESTIONNAIRE_NOTICE,
                detail=QUESTIONNAIRE_NOTICE,
            )

    def _save_event(self, *, kind: str, title: str, detail: str, tool_id: str = "") -> None:
        try:
            from pulse.store.runs import record_event

            record_event(
                self._bound_run_id,
                step_id=self._phase_id,
                acp_session_id=self._session_id or "",
                kind=kind,
                title=title,
                detail=detail,
                tool_id=tool_id,
            )
        except Exception:
            pass
