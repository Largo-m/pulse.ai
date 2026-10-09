"""The TCP listener answers only whoever can read the daemon's token.

`127.0.0.1` keeps the network out but not other users of the same machine; the
Unix socket is `0600`, and the token in the `0600` meta file is TCP's
equivalent. Without it any local account could change `permission_policy` and
start runs with the daemon owner's permissions.
"""

from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.api.token_guard import UNAUTHORIZED, TokenGuard
from pulse.daemon.server import listener_configs

TOKEN = secrets.token_urlsafe()
BASE_URL = "http://127.0.0.1"


@pytest.fixture
def tcp_client() -> TestClient:
    return TestClient(TokenGuard(create_app(), TOKEN), base_url=BASE_URL)


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": f"Basic {TOKEN}"},
        {"Authorization": TOKEN},
        {"Authorization": f"Bearer {TOKEN}x"},
        {"Authorization": "Bearer "},
    ],
    ids=["missing", "wrong", "other-scheme", "no-scheme", "longer", "empty"],
)
def test_a_request_without_the_daemon_token_is_refused(tcp_client: TestClient, headers):
    response = tcp_client.get("/api/status", headers=headers)

    assert response.status_code == UNAUTHORIZED
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "ok" not in response.json()


def test_a_refused_request_never_reaches_the_route(tcp_client: TestClient):
    """The point is that the route does not run, not just that its answer is hidden."""
    authorized = {"Authorization": f"Bearer {TOKEN}"}
    before = tcp_client.get("/api/config", headers=authorized).json()

    response = tcp_client.patch("/api/config/global", json={"permission_policy": "auto_approve"})

    assert response.status_code == UNAUTHORIZED
    assert tcp_client.get("/api/config", headers=authorized).json() == before


def test_the_daemon_token_is_accepted(tcp_client: TestClient):
    response = tcp_client.get("/api/status", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_the_scheme_is_case_insensitive(tcp_client: TestClient):
    """RFC 9110 §11.1: the auth scheme is case-insensitive; the token is not."""
    ok = tcp_client.get("/api/status", headers={"Authorization": f"bearer {TOKEN}"})
    wrong_case = tcp_client.get("/api/status", headers={"Authorization": f"Bearer {TOKEN.upper()}"})

    assert ok.status_code == 200
    assert wrong_case.status_code == UNAUTHORIZED


def test_an_empty_token_is_rejected_at_construction():
    """An empty token would make `Bearer ` a valid credential."""
    with pytest.raises(ValueError, match="token"):
        TokenGuard(create_app(), "")


def test_the_daemon_guards_tcp_and_leaves_the_private_socket_open(tmp_path):
    """The socket is already `0600`; its clients never read the meta file."""
    app = create_app()

    tcp, uds = listener_configs(
        app, host="127.0.0.1", port=0, socket_path=tmp_path / "d.sock", token=TOKEN
    )

    tcp_status = TestClient(tcp.app, base_url=BASE_URL).get("/api/status")
    uds_status = TestClient(uds.app, base_url="http://pulse").get("/api/status")
    assert tcp_status.status_code == UNAUTHORIZED
    assert uds_status.status_code == 200
    assert (tcp.host, tcp.uds) == ("127.0.0.1", None)
    assert uds.uds == str(tmp_path / "d.sock")
