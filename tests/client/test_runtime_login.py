"""The runtime's login runs in the user's terminal; its exit code is the only answer."""

from __future__ import annotations

import sys

from pulse.client.runtime_login import LOGIN_FAILED, run_login


def test_the_login_s_exit_code_is_returned() -> None:
    assert run_login((sys.executable, "-c", "raise SystemExit(3)")) == 3


def test_a_runtime_without_a_login_command_fails_the_login() -> None:
    assert run_login(()) == LOGIN_FAILED


def test_a_login_binary_that_is_not_installed_fails_the_login(tmp_path) -> None:
    assert run_login((str(tmp_path / "no-such-cli"), "login")) == LOGIN_FAILED
