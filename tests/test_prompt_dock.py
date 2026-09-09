from __future__ import annotations

import asyncio
from concurrent.futures import Future

import pytest

pytest.importorskip("textual")

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.adapters.prompt_bridge import PromptKind, PromptRequest
from pulse.tui.screens.cockpit import CockpitScreen
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.prompt_dock import PromptDock


def _select_request(future: Future[object | None] | None = None) -> PromptRequest:
    return PromptRequest(
        kind=PromptKind.SELECT,
        title="Questionário",
        prompt="Qual o tamanho da mudança?",
        choices=[("small", "small"), ("medium", "medium"), ("large", "large")],
        future=future,
    )


def test_prompt_stays_inside_log_stream_while_tools_keep_rendering():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal
        from textual.screen import ModalScreen
        from textual.widgets import OptionList

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                screen = CockpitScreen("fix-bug", "demo")
                holder["screen"] = screen
                with Horizontal(id="cockpit-body"):
                    yield LogStream(screen.state, id="log-stream")

            def on_mount(self) -> None:
                screen = holder["screen"]
                screen.sink.begin_phase("Fase 1 — Planejando quick task")
                screen.sink.handle_update(
                    {
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": "t1",
                            "title": "Read File",
                            "kind": "read",
                            "rawInput": {"path": "/repo/pulse/cli.py"},
                        }
                    }
                )
                log = self.query_one(LogStream)
                log.sync_from_state(screen.state, force=True)
                future: Future[object | None] = Future()
                holder["future"] = future
                log.show_prompt(_select_request(future), future.set_result)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            log = app.query_one(LogStream)
            dock = log.query_one(PromptDock)
            slot = log.query_one("#prompt-slot")
            assert dock.is_mounted
            assert slot.display is True
            assert dock.parent is slot
            assert not any(isinstance(screen, ModalScreen) for screen in app.screen_stack)
            content = str(app.query_one("#stream-content").render())
            assert "Read" in content
            assert "Qual o tamanho da mudança?" in str(dock.query_one(".prompt-text").render())

            holder["screen"].sink.handle_update(
                {
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": "t2",
                        "title": "Write File",
                        "kind": "write",
                        "rawInput": {"path": "/repo/.pulse/specs/plan.md"},
                    }
                }
            )
            log.sync_from_state(holder["screen"].state, force=True)
            content = str(app.query_one("#stream-content").render())
            assert "Write" in content
            assert log.query_one(PromptDock).is_mounted

            options = app.query_one("#prompt-options", OptionList)
            assert options.option_count == 3
            assert options.size.height >= 3
            assert dock.size.height > 1
            assert options.region.y < 40
            options.highlighted = 1
            options.action_select()
            await pilot.pause()
            assert holder["future"].result(timeout=1) == "medium"
            await pilot.pause()
            assert list(log.query(PromptDock)) == []
            assert slot.display is False
            content = str(app.query_one("#stream-content").render())
            assert "Pergunta" in content
            assert "Qual o tamanho da mudança?" in content
            assert "Você" in content
            assert "medium" in content

    asyncio.run(run())


def test_select_options_are_visible_in_compact_terminal():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import OptionList

        choices = [
            ("A", "A) Produto / plataforma com usuários"),
            ("B", "B) API / serviço backend"),
            ("C", "C) Biblioteca / pacote interno"),
            ("D", "D) Automação / script / CLI"),
            ("E", "E) Outro (descreva)"),
        ]

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state_screen = CockpitScreen("setup-project", "demo")
                yield LogStream(state_screen.state, id="log-stream")

            def on_mount(self) -> None:
                future: Future[object | None] = Future()
                self.query_one(LogStream).show_prompt(
                    PromptRequest(
                        kind=PromptKind.SELECT,
                        title="Preciso de algumas informações antes de continuar. · 1/4",
                        prompt="1. O que você está construindo?",
                        choices=choices,
                        future=future,
                    ),
                    future.set_result,
                )

        app = Harness()
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            dock = app.query_one(PromptDock)
            options = app.query_one("#prompt-options", OptionList)
            assert options.option_count == 5
            assert dock.size.height >= 8
            assert options.size.height >= 5
            assert options.region.bottom <= 24
            svg = app.export_screenshot()
            assert "construindo" in svg
            assert "Produto" in svg
            assert "API" in svg
            assert "Biblioteca" in svg
            assert "Outro" in svg

    asyncio.run(run())


def test_cockpit_poll_opens_prompt_dock_not_modal(monkeypatch):
    async def run() -> None:
        from textual.app import App
        from textual.screen import ModalScreen

        monkeypatch.setattr(CockpitScreen, "_run_workflow", lambda self: None)

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(CockpitScreen("fix-bug", "demo"))

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, CockpitScreen)
            future: Future[object | None] = Future()
            screen.bridge._queue.put(_select_request(future))
            await pilot.pause(0.25)
            log = screen.query_one(LogStream)
            assert log.query_one(PromptDock).is_mounted
            assert not any(isinstance(item, ModalScreen) for item in app.screen_stack)
            assert screen._prompt_open is True

    asyncio.run(run())


def test_prompt_text_submit_and_confirm_cancel():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Button, Input

        holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                state_screen = CockpitScreen("new-issue", "demo")
                holder["sink"] = CockpitSink(state_screen.state, cwd="/repo")
                yield LogStream(state_screen.state, id="log-stream")

            def on_mount(self) -> None:
                sink: CockpitSink = holder["sink"]
                sink.begin_phase("Fase Specify")
                self.query_one(LogStream).sync_from_state(sink._state, force=True)

        app = Harness()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            log = app.query_one(LogStream)
            text_future: Future[object | None] = Future()
            log.show_prompt(
                PromptRequest(
                    kind=PromptKind.TEXT,
                    title="Questionário",
                    prompt="Descreva o problema",
                    choices=[],
                    default="kpi",
                    future=text_future,
                ),
                text_future.set_result,
            )
            await pilot.pause()
            field = app.query_one("#prompt-input", Input)
            assert field.value == "kpi"
            field.value = "dashboard hardcoded"
            await field.action_submit()
            await pilot.pause()
            assert text_future.result(timeout=1) == "dashboard hardcoded"
            await pilot.pause()
            assert list(log.query(PromptDock)) == []

            confirm_future: Future[object | None] = Future()
            log.show_prompt(
                PromptRequest(
                    kind=PromptKind.CONFIRM,
                    title="Permissão",
                    prompt="Permitir escrita?",
                    choices=[],
                    default=True,
                    future=confirm_future,
                ),
                confirm_future.set_result,
            )
            await pilot.pause()
            app.query_one("#no", Button).press()
            await pilot.pause()
            assert confirm_future.result(timeout=1) is False

    asyncio.run(run())
