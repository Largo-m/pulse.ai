from pulse.acp.models import resolve_interview_model_id


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
