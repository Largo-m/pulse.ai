"""O texto de fase é arquivo, não código.

O que importa aqui: quem instala o Pulse consegue editar as instruções de fase
sem tocar no venv, e o que ele edita é o que chega no agente.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.agents.loader import install_global_agents
from pulse.plan.new_issue_prompt import build_execute_task_prompt, build_prd_prompt
from pulse.prompts.templates import (
    TemplateError,
    bundled_agents_dir,
    bundled_shared_dir,
    global_shared_dir,
    load_shared,
    load_template,
    render,
)
from pulse.plan.workflow_state import WorkflowState
from pulse.skills.loader import resolve_bundled_skill

SKILL = resolve_bundled_skill("pulse-spec-driven")


def _state() -> WorkflowState:
    return WorkflowState.create_new(feature_slug="login-email", user_prompt="Login com e-mail")


def _prd(tmp_path: Path) -> str:
    return build_prd_prompt(
        workspace=tmp_path, user_prompt="Login com e-mail", skill_dir=SKILL, state=_state()
    )


def test_render_replaces_placeholders():
    assert render("oi {{nome}}", {"nome": "ana"}) == "oi ana"


def test_render_leaves_literal_braces_alone():
    """O texto de fase tem `{id: T1, title: ...}` literal — não é placeholder."""
    text = "Popule `tasks` com `[{id: T1, title: ...}, ...]`"
    assert render(text, {}) == text


def test_render_rejects_unknown_placeholder():
    with pytest.raises(TemplateError, match="placeholder sem valor: idade"):
        render("oi {{nome}}, {{idade}}", {"nome": "ana"})


def test_conditional_block_drops_when_value_is_empty():
    text = "a\n{{#if extra}}{{extra}}\n{{/if}}b"
    assert render(text, {"extra": ""}) == "a\nb"
    assert render(text, {"extra": "meio"}) == "a\nmeio\nb"


def test_every_bundled_agent_template_renders_from_disk():
    for agent_dir in sorted(bundled_agents_dir().iterdir()):
        for template in sorted(agent_dir.glob("*.md")):
            if template.name == "AGENT.md":
                continue
            assert template.read_text(encoding="utf-8").strip(), f"{template} está vazio"


def test_user_edit_in_global_dir_reaches_the_prompt(tmp_path: Path, monkeypatch):
    """O caso que motivou a mudança: editar sem mexer no venv."""
    home = tmp_path / "home"
    monkeypatch.setattr("pulse.config.paths.global_state_dir", lambda: home)
    monkeypatch.setattr("pulse.agents.loader.global_agents_dir", lambda: home / "agents")
    monkeypatch.setattr("pulse.prompts.templates.global_agents_dir", lambda: home / "agents")
    monkeypatch.setattr("pulse.prompts.templates.global_shared_dir", lambda: home / "prompts" / "shared")

    install_global_agents()
    edited = home / "agents" / "prd" / "PHASE.md"
    assert edited.is_file(), "o template precisa ser instalado para o usuário editar"

    edited.write_text(
        "Workspace: `{{workspace}}`\n\nESTIMATIVA DE ESFORÇO OBRIGATÓRIA POR HISTÓRIA\n",
        encoding="utf-8",
    )
    prompt = _prd(tmp_path)
    assert "ESTIMATIVA DE ESFORÇO OBRIGATÓRIA POR HISTÓRIA" in prompt
    assert "## Fase PRD" not in prompt


def test_global_wins_over_bundled_only_when_present(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr("pulse.prompts.templates.global_agents_dir", lambda: home / "agents")
    # sem nada no global, vale o de fábrica
    assert load_template("prd").origin == "bundled"


def test_install_does_not_overwrite_user_edits(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr("pulse.agents.loader.global_agents_dir", lambda: home / "agents")
    monkeypatch.setattr("pulse.prompts.templates.global_shared_dir", lambda: home / "prompts" / "shared")

    install_global_agents()
    edited = home / "agents" / "prd" / "PHASE.md"
    edited.write_text("meu texto", encoding="utf-8")
    install_global_agents()
    assert edited.read_text(encoding="utf-8") == "meu texto"


def test_shared_blocks_are_installed_too(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr("pulse.agents.loader.global_agents_dir", lambda: home / "agents")
    monkeypatch.setattr("pulse.prompts.templates.global_shared_dir", lambda: home / "prompts" / "shared")

    install_global_agents()
    shared = home / "prompts" / "shared"
    for name in ("isolation.md", "clarify.md", "approval.md"):
        assert (shared / name).is_file(), f"{name} não instalado"


def test_missing_template_names_both_paths():
    with pytest.raises(TemplateError) as error:
        load_template("prd", "NAO-EXISTE.md")
    message = str(error.value)
    assert "NAO-EXISTE.md" in message
    assert "prd" in message


def test_techspec_line_disappears_when_techspec_is_skipped(tmp_path: Path):
    state = _state()
    state.phases["techspec"].skip = True
    prompt = build_execute_task_prompt(
        workspace=tmp_path,
        user_prompt="Login",
        skill_dir=SKILL,
        state=state,
        task_id="T1",
        task_title="Form",
        tasks_skipped=False,
    )
    assert "TECHSPEC.md` se existir" not in prompt
    assert "- **T1** — Form" in prompt


def test_shared_block_is_reused_not_copied():
    """Um bloco editado uma vez vale para todas as fases que o usam."""
    isolation = load_shared("isolation").text
    assert "{{workspace}}" in isolation
    assert (bundled_shared_dir() / "isolation.md").is_file()
