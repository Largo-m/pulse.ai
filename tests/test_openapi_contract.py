"""O contrato em `contracts/openapi.yaml` lista as rotas que o engine serve."""

from __future__ import annotations

import re
from pathlib import Path

from pulse.api.app import create_app

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "openapi.yaml"
_PATH = re.compile(r"^  (/\S+):\s*$")
_METHOD = re.compile(r"^    (get|post|put|patch|delete):\s*$")


def _contract_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    current = ""
    for line in CONTRACT.read_text(encoding="utf-8").splitlines():
        path = _PATH.match(line)
        if path:
            current = path.group(1)
            continue
        method = _METHOD.match(line)
        if method and current:
            routes.add((method.group(1), current))
    return routes


def test_every_served_route_is_in_the_contract_and_back():
    served = {
        (method.lower(), path)
        for path, operations in create_app().openapi()["paths"].items()
        for method in operations
    }
    assert served == _contract_routes()
