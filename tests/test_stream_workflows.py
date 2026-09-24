from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import WORKFLOW_PHASES, CockpitState, LogKind, PhaseStatus
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream

WORKFLOWS = tuple(WORKFLOW_PHASES.keys())

PHASE_TITLES: dict[str, tuple[str, ...]] = {
    "spec": ("Classificar spec",),
    "new-issue": ("Fase Specify", "Fase Design", "Fase Tasks", "Fase Execute"),
    "fix-bug": ("Fase 1 — Planejando quick task", "Fase 2 — Implementando quick task"),
    "setup-project": (
        "Fase 1 — Análise do projeto",
        "Fase 2 — Gerando .pulse/specs/project/",
    ),
    "analyze-codebase": (
        "Fase 1 — Explorando codebase",
        "Fase 2 — Gerando .pulse/specs/codebase/",
    ),
}

TOOL_SAMPLES: tuple[tuple[str, dict, LogKind, str], ...] = (
    (
        "read",
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-read",
            "title": "Read File",
            "kind": "read",
            "status": "pending",
            "rawInput": {"path": "/repo/pulse/cli.py"},
        },
        LogKind.READ,
        "pulse/cli.py",
    ),
    (
        "edit",
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-edit",
            "title": "Edit File",
            "kind": "edit",
            "status": "pending",
            "rawInput": {"path": "/repo/.pulse/specs/features/demo/spec.md"},
        },
        LogKind.EDIT,
        "spec.md",
    ),
    (
        "write",
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-write",
            "title": "Write File",
            "kind": "write",
            "status": "pending",
            "rawInput": {"path": "/repo/.pulse/specs/project/STATE.md"},
        },
        LogKind.WRITE,
        "STATE.md",
    ),
    (
        "search",
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-search",
            "title": "Find",
            "kind": "search",
            "status": "pending",
            "rawInput": {"pattern": "dashboard", "path": "/repo/.pulse/specs"},
        },
        LogKind.SEARCH,
        "dashboard",
    ),
    (
        "shell",
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "t-shell",
            "title": "Shell",
            "kind": "execute",
            "status": "pending",
            "rawInput": {"command": "pytest -q"},
        },
        LogKind.SHELL,
        "pytest -q",
    ),
)


def _plain_tool_block(kind: str, target: str, *detail_lines: str) -> str:
    lines = [f"v {kind}", f"  {target}"]
    lines.extend(f"    {line}" for line in detail_lines)
    return "\n".join(lines)


def _render_plain(state: CockpitState) -> str:
    stream = LogStream(state)
    stream._spin_frame = 0
    return stream._render_entries(state).plain


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_all_workflows_have_phase_titles(workflow_id: str):
    assert workflow_id in PHASE_TITLES
    assert len(PHASE_TITLES[workflow_id]) == len(WORKFLOW_PHASES[workflow_id])


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_phase_titles_mark_running_across_workflows(workflow_id: str):
    state = CockpitState()
    state.configure_workflow(workflow_id)
    titles = PHASE_TITLES[workflow_id]
    for index, title in enumerate(titles):
        sink = CockpitSink(state, cwd="/repo")
        sink.begin_phase(title)
        assert state.phases[index].status == PhaseStatus.RUNNING, (
            f"{workflow_id}/{title} should mark phase[{index}] running"
        )
        for prev in range(index):
            assert state.phases[prev].status == PhaseStatus.DONE
        for nxt in range(index + 1, len(state.phases)):
            assert state.phases[nxt].status == PhaseStatus.PENDING


def test_resume_jump_to_last_phase_marks_prior_done():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.apply_phase_statuses(done_ids=("specify",), skipped_ids=("design", "tasks"))
    sink.begin_phase("Fase Execute")
    assert [phase.status for phase in state.phases] == [
        PhaseStatus.DONE,
        PhaseStatus.SKIPPED,
        PhaseStatus.SKIPPED,
        PhaseStatus.RUNNING,
    ]

