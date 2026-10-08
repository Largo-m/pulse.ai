from pulse.replies.session_models import (
    extract_model_labels,
    resolve_interview_model_id,
    resolve_model_display_name,
)


def test_extract_model_labels_returns_all_available():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "auto-id", "name": "Auto"},
                {"modelId": "gpt-id", "name": "gpt-5.5"},
                {"modelId": "sonnet-id", "name": "claude-sonnet-4-6"},
                {"modelId": "composer-id", "name": "composer-2.5"},
                {"modelId": "opus-id", "name": "claude-opus-4.8"},
            ]
        }
    }
    assert extract_model_labels(session) == [
        "Auto",
        "gpt-5.5",
        "claude-sonnet-4-6",
        "composer-2.5",
        "claude-opus-4.8",
    ]


def test_resolve_model_display_name_prefers_human_label():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "default[]", "name": "Auto"},
                {"modelId": "gpt-5.5[context=272k]", "name": "gpt-5.5"},
            ]
        }
    }
    assert resolve_model_display_name(session, "default[]") == "Auto"
    assert resolve_model_display_name(session, "gpt-5.5[context=272k]") == "gpt-5.5"
    assert resolve_model_display_name({}, "default[]") == "Auto"


def test_resolve_interview_model_id_uses_auto_when_config_is_auto():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "auto-id", "name": "Auto"},
                {"modelId": "sonnet-id", "name": "claude-sonnet-4-6"},
            ]
        }
    }
    assert resolve_interview_model_id(session, "Auto") == "auto-id"
    assert resolve_interview_model_id(session, None) == "auto-id"


def test_resolve_interview_model_id_honors_explicit_preference():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "gpt-id", "name": "gpt-5.5"},
                {"modelId": "sonnet-id", "name": "claude-sonnet-4-6"},
            ]
        }
    }
    assert resolve_interview_model_id(session, "gpt-5.5") == "gpt-id"


def test_resolve_interview_model_id_honors_composer_preference():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "composer-id", "name": "composer-2.5"},
                {"modelId": "sonnet-id", "name": "claude-sonnet-4-6"},
            ]
        }
    }
    assert resolve_interview_model_id(session, "composer-2.5") == "composer-id"


def test_resolve_interview_model_id_returns_none_when_preference_not_available():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "gpt-id", "name": "gpt-5.5"},
            ]
        }
    }
    assert resolve_interview_model_id(session, "composer-2.5") is None
