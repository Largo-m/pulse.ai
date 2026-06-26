from __future__ import annotations

from pathlib import Path

_SKILLS_PACKAGE_DIR = Path(__file__).resolve().parent


def bundled_skill_dir(skill_name: str) -> Path:
    return _SKILLS_PACKAGE_DIR / skill_name


def load_bundled_skill(
    skill_name: str,
    *,
    references: tuple[str, ...],
) -> tuple[Path, dict[str, str]]:
    skill_dir = bundled_skill_dir(skill_name)
    if not (skill_dir / "SKILL.md").is_file():
        raise FileNotFoundError(
            f"Skill `{skill_name}` não encontrada em `{skill_dir / 'SKILL.md'}`"
        )
    documents = load_skill_documents(skill_dir, references=references)
    return skill_dir, documents


def load_skill_documents(
    skill_dir: Path,
    *,
    references: tuple[str, ...],
) -> dict[str, str]:
    documents: dict[str, str] = {}
    skill_file = skill_dir / "SKILL.md"
    documents["SKILL.md"] = skill_file.read_text(encoding="utf-8")
    for reference in references:
        reference_path = skill_dir / "references" / reference
        if reference_path.is_file():
            documents[reference] = reference_path.read_text(encoding="utf-8")
    return documents
