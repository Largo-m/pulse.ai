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
        workflow="Specify",
        agent_id="specify",
        workspace=tmp_path,
    )
    joined = "\n".join(sections)
    assert "Agent `specify`" in joined
    assert "Capture WHAT to build" in joined


def test_load_bundled_agent():
    agent = load_agent("specify")
    assert agent is not None
    assert agent.origin == "bundled"
    assert agent.permission_policy == "deny_writes"
    assert "Specify" in agent.body or "WHAT to build" in agent.body


def test_project_agent_overrides_bundled(tmp_path: Path):
    dest = tmp_path / ".pulse" / "agents" / "specify"
    dest.mkdir(parents=True)
    (dest / "AGENT.md").write_text(
        "---\nname: specify\nmodel: gpt-5.5\nruntime: claude\npermission_policy: ask\n---\ncustom body\n",
        encoding="utf-8",
    )
    agent = load_agent("specify", workspace=tmp_path)
    assert agent is not None
    assert agent.origin == "project"
    assert agent.model == "gpt-5.5"
    assert agent.runtime == "claude"
    assert "custom body" in agent.body


def test_discover_claude_agent(tmp_path: Path):
    dest = tmp_path / ".claude" / "agents"
    dest.mkdir(parents=True)
    (dest / "reviewer.md").write_text(
        "---\nname: reviewer\ndescription: Review\n---\nreview playbook\n",
        encoding="utf-8",
    )
    agents = load_agents(workspace=tmp_path)
    ids = {item.definition.id for item in agents}
    assert "reviewer" in ids
    extra = next(item for item in agents if item.definition.id == "reviewer")
    assert extra.origin == "claude"


def test_compose_spec_flows():
    assert compose_workflow_agents("spec") == ("classify",)
    assert expand_spec_flow("quick")[0] == "classify"
    assert "quick-plan" in expand_spec_flow("quick")
    assert "specify" in expand_spec_flow("full")


def test_init_copies_bundled_agents(tmp_path: Path):
    init_project_config(tmp_path)
    assert (tmp_path / ".pulse" / "agents" / "specify" / "AGENT.md").is_file()
