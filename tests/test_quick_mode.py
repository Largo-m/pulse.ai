from pathlib import Path

import pytest

from pulse.plan.quick_prompt import (
    approval_is_positive,
    build_quick_implement_prompt,
    build_quick_plan_prompt,
    resolve_quick_skill,
)
from pulse.plan.runner import run_plan
from pulse.skills.loader import load_bundled_skill


def test_resolve_quick_skill_loads_references():
    skill_dir, documents = resolve_quick_skill()
    assert skill_dir.name == "tlc-spec-driven"
    assert "SKILL.md" in documents
    assert "quick-mode.md" in documents
    assert "coding-principles.md" in documents
    assert "state-management.md" in documents
    assert "user-input.md" in documents


def test_build_quick_plan_prompt_enforces_scope_and_approval():
    _, documents = resolve_quick_skill()
    workspace = Path("/tmp/my-project")
    prompt = build_quick_plan_prompt(
        workspace=workspace,
        user_prompt="Corrigir botão de login que retorna 401",
        documents=documents,
    )
    assert "tlc-spec-driven" in prompt
    assert "Corrigir botão de login" in prompt
    assert str(workspace) in prompt
    assert "quick-mode.md" in prompt
    assert "## user-input.md" not in prompt
    assert "Isolamento" in prompt
    assert "Awaiting Approval" in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "Não edite código de aplicação" in prompt
    assert "quick fixes **pré-definidos**" in prompt
    assert "Outro" in prompt
    assert "```text" in prompt


def test_build_quick_implement_prompt_targets_quick_specs():
    _, documents = resolve_quick_skill()
    prompt = build_quick_implement_prompt(
        workspace=Path("/tmp/my-project"),
        user_prompt="Corrigir botão",
        documents=documents,
        plan_summary="Plano: adicionar checagem de expiração",
        approval_answers="→ A) Sim, aprovar e implementar",
    )
    assert ".pulse/specs/quick/NNN-slug/TASK.md" in prompt
    assert ".pulse/specs/quick/NNN-slug/SUMMARY.md" in prompt
    assert "Status: In Progress" in prompt
    assert "Status: Done" in prompt
    assert "adicionar checagem de expiração" in prompt
    assert "coding-principles.md" in prompt
    assert "git" in prompt.lower()


def test_approval_is_positive():
    assert approval_is_positive("→ A) Sim, aprovar e implementar") is True
    assert approval_is_positive("→ B) Não, preciso de ajustes") is False
    assert approval_is_positive("→ A) Migrar para pipeline completo") is False
    assert approval_is_positive("") is False
    assert approval_is_positive("nenhuma seleção marcada") is False


def test_load_bundled_skill_missing_raises():
    with pytest.raises(FileNotFoundError, match="nonexistent-skill"):
        load_bundled_skill("nonexistent-skill", references=())


def test_run_plan_fix_bug_delegates_to_quick(monkeypatch):
    calls: list[str] = []

    def fake_run(*, user_prompt: str) -> int:
        calls.append(user_prompt)
        return 0

    monkeypatch.setattr("pulse.plan.runner.run_quick", fake_run)
    assert run_plan(spec_type_id="fix-bug", user_prompt="Quick fix botão") == 0
    assert calls == ["Quick fix botão"]
