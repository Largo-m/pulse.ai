from pulse.config.agents import default_acp_command, default_global_agents
from pulse.replies.session_models import extract_model_labels
from pulse.runtimes import all_runtimes, get_runtime, runtime_for_command

CURSOR_SESSION = {
    "modes": {
        "currentModeId": "agent",
        "availableModes": [{"id": "agent", "name": "Agent"}],
    },
    "models": {
        "availableModels": [
            {"modelId": "auto-id", "name": "Auto"},
            {"modelId": "gpt-id", "name": "gpt-5.5"},
        ]
    },
}

CLAUDE_SESSION = {
    "modes": {
        "currentModeId": "default",
        "availableModes": [
            {"id": "default", "name": "Manual"},
            {"id": "acceptEdits", "name": "Accept edits"},
            {"id": "plan", "name": "Plan"},
            {"id": "auto", "name": "Auto"},
            {"id": "bypassPermissions", "name": "Bypass permissions"},
        ],
    },
    "configOptions": [
        {"id": "mode", "category": "mode", "currentValue": "default", "options": []},
        {
            "id": "model",
            "category": "model",
            "currentValue": "opus[1m]",
            "options": [
                {"value": "default", "name": "Default (recommended)"},
                {"value": "opus[1m]", "name": "Opus 5.5"},
                {"value": "sonnet", "name": "Sonnet 5"},
            ],
        },
    ],
}


def test_registry_exposes_both_runtimes():
    assert {runtime.id for runtime in all_runtimes()} == {"cursor", "claude", "codex"}


def test_claude_runs_through_the_npm_adapter():
    command = get_runtime("claude").acp_command
    assert command[0] == "npx"
    assert command[-1].startswith("@agentclientprotocol/claude-agent-acp@")


def test_cursor_speaks_acp_natively():
    assert get_runtime("cursor").acp_command == ["agent", "acp"]


def test_runtime_for_command_maps_back():
    for runtime in all_runtimes():
        assert runtime_for_command(runtime.acp_command).id == runtime.id


def test_default_agents_come_from_the_registry():
    agents = default_global_agents()
    assert set(agents) == {"cursor", "claude", "codex"}
    assert agents["claude"].acp_command == get_runtime("claude").acp_command
    assert agents["claude"].binary == "claude"


def test_default_acp_command_knows_claude():
    assert default_acp_command("claude", "claude")[0] == "npx"
    assert default_acp_command("outro", "outro") == ["outro", "acp"]


def test_cursor_keeps_agent_mode_in_both_phases():
    cursor = get_runtime("cursor")
    assert cursor.resolve_mode(CURSOR_SESSION, execute=False) == "agent"
    assert cursor.resolve_mode(CURSOR_SESSION, execute=True) == "agent"


def test_claude_uses_its_own_mode_ids():
    claude = get_runtime("claude")
    assert claude.resolve_mode(CLAUDE_SESSION, execute=False) == "default"
    assert claude.resolve_mode(CLAUDE_SESSION, execute=True) == "default"


def test_claude_never_uses_plan_mode():
    """A step that "only plans" is usually the one that writes the artifact.

    In `plan` mode Claude writes a plan to ~/.claude/plans instead of the
    requested file, so the artifact never reaches the session. Writes are
    limited by permission_policy, not by the mode.
    """
    claude = get_runtime("claude")
    assert "plan" not in claude.interview_modes[:1]
    assert "plan" not in claude.execute_modes[:1]
    for execute in (False, True):
        assert claude.resolve_mode(CLAUDE_SESSION, execute=execute) != "plan"


def test_session_without_modes_keeps_historic_behavior():
    assert get_runtime("cursor").resolve_mode({}, execute=True) == "agent"


def test_unknown_modes_fall_back_to_current_mode():
    session = {"modes": {"currentModeId": "custom", "availableModes": [{"id": "custom"}]}}
    assert get_runtime("cursor").resolve_mode(session, execute=True) == "custom"


def test_cursor_sets_model_with_set_model():
    request = get_runtime("cursor").model_request(CURSOR_SESSION, "gpt-5.5", session_id="s1")
    assert request is not None
    assert request.method == "session/set_model"
    assert request.params == {"sessionId": "s1", "modelId": "gpt-id"}


def test_claude_sets_model_with_config_option():
    request = get_runtime("claude").model_request(CLAUDE_SESSION, "sonnet", session_id="s1")
    assert request is not None
    assert request.method == "session/set_config_option"
    assert request.params == {"sessionId": "s1", "configId": "model", "value": "sonnet"}


