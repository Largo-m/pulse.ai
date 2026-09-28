from pathlib import Path

import pytest

from pulse.plan.analyze_codebase_prompt import (
    ANALYZE_CODEBASE_REFERENCES,
    CODEBASE_ARTIFACTS,
    build_analyze_codebase_artifact_prompt,
    build_analyze_codebase_prompt,
    resolve_analyze_codebase_skill,
)
from pulse.plan.runner import run_plan
from pulse.skills.loader import load_bundled_skill


def test_resolve_analyze_codebase_skill_returns_skill_dir():
    skill_dir = resolve_analyze_codebase_skill()
    assert skill_dir.name == "pulse-spec-driven"
    assert (skill_dir / "SKILL.md").is_file()
    for reference in ANALYZE_CODEBASE_REFERENCES:
        assert (skill_dir / "references" / reference).is_file()


def test_build_analyze_codebase_prompt_includes_exploration_rules():
    skill_dir = resolve_analyze_codebase_skill()
    workspace = Path("/tmp/my-project")
    prompt = build_analyze_codebase_prompt(
        workspace=workspace,
        user_prompt="Monorepo com API e frontend",
        skill_dir=skill_dir,
    )
    assert "Agent `codebase-explore`" in prompt
    assert "Monorepo com API e frontend" in prompt
    assert str(workspace) in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "ANALYZE_READY" in prompt
    assert "## Isolation (mandatory)" in prompt
    assert "autônomo" in prompt.lower() or "autonomo" in prompt.lower()


def test_build_analyze_codebase_artifact_prompt_targets_codebase_specs():
    skill_dir = resolve_analyze_codebase_skill()
    prompt = build_analyze_codebase_artifact_prompt(
        workspace=Path("/tmp/my-project"),
        user_prompt="App legado",
        skill_dir=skill_dir,
        analysis_summary="Stack: Python + FastAPI",
    )
    for artifact in CODEBASE_ARTIFACTS:
        assert f".pulse/specs/codebase/{artifact}" in prompt
    assert "Python + FastAPI" in prompt
    assert "This run's analysis" in prompt
    assert "concerns.md" in prompt
    assert "## concerns.md" not in prompt


def test_load_bundled_skill_missing_raises():
    with pytest.raises(FileNotFoundError, match="nonexistent-skill"):
        load_bundled_skill("nonexistent-skill", references=())


def test_run_plan_analyze_codebase_delegates(monkeypatch):
    calls: list[str] = []

    def fake_run(*, user_prompt: str, **_kwargs) -> int:
        calls.append(user_prompt)
        return 0

    monkeypatch.setattr("pulse.plan.runner.run_analyze_codebase", fake_run)
    assert run_plan(spec_type_id="analyze-codebase", user_prompt="Mapear") == 0
    assert calls == ["Mapear"]
