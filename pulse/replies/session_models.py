"""The model catalog an agent advertises in its `session/new` reply.

Plain ACP lists `models.availableModels`; the Claude adapter exposes the model
as a config option instead. Both dialects are read here, so the session runner
and every runtime parse the same reply the same way.
"""

from __future__ import annotations

from collections.abc import Mapping

_AUTO_ALIASES = {"auto", "default"}
MODEL_CONFIG_ID = "model"

Session = Mapping[str, object]
ModelItem = Mapping[str, object]


def model_config_option(session: Session) -> Mapping[str, object] | None:
    """Config option that carries the model list."""
    options = session.get("configOptions")
    if not isinstance(options, list):
        return None
    for option in options:
        if not isinstance(option, dict):
            continue
        if option.get("id") == MODEL_CONFIG_ID or option.get("category") == MODEL_CONFIG_ID:
            return option
    return None


def _is_auto_model(model_id: str, name: str) -> bool:
    return name.strip().lower() in _AUTO_ALIASES or model_id.strip().lower() in _AUTO_ALIASES


def _model_fields(item: ModelItem) -> tuple[str, str]:
    model_id = str(item.get("modelId", ""))
    name = str(item.get("name", model_id))
    return model_id, name


def _native_models(session: Session) -> list[ModelItem]:
    models = session.get("models", {})
    if not isinstance(models, dict):
        return []
    available = models.get("availableModels", [])
    if not isinstance(available, list):
        return []
    return [item for item in available if isinstance(item, dict)]


def _config_option_models(session: Session) -> list[ModelItem]:
    """Models exposed as a config option (Claude adapter dialect)."""
    option = model_config_option(session)
    if option is None:
        return []
    values = option.get("options")
    if not isinstance(values, list):
        return []
    items: list[ModelItem] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        model_id = str(value.get("value", ""))
        if not model_id:
            continue
        items.append({"modelId": model_id, "name": str(value.get("name") or model_id)})
    return items


def _available_models(session: Session) -> list[ModelItem]:
    native = _native_models(session)
    if native:
        return native
    return _config_option_models(session)


def _find_auto_model_id(available: list[ModelItem]) -> str | None:
    for item in available:
        model_id, name = _model_fields(item)
        if model_id and _is_auto_model(model_id, name):
            return model_id
    return None


def extract_model_labels(session: Session) -> list[str]:
    result: list[str] = []
    for item in _available_models(session):
        model_id, name = _model_fields(item)
        if not model_id:
            continue
        label = str(name or model_id)
        if label not in result:
            result.append(label)
    return result


def resolve_model_display_name(session: Session, model_id: str | None) -> str:
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
    session: Session,
    preferred_model: str | None,
) -> str | None:
    available = _available_models(session)
    if not available:
        return None

    # A blank preference is "auto": stripped to "", it would match every model.
    preferred_lower = ((preferred_model or "").strip() or "auto").lower()

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


resolve_model_id = resolve_interview_model_id
