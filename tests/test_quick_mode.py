from pathlib import Path

import pytest

from pulse.plan.quick_prompt import (
    QUICK_REFERENCES,
    approval_is_positive,
    build_quick_implement_prompt,
    build_quick_plan_prompt,
    resolve_quick_skill,
)
from pulse.plan.runner import run_plan
from pulse.skills.loader import load_bundled_skill


def test_resolve_quick_skill_returns_skill_dir():
    skill_dir = resolve_quick_skill()
    assert skill_dir.name == "pulse-spec-driven"
    assert (skill_dir / "SKILL.md").is_file()
    for reference in QUICK_REFERENCES:
        assert (skill_dir / "references" / reference).is_file()


def test_build_quick_plan_prompt_enforces_scope_and_approval():
    skill_dir = resolve_quick_skill()
    workspace = Path("/tmp/my-project")
    prompt = build_quick_plan_prompt(
        workspace=workspace,
        user_prompt="Corrigir botão de login que retorna 401",
        skill_dir=skill_dir,
    )
    assert "Agent `quick-plan`" in prompt
    assert "Corrigir botão de login" in prompt
    assert str(workspace) in prompt
    assert "Isolamento" in prompt
    assert "Awaiting Approval" in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "Não edite código de aplicação" in prompt
    assert "quick fixes **pré-definidos**" in prompt
    assert "Outro" in prompt
    assert "```text" in prompt


def test_build_quick_implement_prompt_targets_quick_specs():
    skill_dir = resolve_quick_skill()
    prompt = build_quick_implement_prompt(
        workspace=Path("/tmp/my-project"),
        user_prompt="Fix",
        skill_dir=skill_dir,
        plan_summary="Plano aprovado",
        approval_answers="→ Sim, aprovar e implementar",
    )
    assert ".pulse/specs/quick/" in prompt
    assert "Plano aprovado" in prompt
    assert "coding-principles.md" in prompt
    assert "## coding-principles.md" not in prompt


def test_approval_is_positive():
    assert approval_is_positive("→ Sim, aprovar e implementar")
    assert not approval_is_positive("→ Não, preciso de ajustes")
    assert not approval_is_positive("")


def test_load_bundled_skill_missing_raises():
    with pytest.raises(FileNotFoundError, match="nonexistent-skill"):
        load_bundled_skill("nonexistent-skill", references=())


def test_run_plan_rejects_fix_bug(monkeypatch):
    monkeypatch.setattr("pulse.plan.runner.run_spec", lambda **_k: 0)
    assert run_plan(spec_type_id="fix-bug", user_prompt="Corrigir bug") == 2