@pytest.mark.parametrize("workflow_id", WORKFLOWS)
@pytest.mark.parametrize("sample", TOOL_SAMPLES, ids=[s[0] for s in TOOL_SAMPLES])
def test_tool_kinds_pending_then_gray_block(workflow_id: str, sample: tuple):
    _name, call_payload, expected_kind, target_snip = sample
    state = CockpitState()
    state.configure_workflow(workflow_id)
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase(PHASE_TITLES[workflow_id][0])

    call = dict(call_payload)
    call["toolCallId"] = f"{workflow_id}-{call['toolCallId']}"
    sink.handle_update({"update": call})
    entry = state.entries[-1]
    assert entry.kind == expected_kind
    assert entry.pending is True
    assert target_snip in entry.title or target_snip in entry.detail

    plain = _render_plain(state)
    assert expected_kind.value in plain
    assert target_snip in plain or "carregando" in plain or "…" in plain
    kind_idx = plain.rfind(expected_kind.value)
    assert kind_idx >= 0
    after_kind = plain[kind_idx:]
    assert "\n  " in after_kind

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": call["toolCallId"],
                "status": "in_progress",
            }
        }
    )
    assert state.entries[-1].pending is True

    completed: dict = {
        "sessionUpdate": "tool_call_update",
        "toolCallId": call["toolCallId"],
        "status": "completed",
    }
    if expected_kind == LogKind.SEARCH:
        completed["rawOutput"] = {"totalFiles": 2}
        completed["locations"] = [
            "/repo/.pulse/specs/a.md",
            "/repo/.pulse/specs/b.md",
        ]
    sink.handle_update({"update": completed})
    assert state.entries[-1].pending is False

    plain_done = _render_plain(state)
    assert f"v {expected_kind.value}" in plain_done
    assert target_snip in plain_done
    block_start = plain_done.rfind(f"v {expected_kind.value}")
    block = plain_done[block_start : block_start + 240]
    assert "\n  " in block
    if expected_kind == LogKind.SEARCH:
        assert "2 files" in plain_done or "in .pulse/specs" in plain_done


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_assistant_gutter_across_workflows(workflow_id: str):
    state = CockpitState()
    state.configure_workflow(workflow_id)
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase(PHASE_TITLES[workflow_id][0])
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {
                    "type": "text",
                    "text": "Vou usar `Specify` e marcar **large** no STATE.",
                },
            }
        }
    )
    plain = _render_plain(state)
    assert "Assistente" in plain
    assert "│" in plain
    assert "Specify" in plain
    assert "large" in plain
    assert "**" not in plain
    assert "`" not in plain


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_placeholder_keeps_spinner_until_path(workflow_id: str, tmp_path: Path, monkeypatch):
    import json
    import sqlite3

    session_id = f"sess-{workflow_id}"
    root = tmp_path / "acp-sessions" / session_id
    root.mkdir(parents=True)
    db = root / "store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE blobs (id TEXT PRIMARY KEY, data BLOB)")
    con.commit()
    con.close()
    monkeypatch.setattr("pulse.tui.cursor_store._ACP_SESSIONS", tmp_path / "acp-sessions")
    monkeypatch.setattr("pulse.tui.cursor_store._CHATS", tmp_path / "chats")

    state = CockpitState()
    state.configure_workflow(workflow_id)
    sink = CockpitSink(state, cwd="/repo", session_id=session_id)
    sink.begin_phase(PHASE_TITLES[workflow_id][0])
    tool_id = f"{workflow_id}-placeholder\nfc_1"

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": tool_id,
                "title": "Read File",
                "kind": "read",
                "status": "pending",
                "rawInput": {},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": tool_id,
                "status": "completed",
            }
        }
    )
    assert state.entries[-1].pending is True
    plain = _render_plain(state)
    assert "carregando…" in plain or "…" in plain
    assert "v Read" not in plain or state.entries[-1].pending is True

    con = sqlite3.connect(db)
    blob = {
        "role": "assistant",
        "content": [
            {
                "type": "tool-call",
                "toolCallId": tool_id,
                "toolName": "Read",
                "args": {"path": f"/repo/{workflow_id}/file.md"},
            }
        ],
    }
    con.execute("INSERT INTO blobs(id, data) VALUES (?, ?)", ("1", json.dumps(blob).encode()))
    con.commit()
    con.close()

    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "Seguindo."},
            }
        }
    )
    entry = next(item for item in state.entries if item.tool_id == tool_id)
    assert entry.pending is False
    assert entry.title.endswith("file.md")
    plain_done = _render_plain(state)
    assert "v Read" in plain_done
    assert f"{workflow_id}/file.md" in plain_done
    assert "\n  " in plain_done[plain_done.rfind("v Read") :]


