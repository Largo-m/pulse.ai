import pytest


@pytest.fixture(autouse=True)
def _screens_reach_an_in_process_daemon(in_process_daemon: object) -> None:
    """A screen never starts a real daemon, and never touches SQLite behind its back."""
