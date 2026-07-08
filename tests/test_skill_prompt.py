from pathlib import Path

from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill


def test_extend_prompt_with_bundled_skill_lists_files_not_content():
    skill_dir = resolve_bundled_skill("tlc-spec-driven")
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name="tlc-spec-driven",
        workflow="Setup project",
        references=("project-init.md", "roadmap.md"),
    )
    joined = "\n".join(sections)
    assert "Use a skill instalada: `tlc-spec-driven`" in joined
    assert "Siga o workflow **Setup project**." in joined
    assert f"`{skill_dir / 'SKILL.md'}`" in joined
    assert f"`{skill_dir / 'references' / 'project-init.md'}`" in joined
    assert "Tech Lead's Club" not in joined
