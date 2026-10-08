from __future__ import annotations

from pathlib import Path

import pytest

from tests.orchestrator.harness import EngineHarness


@pytest.fixture
def wired(tmp_path: Path) -> EngineHarness:
    """Engine on in-memory ports: a scripted agent, storage, workspace and profiles."""
    return EngineHarness(tmp_path)
