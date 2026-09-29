from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pulse.prompts.text_questionnaire import extract_questionnaire_block
from pulse.tui.artifacts import artifact_has_content
from pulse.tui.cursor_store import CursorStoreIndex
from pulse.tui.state import CockpitState, LogKind
from pulse.tui.tool_detail import (
    build_tool_labels,
    extract_paths,
    merge_tool_update,
)

_TOOL_KINDS = frozenset({"tool_call", "tool_call_update", "tool_result"})
_QUESTIONNAIRE_START = re.compile(
    r"```(?:text)?|Preciso de algumas informações|I need some information before continuing|Apresentando todas as perguntas",
    re.IGNORECASE,
)
_SETUP_READY = re.compile(r"SETUP_READY\s*", re.IGNORECASE)
_MODEL_RE = re.compile(r"^Modelo:\s*(.+)$", re.IGNORECASE)
_COUNT_ONLY_RE = re.compile(r"^\d+\s+files?$", re.IGNORECASE)

NotifyFn = Callable[[], None]


def _is_placeholder(title: str, detail: str = "") -> bool:
    text = title.strip()
    if text in {"", "…", "..."}:
        return not detail.strip()
    return False


def _is_vague_search(title: str) -> bool:
    return bool(_COUNT_ONLY_RE.match(title.strip()))


def _tool_done(update: dict[str, Any]) -> bool:
    status = str(update.get("status") or "").strip().lower()
    return status in {"completed", "failed"}


def _tool_failed(update: dict[str, Any]) -> bool:
    status = str(update.get("status") or "").strip().lower()
    if status in {"failed", "error"}:
        return True
    raw_output = update.get("rawOutput")
    if isinstance(raw_output, dict) and raw_output.get("error"):
        return True
    return False


