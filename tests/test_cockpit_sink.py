from __future__ import annotations

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState, LogKind, PhaseStatus


def test_cockpit_sink_streams_assistant_and_tools():
    state = CockpitState()
    state.configure_workflow("new-issue")
    dirty = {"n": 0}
    sink = CockpitSink(state, on_change=lambda: dirty.__setitem__("n", dirty["n"] + 1))

    sink.begin_phase("Fase Specify")
    assert state.phases[0].status == PhaseStatus.RUNNING

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "Analisando `modelo`"},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.ASSISTANT

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "call-1",
                "title": "Read File",
                "kind": "read",
            }
        }
    )
    assert state.entries[-1].kind == LogKind.READ
    assert state.entries[-1].title == "…"

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "call-1",
                "status": "completed",
                "rawOutput": {"content": "# Specify\n\n**Goal**: capture requirements"},
            }
        }
    )
    assert state.entries[-1].title == "Specify"
    assert dirty["n"] > 0


def test_edit_update_fills_path():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Specify")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "edit-1",
                "title": "Edit File",
                "kind": "edit",
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "edit-1",
                "status": "completed",
                "content": [
                    {
                        "type": "diff",
                        "path": "/repo/.pulse/specs/features/demo/spec.md",
                    }
                ],
            }
        }
    )
    entry = state.entries[-1]
    assert entry.kind == LogKind.EDIT
    assert entry.title.endswith("spec.md")
    assert "features" in entry.title


def test_search_update_shows_file_count():
    state = CockpitState()
    state.configure_workflow("fix-bug")
    sink = CockpitSink(state)
    sink.begin_phase("Planejar")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "find-1",
                "title": "Find",
                "kind": "search",
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "find-1",
                "status": "completed",
                "rawOutput": {"totalFiles": 4, "truncated": False},
            }
        }
    )
    assert state.entries[-1].kind == LogKind.SEARCH
    assert state.entries[-1].title == "4 files"


def test_cockpit_sink_suppresses_questionnaire_stream():
    state = CockpitState()
    state.configure_workflow("setup-project")
    sink = CockpitSink(state)
    sink.begin_phase("Fase 1")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "text",
                    "text": "Preciso de algumas informações\n```text\n",
                },
            }
        }
    )
    assert any(entry.title == "Questionário interativo" for entry in state.entries)
