from pathlib import Path

import pytest

from pulse.plan.analyze_codebase_prompt import (
    CODEBASE_ARTIFACTS,
    build_analyze_codebase_artifact_prompt,
    build_analyze_codebase_prompt,
    resolve_analyze_codebase_skill,
)
from pulse.plan.runner import run_plan
from pulse.skills.loader import load_bundled_skill


def test_resolve_analyze_codebase_skill_loads_references():
    skill_dir, documents = resolve_analyze_codebase_skill()
    assert skill_dir.name == "tlc-spec-driven"
    assert "SKILL.md" in documents
    assert "brownfield-mapping.md" in documents
    assert "concerns.md" in documents
    assert "code-analysis.md" in documents
    assert "user-input.md" in documents


def test_build_analyze_codebase_prompt_includes_exploration_rules():
    _, documents = resolve_analyze_codebase_skill()
    workspace = Path("/tmp/my-project")
    prompt = build_analyze_codebase_prompt(
        workspace=workspace,
        user_prompt="Monorepo com API e frontend",
        documents=documents,
    )
    assert "tlc-spec-driven" in prompt
    assert "Monorepo com API e frontend" in prompt
    assert "brownfield-mapping.md" in prompt
    assert "## user-input.md" not in prompt
    assert str(workspace) in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "ANALYZE_READY" in prompt
    assert "Isolamento" in prompt
    assert "autônomo" in prompt.lower() or "autonomo" in prompt.lower()


def test_build_analyze_codebase_artifact_prompt_targets_codebase_specs():
    _, documents = resolve_analyze_codebase_skill()
    prompt = build_analyze_codebase_artifact_prompt(
        workspace=Path("/tmp/my-project"),
        user_prompt="App legado",
        documents=documents,
        analysis_summary="Stack: Python + FastAPI",
    )
    for artifact in CODEBASE_ARTIFACTS:
        assert f".pulse/specs/codebase/{artifact}" in prompt
    assert "Python + FastAPI" in prompt
    assert "Análise desta execução" in prompt
    assert "concerns.md" in prompt


def test_load_bundled_skill_missing_raises():
    with pytest.raises(FileNotFoundError, match="nonexistent-skill"):
        load_bundled_skill("nonexistent-skill", references=())


def test_run_plan_analyze_codebase_delegates(monkeypatch):
    calls: list[str] = []

    def fake_run(*, user_prompt: str) -> int:
        calls.append(user_prompt)
        return 0

    monkeypatch.setattr("pulse.plan.runner.run_analyze_codebase", fake_run)
    assert run_plan(spec_type_id="analyze-codebase", user_prompt="Mapear") == 0
    assert calls == ["Mapear"]