class CockpitSink:
    cockpit = True

    def __init__(
        self,
        state: CockpitState,
        *,
        on_change: NotifyFn | None = None,
        cwd: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self._state = state
        self._on_change = on_change
        self._cwd = cwd
        self._streaming_message = False
        self._agent_text = ""
        self._questionnaire_mode = False
        self._questionnaire_announced = False
        self._visible_tool_ids: set[str] = set()
        self._tool_payloads: dict[str, dict[str, Any]] = {}
        self._store = CursorStoreIndex(session_id)
        self._pending_session_phase = False

    def set_cwd(self, cwd: str | None) -> None:
        self._cwd = cwd

    def set_session_id(self, session_id: str | None) -> None:
        self._store.set_session(session_id)
        sid = session_id or ""
        self._state.acp_session_id = sid
        self._pending_session_phase = bool(sid)
        if not sid:
            return
        refs = self._state.acp_sessions
        if refs and refs[-1].get("session_id") == sid:
            return
        refs.append({"session_id": sid, "phase_id": ""})

    def reset_capture(self) -> None:
        self._agent_text = ""
        self._questionnaire_mode = False
        self._questionnaire_announced = False
        self._streaming_message = False

    def agent_text(self) -> str:
        return self._agent_text

    def has_text_questionnaire(self) -> bool:
        return extract_questionnaire_block(self._agent_text) is not None

    def handle_update(self, params: dict[str, Any]) -> None:
        update = params.get("update", params)
        if not isinstance(update, dict):
            return
        kind = update.get("sessionUpdate")

        if kind == "agent_message_chunk":
            content = update.get("content", {})
            if content.get("type") == "text":
                text = str(content.get("text", ""))
                if text:
                    self._agent_text += text
                    self._maybe_enter_questionnaire_mode()
                    if self._questionnaire_mode:
                        self._announce_questionnaire_once()
                        return
                    visible = _SETUP_READY.sub("", text)
                    changed = self._backfill_vague_entries()
                    if not visible:
                        if changed:
                            self._emit()
                        return
                    self._state.append_assistant(visible)
                    self._streaming_message = True
                    self._emit()
            return

        if kind == "agent_thought_chunk":
            if self._backfill_vague_entries():
                self._emit()
            return

        if kind in _TOOL_KINDS:
            self._handle_tool(update, kind=str(kind))
            return

        if kind == "session_info_update":
            title = update.get("title")
            if title:
                self._finish_message_line()
                title_text = str(title)
                match = _MODEL_RE.match(title_text)
                if match:
                    self._state.set_model(match.group(1).strip())
                    self._backfill_vague_entries()
                    self._emit()
            return

    def begin_phase(self, title: str) -> None:
        self.finish()
        self._visible_tool_ids.clear()
        self._tool_payloads.clear()
        self._state.begin_phase(title)
        if self._pending_session_phase and self._state.acp_sessions:
            self._state.acp_sessions[-1]["phase_id"] = self._state._entry_phase_id()
            self._pending_session_phase = False
        self._state.add_info(title)
        self._emit()

    def apply_phase_statuses(
        self,
        *,
        steps: list[dict[str, str]] | tuple[dict[str, str], ...] = (),
        done_ids: list[str] | tuple[str, ...] = (),
        skipped_ids: list[str] | tuple[str, ...] = (),
        failed_ids: list[str] | tuple[str, ...] = (),
    ) -> None:
        self._state.apply_phase_statuses(
            steps=steps,
            done_ids=done_ids,
            skipped_ids=skipped_ids,
            failed_ids=failed_ids,
        )
        self._emit()

    def mark_paused(self) -> None:
        self._finish_message_line()
        self._state.mark_paused()
        self._emit()

    def mark_resumed(self) -> None:
        self._state.mark_resumed()
        self._emit()

    def mark_stopped(self) -> None:
        self._finish_message_line()
        self._state.mark_stopped()
        self._emit()

    def info(self, title: str) -> None:
        text = str(title or "").strip()
        if not text:
            return
        self._finish_message_line()
        self._state.add_info(text)
        self._emit()

    def error(self, title: str, reason: str = "") -> None:
        text = str(title or "").strip() or "Erro"
        self._finish_message_line()
        self._state.add_error(text, str(reason or "").strip())
        self._emit()

    def finish(self) -> None:
        self._finish_message_line()

    def finish_question_prompt(self) -> None:
        self._finish_message_line()
        self._state.finish_assistant()
        self._emit()

    def _enrich_from_store(
        self,
        merged: dict[str, Any],
        tool_id: str,
        *,
        force: bool = False,
    ) -> dict[str, Any]:
        if not tool_id:
            return merged
        raw_input = merged.get("rawInput")
        if isinstance(raw_input, dict) and raw_input and not force:
            return merged
        args = self._store.lookup_args(tool_id, force=force)
        if not args:
            return merged
        return merge_tool_update(merged, {"rawInput": args})

    def _backfill_vague_entries(self) -> bool:
        changed = False
        for entry in self._state.entries:
            if not entry.tool_id:
                continue
            needs = False
            if entry.kind == LogKind.SEARCH and _is_vague_search(entry.title):
                needs = True
            elif entry.kind in {LogKind.READ, LogKind.EDIT, LogKind.WRITE} and entry.title.strip() in {
                "…",
                "...",
            }:
                needs = True
            if not needs:
                continue
            payload = self._tool_payloads.get(entry.tool_id, {"toolCallId": entry.tool_id})
            enriched = self._enrich_from_store(payload, entry.tool_id, force=True)
            self._tool_payloads[entry.tool_id] = enriched
            log_kind, target, detail = build_tool_labels(
                enriched,
                cwd=self._cwd,
                fallback_kind=entry.kind,
            )
            if _is_placeholder(target, detail):
                continue
            if entry.kind == LogKind.SEARCH and _is_vague_search(target):
                continue
            done = _tool_done(enriched)
            self._state.update_tool_entry(
                entry.tool_id,
                kind=log_kind,
                title=target,
                detail=detail,
                pending=not done,
            )
            self._record_tool_metrics(enriched, log_kind, target, ready=done)
            changed = True
        return changed

    def _handle_tool(self, update: dict[str, Any], *, kind: str) -> None:
        tool_id = str(update.get("toolCallId") or "")
        force_store = kind in {"tool_call_update", "tool_result"}
        if tool_id:
            previous = self._tool_payloads.get(tool_id, {})
            merged = merge_tool_update(previous, update)
            merged = self._enrich_from_store(merged, tool_id, force=force_store)
            self._tool_payloads[tool_id] = merged
        else:
            merged = update

        existing_kind = None
        if tool_id:
            for entry in self._state.entries:
                if entry.tool_id == tool_id:
                    existing_kind = entry.kind
                    break

        log_kind, target, detail = build_tool_labels(
            merged,
            cwd=self._cwd,
            fallback_kind=existing_kind,
        )
        placeholder = _is_placeholder(target, detail)
        done = _tool_done(merged) or kind == "tool_result"
        pending = not done or placeholder
        display_title = "…" if placeholder else target
        display_detail = "" if placeholder else detail
        changed = False

        if kind == "tool_call":
            if tool_id and tool_id in self._visible_tool_ids:
                if self._backfill_vague_entries():
                    self._emit()
                return
            if tool_id:
                self._visible_tool_ids.add(tool_id)
            self._finish_message_line()
            self._state.add_tool_entry(
                log_kind,
                display_title,
                display_detail,
                tool_id=tool_id,
                pending=True,
            )
            self._record_tool_metrics(merged, log_kind, target, ready=False)
            changed = True
        elif kind in {"tool_call_update", "tool_result"}:
            if tool_id and tool_id in self._visible_tool_ids:
                if placeholder and not done:
                    if self._backfill_vague_entries():
                        changed = True
                    if changed:
                        self._emit()
                    return
                updated = self._state.update_tool_entry(
                    tool_id,
                    kind=existing_kind or log_kind,
                    title=display_title if not placeholder else None,
                    detail=display_detail if not placeholder else None,
                    pending=pending,
                )
                if updated is not None:
                    self._record_tool_metrics(
                        merged,
                        existing_kind or log_kind,
                        target,
                        ready=not pending,
                    )
                    changed = True
            elif not placeholder or done:
                if tool_id:
                    self._visible_tool_ids.add(tool_id)
                self._finish_message_line()
                self._state.add_tool_entry(
                    log_kind,
                    display_title,
                    display_detail,
                    tool_id=tool_id,
                    pending=pending,
                )
                self._record_tool_metrics(
                    merged,
                    log_kind,
                    target,
                    ready=not pending,
                )
                changed = True

        if self._backfill_vague_entries():
            changed = True
        if changed:
            self._emit()

    def _record_tool_metrics(
        self,
        update: dict[str, Any],
        log_kind: LogKind,
        target: str,
        *,
        ready: bool,
    ) -> None:
        if _tool_failed(update):
            issue_key = str(update.get("toolCallId") or target or "").strip()
            if issue_key:
                self._state.record_issue(issue_key)

        paths = extract_paths(update, cwd=self._cwd)
        if not paths and log_kind in {
            LogKind.READ,
            LogKind.EDIT,
            LogKind.WRITE,
            LogKind.LIST,
        }:
            text = str(target or "").strip()
            if text and text not in {"…", "..."} and ("/" in text or "." in text):
                paths = [text]
        if paths:
            self._state.record_files(paths)
            if log_kind in {LogKind.WRITE, LogKind.EDIT}:
                for path in paths:
                    self._state.upsert_artifact(
                        path,
                        ready=ready,
                        has_content=artifact_has_content(path, self._cwd),
                    )

    def _maybe_enter_questionnaire_mode(self) -> None:
        if self._questionnaire_mode:
            return
        if _QUESTIONNAIRE_START.search(self._agent_text):
            self._questionnaire_mode = True
            self._finish_message_line()

    def _announce_questionnaire_once(self) -> None:
        if self._questionnaire_announced:
            return
        self._questionnaire_announced = True
        self._state.add_info("Questionário interativo")
        self._emit()

    def _finish_message_line(self) -> None:
        if self._streaming_message:
            self._streaming_message = False
            self._state.finish_assistant()

    def _emit(self) -> None:
        if self._on_change is not None:
            self._on_change()
