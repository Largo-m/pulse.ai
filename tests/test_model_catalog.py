from __future__ import annotations

from pulse.config.model_catalog import DEFAULT_MODELS, collect_available_models


def test_collect_available_models_falls_back_to_defaults(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "pulse.config.model_catalog.fetch_acp_available_models",
        lambda **kwargs: [],
    )
    models = collect_available_models(tmp_path)
    assert models
    assert "Auto" in models or "auto" in models or models == list(DEFAULT_MODELS)


def test_collect_available_models_uses_acp(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "pulse.config.model_catalog.fetch_acp_available_models",
        lambda **kwargs: ["claude-sonnet-4-6", "gpt-5.5"],
    )
    models = collect_available_models(tmp_path)
    assert "claude-sonnet-4-6" in models
    assert "gpt-5.5" in models


def test_collect_available_models_keeps_only_the_runtime(monkeypatch, tmp_path):
    from pulse.config.global_config import mark_onboarding_complete

    mark_onboarding_complete(
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="composer-2.5",
        permission_policy="ask",
        acp_test_passed=True,
        path=tmp_path / "pulse.db",
    )

    def fake_models(*, command, cwd, timeout_seconds=30.0):
        if command[:1] == ["claude-code"]:
            return ["claude-opus-4.8", "claude-sonnet-4-6"]
        return ["Auto", "gpt-5.5", "composer-2.5"]

    monkeypatch.setattr("pulse.config.model_catalog.fetch_acp_available_models", fake_models)
    cursor_models = collect_available_models(tmp_path, agent_name="cursor")
    claude_models = collect_available_models(tmp_path, agent_name="claude")
    assert "claude-opus-4.8" not in cursor_models
    assert "claude-sonnet-4-6" not in cursor_models
    assert "gpt-5.5" not in claude_models
    assert "composer-2.5" not in claude_models
    assert "Auto" in cursor_models
    assert "claude-opus-4.8" in claude_models
