from __future__ import annotations

from typing import Any


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


def extract_model_labels(session: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for item in _available_models(session):
        model_id, name = _model_fields(item)
        if not model_id:
            continue
        label = str(name or model_id)
        if label not in result:
            result.append(label)
    return result


def resolve_model_display_name(session: dict[str, Any], model_id: str | None) -> str:
    mid = (model_id or "").strip()
    if not mid:
        return ""
    for item in _available_models(session):
        item_id, name = _model_fields(item)
        if item_id == mid:
            label = str(name or item_id).strip()
            if label:
                return label
    if mid.lower() in {"default[]", "auto", "auto-id"}:
        return "Auto"
    if mid.endswith("[]") and mid[:-2]:
        return mid[:-2]
    return mid


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
        if preferred_lower in haystack:
            return model_id

    return None
