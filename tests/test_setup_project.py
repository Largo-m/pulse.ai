from pathlib import Path

import pytest

from pulse.plan.setup_project_prompt import (
    SETUP_PROJECT_REFERENCES,
    build_setup_project_artifact_prompt,
    build_setup_project_prompt,
    resolve_tlc_spec_skill,
)
from pulse.prompts.ask_question import (
    format_option_label,
    parse_questionnaire_meta,
    resolve_question_progress,
)
from pulse.skills.loader import bundled_skill_dir, load_bundled_skill, resolve_bundled_skill


def test_bundled_skill_dir():
    skill_dir = bundled_skill_dir("tlc-spec-driven")
    assert skill_dir.name == "tlc-spec-driven"
    assert (skill_dir / "SKILL.md").is_file()


def test_resolve_tlc_spec_skill_returns_skill_dir():
    skill_dir = resolve_tlc_spec_skill()
    assert skill_dir.name == "tlc-spec-driven"
    assert (skill_dir / "SKILL.md").is_file()
    for reference in SETUP_PROJECT_REFERENCES:
        assert (skill_dir / "references" / reference).is_file()


def test_load_bundled_skill_missing_raises():
    with pytest.raises(FileNotFoundError, match="nonexistent-skill"):
        load_bundled_skill("nonexistent-skill", references=())


def test_resolve_bundled_skill_missing_raises():
    with pytest.raises(FileNotFoundError, match="nonexistent-skill"):
        resolve_bundled_skill("nonexistent-skill")


def test_build_setup_project_prompt_uses_skill_reference_not_inline_content():
    skill_dir = resolve_tlc_spec_skill()
    workspace = Path("/tmp/my-project")
    prompt = build_setup_project_prompt(
        workspace=workspace,
        user_prompt="App de trading",
        skill_dir=skill_dir,
    )
    assert "Use a skill instalada: `tlc-spec-driven`" in prompt
    assert "Siga o workflow **Setup project**." in prompt
    assert f"`{skill_dir / 'SKILL.md'}`" in prompt
    assert "App de trading" in prompt
    assert "project-init.md" in prompt
    assert "## roadmap.md" not in prompt
    assert str(workspace) in prompt
    assert "SETUP_READY" in prompt
    assert "Isolamento" in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "bloco de texto" in prompt
    assert "```text" in prompt
    assert len(prompt) < 8_000


def test_build_setup_project_artifact_prompt_targets_specs():
    skill_dir = resolve_tlc_spec_skill()
    prompt = build_setup_project_artifact_prompt(
        workspace=Path("/tmp/my-project"),
        user_prompt="App",
        skill_dir=skill_dir,
        analysis_summary="Stack: Vue + Node",
    )
    assert ".pulse/specs/project/PROJECT.md" in prompt
    assert ".pulse/specs/project/ROADMAP.md" in prompt
    assert ".pulse/specs/project/STATE.md" in prompt
    assert "Vue + Node" in prompt
    assert "Análise desta execução" in prompt
    assert "sessão anterior" not in prompt.lower()
    assert "## state-management.md" not in prompt


def test_format_option_label_adds_letter_prefix():
    assert format_option_label(0, "Paper trading") == "A) Paper trading"
    assert format_option_label(1, "B) Já prefixado") == "B) Já prefixado"


def test_parse_questionnaire_meta():
    meta = parse_questionnaire_meta(
        {
            "title": "Preciso de algumas informações antes de continuar.",
            "questionIndex": 2,
            "totalQuestions": 4,
        }
    )
    assert meta["title"].startswith("Preciso")
    assert meta["index"] == 2
    assert meta["total"] == 4


def test_resolve_question_progress_prefers_explicit_meta():
    index, total = resolve_question_progress(
        question={"id": "q1", "prompt": "Pergunta?"},
        position=1,
        batch_size=1,
        meta={"index": 3, "total": 4},
    )
    assert index == 3
    assert total == 4
