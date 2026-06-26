from __future__ import annotations

from typing import Any

_UNSUPPORTED_MARKERS = ("composer",)

_PREFERRED_MARKERS = (
    "claude-sonnet",
    "claude-opus",
    "gpt-5",
    "gpt-4",
    "claude-4",
)


def is_unsupported_interview_model(*, model_id: str, name: str = "") -> bool:
    combined = f"{model_id} {name}".lower()
    return any(marker in combined for marker in _UNSUPPORTED_MARKERS)


def _is_auto_model(model_id: str, name: str) -> bool:
    return name.strip().lower() == "auto" or model_id.strip().lower() == "auto"


def _model_fields(item: dict[str, Any]) -> tuple[str, str]:
    model_id = str(item.get("modelId", ""))
    name = str(item.get("name", model_id))
    return model_id, name


def _available_models(session: dict[str, Any]) -> list[dict[str, Any]]:
    models = session.get("models", {})
    available = models.get("availableModels", [])
    if not isinstance(available, list):
        return []
    return [item for item in available if isinstance(item, dict)]


def _find_auto_model_id(available: list[dict[str, Any]]) -> str | None:
    for item in available:
        model_id, name = _model_fields(item)
        if model_id and _is_auto_model(model_id, name):
            return model_id
    return None


def resolve_interview_model_id(
    session: dict[str, Any],
    preferred_model: str | None,
) -> str | None:
    available = _available_models(session)
    if not available:
        return None

    preferred = (preferred_model or "auto").strip()
    preferred_lower = preferred.lower()

    if preferred_lower in {"auto", "default"}:
        return _find_auto_model_id(available)

    for item in available:
        model_id, name = _model_fields(item)
        if not model_id:
            continue
        haystack = f"{model_id} {name}".lower()
        if preferred_lower in haystack and not is_unsupported_interview_model(
            model_id=model_id,
            name=name,
        ):
            return model_id

    for marker in _PREFERRED_MARKERS:
        for item in available:
            model_id, name = _model_fields(item)
            if not model_id:
                continue
            haystack = f"{model_id} {name}".lower()
            if marker in haystack and not is_unsupported_interview_model(
                model_id=model_id,
                name=name,
            ):
                return model_id

    for item in available:
        model_id, name = _model_fields(item)
        if model_id and not is_unsupported_interview_model(model_id=model_id, name=name):
            return model_id

    return None
