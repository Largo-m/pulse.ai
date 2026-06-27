from unittest.mock import patch

from pathlib import Path

from pulse.terminal.prompts import collect_available_models


def test_collect_available_models_from_acp(tmp_path: Path):
    resolved_agents = {
        "cursor": type(
            "Agent",
            (),
            {
                "acp_command": ["agent", "acp"],
                "models": ["Auto"],
            },
        )(),
    }
    fake_resolved = type(
        "Resolved",
        (),
        {
            "model": "gpt-5.5",
            "workspace_dir": tmp_path,
            "agents": resolved_agents,
        },
    )()

    acp_models = [f"model-{index}" for index in range(12)]

    with patch("pulse.terminal.prompts.resolve_config", return_value=fake_resolved):
        with patch(
            "pulse.terminal.prompts.fetch_acp_available_models",
            return_value=acp_models,
        ):
            models = collect_available_models(tmp_path)

    assert models == acp_models + ["gpt-5.5"]


def test_collect_available_models_falls_back_to_defaults(tmp_path: Path):
    fake_resolved = type(
        "Resolved",
        (),
        {
            "model": "auto",
            "workspace_dir": tmp_path,
            "agents": {},
        },
    )()

    with patch("pulse.terminal.prompts.resolve_config", return_value=fake_resolved):
        with patch("pulse.terminal.prompts.fetch_acp_available_models", return_value=[]):
            models = collect_available_models(tmp_path)

    assert len(models) >= 4
