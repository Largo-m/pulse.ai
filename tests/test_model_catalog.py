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
