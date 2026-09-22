from __future__ import annotations

import json


def dump_list(values: list[str]) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def load_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]
