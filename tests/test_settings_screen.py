from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.config.project_config import init_project_config, load_project_config
from pulse.store.agent_settings import upsert_agent_settings
from pulse.tui.screens.settings import SettingsScreen
from pulse.tui.theme import COCKPIT_CSS


def test_settings_shows_saved_model_after_select(tmp_path: Path):
    init_project_config(tmp_path)
    project = load_project_config(tmp_path)
    assert project is not None

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(SettingsScreen(cwd=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, SettingsScreen)
            title = screen.query_one(".settings-title")
            assert "CONFIGURAÇÕES" in str(title.render())
            screen._show_pulse_agents()
            await pilot.pause()
            specify = next(
                agent_id
                for agent_id, _ in [
                    (opt.id, str(opt.prompt))
                    for opt in screen.query_one(OptionList)._options
                    if opt.id and str(opt.id).startswith("workflow:")
                ]
                if agent_id.endswith("specify")
            )
            screen._workflow_id = specify.split(":", 1)[1]
            upsert_agent_settings(project.project_id, screen._workflow_id, model="composer-2.5")
            screen._show_workflow_fields()
            await pilot.pause()
            labels = [str(opt.prompt) for opt in screen.query_one(OptionList)._options]
            assert any("Modelo — composer-2.5" in label for label in labels)
            screen._show_pulse_agents()
            await pilot.pause()
            labels = [str(opt.prompt) for opt in screen.query_one(OptionList)._options]
            assert any("composer-2.5" in label and "Specify" in label for label in labels)

    asyncio.run(run())


def test_settings_model_picker_uses_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    init_project_config(tmp_path)
    project = load_project_config(tmp_path)
    assert project is not None
    seen: dict[str, str | None] = {}

    def fake_models(cwd: Path, agent_name: str | None = None) -> list[str]:
        seen["runtime"] = agent_name
        if agent_name == "claude":
            return ["claude-opus-4.8"]
        return ["gpt-5.5", "composer-2.5"]

    monkeypatch.setattr("pulse.tui.screens.settings.collect_available_models", fake_models)

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(SettingsScreen(cwd=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, SettingsScreen)
            upsert_agent_settings(project.project_id, "specify", runtime="claude")
            screen._workflow_id = "specify"
            screen._load_models(for_workflow=True)
            for _ in range(20):
                await pilot.pause(0.05)
                labels = [str(opt.prompt) for opt in screen.query_one(OptionList)._options]
                if any(label.startswith("claude-opus") for label in labels):
                    break
            labels = [str(opt.prompt) for opt in screen.query_one(OptionList)._options]
            assert seen["runtime"] == "claude"
            assert any("claude-opus-4.8" in label for label in labels)
            assert not any("gpt-5.5" in label for label in labels)

    asyncio.run(run())
