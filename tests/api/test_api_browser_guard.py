from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from pulse.api.app import create_app
from pulse.daemon.runs import RunManager


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(RunManager()), base_url="http://127.0.0.1")


def test_cross_site_post_from_a_browser_never_reaches_a_route(monkeypatch, client, tmp_path):
    """A web page can send a no-cors POST to 127.0.0.1 without any preflight.

    CORS only hides the response; the route would still run. `acp-probe` takes
    only query parameters, so a page the user happens to visit could make the
    daemon spawn an agent CLI in a directory of its choosing.
    """
    spawned: list[object] = []
    monkeypatch.setattr(
        "pulse.acp.client.probe_acp_connection", lambda **kwargs: spawned.append(kwargs)
    )

    response = client.post(
        "/api/doctor/acp-probe",
        params={"workspace": str(tmp_path), "runtime": "claude"},
        headers={"Origin": "https://attacker.example"},
    )

    assert response.status_code == 403
    assert spawned == []


@pytest.mark.parametrize("origin", ["null", "http://127.0.0.1:8787", "http://localhost"])
def test_any_browser_origin_is_refused_even_a_local_one(client, origin):
    """Pulse has no browser UI, so no legitimate caller sends `Origin`.

    A page served from another localhost port is as untrusted as a remote one.
    """
    response = client.get("/api/status", headers={"Origin": origin})

    assert response.status_code == 403


def test_the_cli_client_without_origin_is_served(client):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_responses_carry_headers_that_keep_a_browser_from_rendering_them(client):
    """Defense in depth: a JSON API response is never sniffed, framed or referred."""
    response = client.get("/api/status")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"


def test_a_refused_request_also_carries_the_security_headers(client):
    response = client.get("/api/status", headers={"Origin": "https://attacker.example"})

    assert response.headers["x-content-type-options"] == "nosniff"
