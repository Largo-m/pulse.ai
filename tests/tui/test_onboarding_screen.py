from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.tui.screens.onboarding import OnboardingScreen
from pulse.tui.theme import COCKPIT_CSS
from tests.tui.conftest import DAEMON_DOWN, cut_the_daemon


def test_onboarding_uses_centered_panel_layout():
    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(OnboardingScreen())

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, OnboardingScreen)
            title = screen.query_one(".onboard-title")
            assert "CONFIGURAR PULSE" in str(title.render())
            assert screen.query_one("#onboard-options")
            assert screen.query_one("#onboard-input")
            assert screen.query_one("#onboard-report")

    asyncio.run(run())


class _Probe:
    """The ACP probe at the daemon's boundary; records what onboarding asked the daemon."""

    calls: list[dict[str, object]] = []
    probe: dict[str, object] = {}

    @classmethod
    def run(cls, *, command: list[str], cwd: str, **_kwargs: object) -> object:
        from pulse.acp.client import AcpProbeResult
        from pulse.runtimes import runtime_for_command

        cls.calls.append({"workspace": Path(cwd), "runtime": runtime_for_command(command).id})
        error = cls.probe.get("error")
        models = cls.probe.get("available_models")
        return AcpProbeResult(
            success=bool(cls.probe.get("ok")),
            message=str(cls.probe.get("message") or ""),
            error=str(error) if error is not None else None,
            available_models=[str(model) for model in models] if isinstance(models, list) else [],
        )


def _probe_on_screen(monkeypatch, tmp_path, *, probe=None, unreachable=False):

    monkeypatch.setattr(_Probe, "calls", [])
    monkeypatch.setattr(_Probe, "probe", probe or {})
    monkeypatch.setattr("pulse.acp.client.probe_acp_connection", _Probe.run)
    monkeypatch.setattr("pulse.api.settings_routes.collect_available_models", lambda *_a, **_k: [])
    outcome: dict[str, object] = {}

    async def run() -> None:
        from textual.app import App
        from textual.widgets import Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(OnboardingScreen())

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, OnboardingScreen)
            screen._workspace = tmp_path
            if unreachable:
                cut_the_daemon(monkeypatch)
            screen._run_acp_probe()
            await app.workers.wait_for_complete()
            await pilot.pause()
            outcome["step"] = screen._step
            outcome["report"] = str(screen.query_one("#onboard-report", Static).render())
            outcome["runtime"] = screen._chosen().id

    asyncio.run(run())
    return outcome


def test_onboarding_probes_the_chosen_runtime_through_the_engine(monkeypatch, tmp_path):
    """The TUI is a thin client: the ACP probe runs in the daemon, never in the TUI process."""
    outcome = _probe_on_screen(
        monkeypatch,
        tmp_path,
        probe={"ok": False, "message": "falhou", "error": "auth", "available_models": ["m1"]},
    )

    assert _Probe.calls == [{"workspace": tmp_path, "runtime": outcome["runtime"]}]
    assert outcome["step"] == "acp_fail"
    assert outcome["report"] == "auth"


def test_an_unreachable_engine_is_a_failed_probe_the_user_can_skip(monkeypatch, tmp_path):
    """Onboarding must not crash when the daemon does not answer; it offers to continue instead."""
    outcome = _probe_on_screen(monkeypatch, tmp_path, unreachable=True)

    assert _Probe.calls == []
    assert outcome["step"] == "acp_fail"
    assert outcome["report"] == DAEMON_DOWN
