"""The TUI's gateway to the daemon: typed answers, and a failure the screens can show.

A daemon that cannot be reached must surface as `EngineUnavailable`, never as a
transport exception that would crash a screen; an unknown id is `None`, not an error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.client.engine_client import EngineClient
from pulse.tui import engine


def _refused(_self: object) -> None:
    raise RuntimeError("could not connect to pulse-engine")


def test_an_unreachable_daemon_is_engine_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(EngineClient, "ensure_daemon", _refused)

    with pytest.raises(engine.EngineUnavailable, match="could not connect"):
        engine.history(tmp_path)


def test_a_daemon_error_is_engine_unavailable(monkeypatch, tmp_path: Path) -> None:
    def broken(*_args: object) -> list:
        raise OSError("disk gone")

    monkeypatch.setattr("pulse.history.catalog.HistoryCatalog.list_items", broken)

    with pytest.raises(engine.EngineUnavailable):
        engine.history(tmp_path)


def test_unknown_ids_are_none(tmp_path: Path) -> None:
    assert engine.history_item(tmp_path, "nope") is None
    assert engine.run_log("nope") is None
    assert engine.worktree_state(tmp_path, "nope") is None
    assert engine.delete_history_item(tmp_path, "nope") is False
    assert engine.remove_worktree(tmp_path, "nope") is False
    assert engine.workflow("nope") is None


def test_workflows_come_back_with_their_steps_in_order() -> None:
    from tests.conftest import make_workflow

    make_workflow("demo", steps=[("plan", "Planejar"), ("run", "Implementar")], label="Demo")

    shape = engine.workflow("demo")

    assert shape is not None
    assert (shape.label, shape.steps) == ("Demo", (("plan", "Planejar"), ("run", "Implementar")))