def test_claude_maps_auto_to_its_default_model():
    request = get_runtime("claude").model_request(CLAUDE_SESSION, "Auto", session_id="s1")
    assert request is not None
    assert request.params["value"] == "default"


def test_model_request_is_none_without_models():
    assert get_runtime("claude").model_request({}, "sonnet", session_id="s1") is None


def test_model_labels_read_config_options_too():
    assert extract_model_labels(CLAUDE_SESSION) == [
        "Default (recommended)",
        "Opus 5.5",
        "Sonnet 5",
    ]
    assert extract_model_labels(CURSOR_SESSION) == ["Auto", "gpt-5.5"]


def test_cursor_authenticates_with_its_method_id():
    assert get_runtime("cursor").auth_method(["cursor_login"]) == "cursor_login"


def test_claude_skips_authenticate_when_nothing_is_advertised():
    assert get_runtime("claude").auth_method([]) is None
    assert get_runtime("cursor").auth_method([]) is None


def test_unknown_method_falls_back_to_the_first_advertised():
    assert get_runtime("claude").auth_method(["oauth"]) == "oauth"


def test_doctor_only_fails_on_the_active_runtime(monkeypatch):
    """A Claude-only machine must not fail doctor for lacking Cursor."""
    from pulse.doctor import checks as checks_module

    def fake_checks(runtime_id):
        if runtime_id == "claude":
            return [checks_module.CheckResult("Claude Code CLI", "ok", "ok")]
        return [checks_module.CheckResult("Cursor CLI", "fail", "sem agent")]

    monkeypatch.setattr(checks_module, "run_agent_checks", fake_checks)
    results = checks_module.run_doctor_checks("claude")
    statuses = {check.name: check.status for check in results}
    assert statuses["Claude Code CLI"] == "ok"
    assert statuses["Runtime cursor"] == "warn"
    assert not any(check.status == "fail" for check in results)


def test_doctor_fails_when_the_active_runtime_is_broken(monkeypatch):
    from pulse.doctor import checks as checks_module

    def fake_checks(runtime_id):
        return [checks_module.CheckResult(f"{runtime_id} CLI", "fail", "faltando")]

    monkeypatch.setattr(checks_module, "run_agent_checks", fake_checks)
    results = checks_module.run_doctor_checks("cursor")
    assert any(check.status == "fail" for check in results)


def _only_available(monkeypatch, available_id):
    monkeypatch.setattr(
        "pulse.runtimes.base.AgentRuntime.is_available",
        lambda self: self.id == available_id,
    )


def test_agent_runtime_falls_back_when_declared_runtime_is_missing(monkeypatch):
    """An agent declaring `cursor` runs on Claude when Cursor is not installed."""
    from pulse.config import resolved as resolved_module

    _only_available(monkeypatch, "claude")
    assert resolved_module._available_runtime_fallback("cursor", None, None) == "claude"


def test_no_fallback_when_the_declared_runtime_is_available(monkeypatch):
    from pulse.config import resolved as resolved_module

    _only_available(monkeypatch, "cursor")
    assert resolved_module._available_runtime_fallback("cursor", None, None) is None


def test_fallback_prefers_the_machine_default(monkeypatch):
    from types import SimpleNamespace

    from pulse.config import resolved as resolved_module

    monkeypatch.setattr("pulse.runtimes.base.AgentRuntime.is_available", lambda self: True)
    assert resolved_module._available_runtime_fallback("cursor", None, None) is None

    _only_available(monkeypatch, "claude")
    global_cfg = SimpleNamespace(default_agent="claude")
    assert resolved_module._available_runtime_fallback("cursor", None, global_cfg) == "claude"


def test_no_fallback_when_nothing_is_available(monkeypatch):
    from pulse.config import resolved as resolved_module

    _only_available(monkeypatch, "nenhum")
    assert resolved_module._available_runtime_fallback("cursor", None, None) is None


def test_runtime_for_command_ignores_the_pinned_version():
    """Config saved before the version pin still maps to Claude."""
    assert (
        runtime_for_command(["npx", "-y", "@agentclientprotocol/claude-agent-acp"]).id == "claude"
    )


def test_runtime_for_command_matches_the_executable_not_a_substring():
    """`agent` (Cursor) is inside `claude-agent-acp`: substring matching picked the wrong one."""
    assert runtime_for_command(["/usr/local/bin/agent", "acp"]).id == "cursor"
    assert runtime_for_command(["/usr/local/bin/claude"]).id == "claude"
