from pathlib import Path

from pulse.context.workspace_context import (
    discover_workspace_rules,
    discover_workspace_skills,
    extend_prompt_with_workspace_context,
    load_workspace_context,
    parse_skill_metadata,
)
from pulse.plan.analyze_codebase_prompt import build_analyze_codebase_prompt, resolve_analyze_codebase_skill
from pulse.plan.quick_prompt import build_quick_plan_prompt, resolve_quick_skill
from pulse.plan.setup_project_prompt import build_setup_project_prompt, resolve_tlc_spec_skill


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discover_workspace_rules_finds_root_and_cursor_rules(tmp_path: Path):
    _write(tmp_path / "AGENTS.md", "# Agents\nRode testes antes de commitar.")
    _write(tmp_path / "CLAUDE.md", "# Claude\nNão commite sem pedir.")
    _write(tmp_path / ".cursor" / "rules" / "python.mdc", "Use type hints.")

    rules = discover_workspace_rules(tmp_path)
    paths = {rule.relative_path for rule in rules}
    assert paths == {"AGENTS.md", "CLAUDE.md", ".cursor/rules/python.mdc"}
    assert "Rode testes" in next(r for r in rules if r.relative_path == "AGENTS.md").content


def test_discover_workspace_skills_finds_any_skill_md(tmp_path: Path):
    _write(
        tmp_path / ".cursor" / "skills" / "deploy" / "SKILL.md",
        "---\nname: deploy\ndescription: Deploy para produção com checklist.\n---\n# Deploy\n",
    )
    _write(
        tmp_path / "custom" / "lint" / "SKILL.md",
        "---\nname: lint\ndescription: Rodar linters do projeto.\n---\n# Lint\n",
    )
    _write(
        tmp_path / ".pulse" / "skills" / "legacy" / "SKILL.md",
        "---\ndescription: Legado.\n---\n# Legacy\n",
    )

    skills = discover_workspace_skills(tmp_path)
    names = {skill.name for skill in skills}
    paths = {skill.skill_file for skill in skills}
    assert names == {"deploy", "lint"}
    assert "custom/lint/SKILL.md" in paths
    assert not any("legacy" in path for path in paths)


def test_parse_skill_metadata_reads_frontmatter(tmp_path: Path):
    skill_file = tmp_path / "SKILL.md"
    _write(
        skill_file,
        "---\nname: custom-name\ndescription: Faz algo útil.\n---\n# Title\n",
    )
    name, description = parse_skill_metadata(skill_file)
    assert name == "custom-name"
    assert description == "Faz algo útil."


def test_extend_prompt_with_workspace_context_inlines_rules(tmp_path: Path):
    _write(tmp_path / "AGENTS.md", "Sempre rode os testes.")
    sections: list[str] = ["## Isolamento", ""]
    extend_prompt_with_workspace_context(sections, tmp_path, mode="full")
    joined = "\n".join(sections)
    assert "Leia `AGENTS.md` e `CLAUDE.md`" in joined
    assert "Sempre rode os testes." in joined
    assert "AGENTS.md" in joined


def test_extend_prompt_with_workspace_context_index_skips_inline(tmp_path: Path):
    _write(tmp_path / "AGENTS.md", "Sempre rode os testes. Conteúdo longo que não deve ir no prompt.")
    sections: list[str] = ["## Isolamento", ""]
    extend_prompt_with_workspace_context(sections, tmp_path, mode="index")
    joined = "\n".join(sections)
    assert "índice" in joined.lower() or "Índice" in joined or "(índice)" in joined
    assert "`AGENTS.md`" in joined
    assert "Sempre rode os testes. Conteúdo longo que não deve ir no prompt." not in joined
    assert "Não releia todas as rules por rotina." in joined


def test_discover_workspace_rules_can_skip_content(tmp_path: Path):
    _write(tmp_path / "AGENTS.md", "conteúdo secreto")
    rules = discover_workspace_rules(tmp_path, load_content=False)
    assert len(rules) == 1
    assert rules[0].relative_path == "AGENTS.md"
    assert rules[0].content == ""


