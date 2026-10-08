from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from pulse.tui.screens.onboarding import OnboardingScreen
from pulse.tui.theme import COCKPIT_CSS


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


class _FakeEngine:
    """Stands in for the daemon at the HTTP boundary; records what onboarding asked."""

    calls: list[dict[str, object]] = []
    probe: dict[str, object] = {}
    unreachable = False

    def __init__(self, **_kwargs: object) -> None:
        pass

    def ensure_daemon(self) -> None:
        if self.unreachable:
            raise RuntimeError("Não foi possível conectar ao pulse-engine")

    def acp_probe(self, *, workspace, runtime: str) -> dict[str, object]:
        self.calls.append({"workspace": workspace, "runtime": runtime})
        return self.probe

    def close(self) -> None:
        pass


def _probe_on_screen(monkeypatch, tmp_path, *, probe=None, unreachable=False):
    monkeypatch.setattr(_FakeEngine, "calls", [])
    monkeypatch.setattr(_FakeEngine, "probe", probe or {})
    monkeypatch.setattr(_FakeEngine, "unreachable", unreachable)
    monkeypatch.setattr("pulse.tui.screens.onboarding.EngineClient", _FakeEngine)
    monkeypatch.setattr(
        "pulse.tui.screens.onboarding.collect_available_models", lambda *_a, **_k: []
    )
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
            screen._run_acp_probe()
            await app.workers.wait_for_complete()
            await pilot.pause()
            outcome["step"] = screen._step
            outcome["models"] = list(screen._models)
            outcome["report"] = str(screen.query_one("#onboard-report", Static).render())
            outcome["runtime"] = screen._runtime.id

    asyncio.run(run())
    return outcome


def test_onboarding_probes_the_chosen_runtime_through_the_engine(monkeypatch, tmp_path):
    """The TUI is a thin client: the ACP probe runs in the daemon, never in the TUI process."""
    outcome = _probe_on_screen(
        monkeypatch,
        tmp_path,
        probe={"ok": False, "message": "falhou", "error": "auth", "available_models": ["m1"]},
    )

    assert _FakeEngine.calls == [{"workspace": tmp_path, "runtime": outcome["runtime"]}]
    assert outcome["step"] == "acp_fail"
    assert outcome["models"] == ["m1"]
    assert outcome["report"] == "auth"


def test_an_unreachable_engine_is_a_failed_probe_the_user_can_skip(monkeypatch, tmp_path):
    """Onboarding must not crash when the daemon can't start; it offers to continue instead."""
    outcome = _probe_on_screen(monkeypatch, tmp_path, unreachable=True)

    assert _FakeEngine.calls == []
    assert outcome["step"] == "acp_fail"
    assert outcome["report"] == "Não foi possível conectar ao pulse-engine"
