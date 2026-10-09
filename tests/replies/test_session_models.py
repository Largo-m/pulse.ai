import pytest

from pulse.replies.session_models import (
    extract_model_labels,
    model_config_option,
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


# The Claude adapter lists models as a `configOptions` entry instead of
# `models.availableModels`; both dialects must read the same.
CLAUDE_SESSION = {
    "configOptions": [
        "not an option",
        {"id": "mode", "options": [{"value": "plan", "name": "Plan"}]},
        {
            "id": "model",
            "options": [
                "loose",
                {"value": "", "name": "No id"},
                {"value": "default", "name": "Default (recommended)"},
                {"value": "opus", "name": "Opus"},
                {"value": "sonnet"},
            ],
        },
    ]
}


def test_the_claude_dialect_lists_its_models_from_the_config_option():
    assert extract_model_labels(CLAUDE_SESSION) == ["Default (recommended)", "Opus", "sonnet"]


def test_the_model_option_is_found_by_category_too():
    session = {"configOptions": [{"id": "x", "category": "model", "options": [{"value": "m"}]}]}

    assert model_config_option(session) == session["configOptions"][0]
    assert extract_model_labels(session) == ["m"]


@pytest.mark.parametrize(
    "session",
    [
        {},
        {"configOptions": "model"},
        {"configOptions": [{"id": "mode"}]},
        {"configOptions": [{"id": "model", "options": "opus"}]},
        {"models": "auto", "configOptions": [{"id": "model", "options": []}]},
        {"models": {"availableModels": "auto"}},
    ],
)
def test_a_reply_without_a_usable_catalog_lists_nothing(session):
    assert extract_model_labels(session) == []
    assert resolve_interview_model_id(session, "opus") is None


def test_native_models_win_over_the_config_option():
    session = {**CLAUDE_SESSION, "models": {"availableModels": [{"modelId": "gpt", "name": "GPT"}]}}

    assert extract_model_labels(session) == ["GPT"]


def test_items_without_an_id_are_skipped_not_the_rest_of_the_list():
    session = {
        "models": {
            "availableModels": [
                "loose",
                {"name": "Nameless"},
                {"modelId": "gpt-5", "name": "GPT 5"},
                {"modelId": "gpt-5", "name": "GPT 5"},
                {"modelId": "composer"},
            ]
        }
    }

    assert extract_model_labels(session) == ["GPT 5", "composer"]
    assert resolve_interview_model_id(session, "composer") == "composer"


@pytest.mark.parametrize("preferred", [None, "", "  ", "auto", "AUTO", "Default", " default "])
def test_any_spelling_of_auto_picks_the_agent_s_auto_model(preferred):
    session = {
        "models": {
            "availableModels": [
                {"name": "No id"},
                {"modelId": "gpt-5", "name": "GPT 5"},
                {"modelId": "AUTO", "name": "Let the agent choose"},
            ]
        }
    }

    assert resolve_interview_model_id(session, preferred) == "AUTO"


def test_auto_is_recognized_by_name_when_the_id_is_opaque():
    session = {"models": {"availableModels": [{"modelId": "x-17", "name": " Auto "}]}}

    assert resolve_interview_model_id(session, "auto") == "x-17"


def test_without_an_auto_model_auto_picks_nothing():
    session = {"models": {"availableModels": [{"modelId": "gpt-5", "name": "GPT 5"}]}}

    assert resolve_interview_model_id(session, None) is None


@pytest.mark.parametrize(
    ("model_id", "shown"),
    [
        (None, ""),
        ("   ", ""),
        ("opus", "Opus"),
        ("AUTO", "Auto"),
        ("Auto-Id", "Auto"),
        ("Default[]", "Auto"),
        ("sonnet[]", "sonnet"),
        ("[]", "[]"),
        ("ab[]", "ab"),
        ("unknown-model", "unknown-model"),
    ],
)
def test_the_display_name_is_the_agent_s_label_or_a_readable_id(model_id, shown):
    assert resolve_model_display_name(CLAUDE_SESSION, model_id) == shown


def test_a_listed_model_without_a_name_is_shown_by_its_id():
    session = {"models": {"availableModels": [{"modelId": "gpt-5"}]}}

    assert resolve_model_display_name(session, "gpt-5") == "gpt-5"
