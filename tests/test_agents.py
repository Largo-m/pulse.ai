from pathlib import Path

from pulse.agents.compose import compose_workflow_agents, expand_spec_flow
from pulse.agents.loader import load_agent, load_agents
from pulse.config.project_config import init_project_config
from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill


def test_extend_prompt_with_bundled_skill_lists_files_not_content():
    skill_dir = resolve_bundled_skill("pulse-spec-driven")
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name="pulse-spec-driven",
        workflow="Setup project",
        references=("project-init.md", "roadmap.md"),
    )
    joined = "\n".join(sections)
    assert "Use a skill instalada: `pulse-spec-driven`" in joined
    assert "Siga o workflow **Setup project**." in joined
    assert f"`{skill_dir / 'SKILL.md'}`" in joined
    assert f"`{skill_dir / 'references' / 'project-init.md'}`" in joined
    assert "Tech Lead's Club" not in joined


def test_extend_prompt_injects_agent_body(tmp_path: Path):
    skill_dir = resolve_bundled_skill("pulse-spec-driven")
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name="pulse-spec-driven",
        workflow="PRD",
        agent_id="prd",
        workspace=tmp_path,
    )
    joined = "\n".join(sections)
    assert "Agent `prd`" in joined
    assert "Capture WHAT to build" in joined


def test_load_bundled_agent():
    agent = load_agent("prd")
    assert agent is not None
    assert agent.origin == "bundled"
    assert agent.permission_policy == "deny_writes"
    assert "PRD" in agent.body or "WHAT to build" in agent.body


def test_global_agent_overrides_bundled(tmp_path: Path):
    from pulse.config.paths import global_agents_dir

    dest = global_agents_dir() / "prd"
    dest.mkdir(parents=True)
    (dest / "AGENT.md").write_text(
        "---\nname: prd\nmodel: gpt-5.5\nruntime: claude\npermission_policy: ask\n---\ncustom body\n",
        encoding="utf-8",
    )
    agent = load_agent("prd", workspace=tmp_path)
    assert agent is not None
    assert agent.origin == "global"
    assert agent.model == "gpt-5.5"
    assert agent.runtime == "claude"
    assert "custom body" in agent.body


def test_project_and_editor_agents_are_ignored(tmp_path: Path):
    project = tmp_path / ".pulse" / "agents" / "prd"
    project.mkdir(parents=True)
    (project / "AGENT.md").write_text("---\nmodel: nope\n---\nfrom project\n", encoding="utf-8")
    for dirname in (".cursor", ".claude", ".codex"):
        dest = tmp_path / dirname / "agents"
        dest.mkdir(parents=True)
        (dest / "reviewer.md").write_text("---\nname: reviewer\n---\nextra\n", encoding="utf-8")
    agent = load_agent("prd", workspace=tmp_path)
    assert agent is not None
    assert agent.origin == "bundled"
    assert "from project" not in agent.body
    ids = {item.definition.id for item in load_agents(workspace=tmp_path)}
    assert "reviewer" not in ids


def test_discover_global_agent(tmp_path: Path):
    from pulse.config.paths import global_agents_dir

    dest = global_agents_dir() / "reviewer"
    dest.mkdir(parents=True)
    (dest / "AGENT.md").write_text(
        "---\nname: reviewer\ndescription: Review\n---\nreview playbook\n",
        encoding="utf-8",
    )
    agents = load_agents(workspace=tmp_path)
    extra = next(item for item in agents if item.definition.id == "reviewer")
    assert extra.origin == "global"
    assert "review playbook" in extra.body


def test_compose_spec_flows():
    assert compose_workflow_agents("spec") == ("classify",)
    assert expand_spec_flow("quick")[0] == "classify"
    assert "quick-plan" in expand_spec_flow("quick")
    assert "prd" in expand_spec_flow("full")


def test_init_copies_bundled_agents_into_home(tmp_path: Path):
    from pulse.config.paths import global_agents_dir

    init_project_config(tmp_path)
    assert (global_agents_dir() / "prd" / "AGENT.md").is_file()
    assert not (tmp_path / ".pulse" / "agents").exists()


def test_apply_agent_settings_uses_sqlite_override(tmp_path: Path):
    from pulse.agents.loader import apply_agent_settings, load_agent
    from pulse.store.agent_settings import upsert_agent_settings

    init_project_config(tmp_path)
    from pulse.config.project_config import load_project_config

    project = load_project_config(tmp_path)
    assert project is not None
    loaded = load_agent("prd", workspace=tmp_path)
    assert loaded is not None
    original_model = loaded.model
    upsert_agent_settings(project.project_id, "prd", model="composer-2.5")
    view = apply_agent_settings(loaded, project.project_id)
    assert view.model == "composer-2.5"
    assert loaded.model == original_model
    assert view.runtime == loaded.runtime
