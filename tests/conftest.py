from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_pulse_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULSE_DB", str(tmp_path / "pulse.db"))