@pytest.mark.parametrize("workflow_id", WORKFLOWS)
def test_textual_render_smoke_all_workflows(workflow_id: str):
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        from pulse.tui.widgets.phase_sidebar import PhaseSidebar

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state = CockpitState()
                state.configure_workflow(workflow_id)
                holder["state"] = state
                holder["sink"] = CockpitSink(state, cwd="/repo")
                with Horizontal():
                    yield PhaseSidebar(state, id="phase-sidebar")
                    yield LogStream(state, id="log-stream")

            def on_mount(self) -> None:
                sink: CockpitSink = holder["sink"]
                sink.begin_phase(PHASE_TITLES[workflow_id][0])
                sink.handle_update(
                    {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {
                                "type": "text",
                                "text": f"Rodando `{workflow_id}` com **cuidado**.",
                            },
                        }
                    }
                )
                for _name, payload, _kind, _snip in TOOL_SAMPLES[:3]:
                    call = dict(payload)
                    call["toolCallId"] = f"smoke-{workflow_id}-{call['toolCallId']}"
                    sink.handle_update({"update": call})
                    sink.handle_update(
                        {
                            "update": {
                                "sessionUpdate": "tool_call_update",
                                "toolCallId": call["toolCallId"],
                                "status": "completed",
                            }
                        }
                    )
                self.query_one(PhaseSidebar).sync_from_state(holder["state"])
                self.query_one(LogStream).sync_from_state(holder["state"], force=True)

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            content = str(app.query_one("#stream-content").render())
            phases = str(app.query_one("#phase-content").render())
            assert "Assistente" in content
            assert "│" in content
            assert "Read" in content
            assert "Edit" in content
            assert "Write" in content
            assert "v Read" in content or "Read" in content
            assert "\n  " in content or "  pulse/" in content or "cli.py" in content
            assert any(phase.label in phases for phase in holder["state"].phases)
            assert "em curso" in phases or "pendente" in phases

    asyncio.run(run())


def test_search_detail_gray_block_layout():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Fase Specify")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "search-layout",
                "title": "Find",
                "kind": "search",
                "rawInput": {"pattern": "dashboard", "path": "/repo/.pulse/specs"},
            }
        }
    )
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "search-layout",
                "status": "completed",
                "rawOutput": {"totalFiles": 3},
                "locations": [
                    "/repo/.pulse/specs/a.md",
                    "/repo/.pulse/specs/b.md",
                    "/repo/.pulse/specs/c.md",
                ],
            }
        }
    )
    plain = _render_plain(state)
    expected_head = _plain_tool_block("Search", "“dashboard”")
    assert expected_head.splitlines()[0] in plain
    assert "“dashboard”" in plain
    assert "in .pulse/specs" in plain
    assert "3 files" in plain
    search_idx = plain.rfind("v Search")
    block = plain[search_idx:]
    lines = [line for line in block.splitlines() if line.strip()][:5]
    assert lines[0].endswith("Search")
    assert lines[1].startswith("  ")
    assert lines[2].startswith("    ")


def test_log_stream_renders_only_selected_step():
    state = CockpitState()
    state.configure_workflow("new-issue")
    sink = CockpitSink(state, cwd="/repo")
    sink.begin_phase("Fase Specify")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "Escrevendo spec"},
            }
        }
    )
    sink.begin_phase("Fase Design")
    sink.handle_update(
        {
            "update": {
                "sessionUpdate": "agent_message_chunk",
                "content": {"type": "text", "text": "Escrevendo design"},
            }
        }
    )
    design_plain = _render_plain(state)
    assert "Escrevendo design" in design_plain
    assert "Escrevendo spec" not in design_plain

    state.select_phase(0)
    spec_plain = _render_plain(state)
    assert "Escrevendo spec" in spec_plain
    assert "Escrevendo design" not in spec_plain
    assert "Nenhuma atividade neste step." not in spec_plain

    state.select_phase(3)
    empty_plain = _render_plain(state)
    assert "Aguardando atividade do agente…" in empty_plain
