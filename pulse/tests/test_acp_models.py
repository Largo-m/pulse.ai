from pulse.acp.models import is_unsupported_interview_model, resolve_interview_model_id


def test_is_unsupported_interview_model():
    assert not is_unsupported_interview_model(model_id="auto", name="Auto")
    assert is_unsupported_interview_model(model_id="composer-2.5", name="Composer 2.5")
    assert not is_unsupported_interview_model(model_id="claude-sonnet-4-6", name="Claude Sonnet")


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


def test_resolve_interview_model_id_honors_explicit_supported_preference():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "gpt-id", "name": "gpt-5.5"},
                {"modelId": "sonnet-id", "name": "claude-sonnet-4-6"},
            ]
        }
    }
    assert resolve_interview_model_id(session, "gpt-5.5") == "gpt-id"


def test_resolve_interview_model_id_skips_composer_preference():
    session = {
        "models": {
            "availableModels": [
                {"modelId": "composer-id", "name": "composer-2.5"},
                {"modelId": "sonnet-id", "name": "claude-sonnet-4-6"},
            ]
        }
    }
    assert resolve_interview_model_id(session, "composer-2.5") == "sonnet-id"