def test_build_specify_prompt_uses_index_context(tmp_path: Path):
    from pulse.plan.new_issue_prompt import build_specify_prompt, resolve_new_issue_skill
    from pulse.plan.specify_state import WorkflowState

    _write(tmp_path / "AGENTS.md", "Regra longa que não deve ser inlined no Specify.")
    skill_dir = resolve_new_issue_skill()
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login")
    prompt = build_specify_prompt(
        workspace=tmp_path,
        user_prompt="Login",
        skill_dir=skill_dir,
        state=state,
    )
    assert "`AGENTS.md`" in prompt
    assert "Regra longa que não deve ser inlined no Specify." not in prompt
    assert "coding-principles.md" not in prompt
    assert "Não releia rules/skills" in prompt


def test_build_execute_wave_prompt_uses_full_context(tmp_path: Path):
    from pulse.plan.new_issue_prompt import build_execute_wave_prompt, resolve_new_issue_skill
    from pulse.plan.specify_state import WorkflowState

    _write(tmp_path / "AGENTS.md", "Sempre rode os testes no Execute.")
    skill_dir = resolve_new_issue_skill()
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login")
    prompt = build_execute_wave_prompt(
        workspace=tmp_path,
        user_prompt="Login",
        skill_dir=skill_dir,
        state=state,
        wave_label="Wave 1",
        task_lines=["- **T1** — A"],
        task_ids=["T1"],
        parallel=False,
        tasks_skipped=False,
    )
    assert "Sempre rode os testes no Execute." in prompt
    assert "coding-principles.md" in prompt
    assert "antes de editar código" in prompt.lower() or "antes de editar código" in prompt

def test_build_setup_project_prompt_includes_workspace_rules(tmp_path: Path):
    _write(tmp_path / "AGENTS.md", "Não commite sem pedir.")
    skill_dir = resolve_tlc_spec_skill()
    prompt = build_setup_project_prompt(
        workspace=tmp_path,
        user_prompt="App",
        skill_dir=skill_dir,
    )
    assert "Leia `AGENTS.md` e `CLAUDE.md`" in prompt
    assert "Não commite sem pedir." in prompt


def test_build_analyze_codebase_prompt_includes_workspace_rules(tmp_path: Path):
    _write(tmp_path / "CLAUDE.md", "Responda em português no código.")
    skill_dir = resolve_analyze_codebase_skill()
    prompt = build_analyze_codebase_prompt(
        workspace=tmp_path,
        user_prompt="Mapear",
        skill_dir=skill_dir,
    )
    assert "Leia `AGENTS.md` e `CLAUDE.md`" in prompt
    assert "Responda em português no código." in prompt


def test_build_quick_plan_prompt_lists_project_skills(tmp_path: Path):
    _write(
        tmp_path / ".cursor" / "skills" / "test-skill" / "SKILL.md",
        "---\ndescription: Executar testes do projeto.\n---\n# Tests\n",
    )
    skill_dir = resolve_quick_skill()
    prompt = build_quick_plan_prompt(
        workspace=tmp_path,
        user_prompt="Fix bug",
        skill_dir=skill_dir,
    )
    assert "Skills do projeto (sob demanda)" in prompt
    assert ".cursor/skills/test-skill/SKILL.md" in prompt
    assert "Executar testes do projeto." in prompt
    assert "(índice)" in prompt or "Índice apenas" in prompt


def test_build_quick_plan_prompt_does_not_inline_rules(tmp_path: Path):
    from pulse.plan.quick_prompt import build_quick_plan_prompt

    _write(tmp_path / "AGENTS.md", "Conteúdo que não deve ir no plano Quick.")
    skill_dir = resolve_quick_skill()
    prompt = build_quick_plan_prompt(
        workspace=tmp_path,
        user_prompt="Fix bug",
        skill_dir=skill_dir,
    )
    assert "`AGENTS.md`" in prompt
    assert "Conteúdo que não deve ir no plano Quick." not in prompt
    assert "coding-principles.md" not in prompt

def test_load_workspace_context_empty_workspace(tmp_path: Path):
    context = load_workspace_context(tmp_path)
    assert context.rules == ()
    assert context.skills == ()
