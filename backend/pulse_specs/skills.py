from __future__ import annotations

from pathlib import Path

from pulse_specs.discovery import SpecPhase

_BASE_SKILLS = (
    "python-expert",
    "clean-code",
    "python-design-patterns",
    "python-testing-patterns",
    "python-project-structure",
)

_TUI_PHASES = {10, 11, 12, 16}
_SECURITY_PHASES = {13, 15}


def resolve_applicable_skills(phase: SpecPhase, artifacts_path: Path) -> list[str]:
    skill_names = list(_BASE_SKILLS)
    if phase.number in _TUI_PHASES:
        skill_names.append("terminal-ui")
    if phase.number in _SECURITY_PHASES:
        skill_names.append("security-review")
    skill_names.append("create-pr")

    skills_root = artifacts_path / ".cursor" / "skills"
    resolved: list[str] = []
    for name in skill_names:
        skill_path = skills_root / name / "SKILL.md"
        if skill_path.is_file():
            resolved.append(f"@backend/.cursor/skills/{name}/SKILL.md")
    return resolved
