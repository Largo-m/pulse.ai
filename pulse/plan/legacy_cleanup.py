from __future__ import annotations

import shutil
from pathlib import Path

LEGACY_QUESTIONS_DIR = Path(".pulse") / "skills"
LEGACY_HANDOFF_DIR = Path(".pulse") / "handoff"


def cleanup_legacy_pulse_questions(*, workspace: Path, skill_id: str) -> None:
    questions_dir = workspace / LEGACY_QUESTIONS_DIR / skill_id / "questions"
    if questions_dir.is_dir():
        shutil.rmtree(questions_dir)

    handoff_file = workspace / LEGACY_HANDOFF_DIR / f"{skill_id}.md"
    if handoff_file.is_file():
        handoff_file.unlink()

    skill_root = workspace / LEGACY_QUESTIONS_DIR / skill_id
    if skill_root.is_dir() and not any(skill_root.iterdir()):
        skill_root.rmdir()

    handoff_root = workspace / LEGACY_HANDOFF_DIR
    if handoff_root.is_dir() and not any(handoff_root.iterdir()):
        handoff_root.rmdir()
