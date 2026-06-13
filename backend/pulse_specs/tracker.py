from __future__ import annotations

from pathlib import Path


def spec_workflow_dir(artifacts_path: Path, phase_slug: str) -> Path:
    return artifacts_path / ".workflow" / "specs" / phase_slug


def spec_status_path(artifacts_path: Path, phase_slug: str) -> Path:
    return spec_workflow_dir(artifacts_path, phase_slug) / "_status.md"


def ensure_spec_workflow_dir(artifacts_path: Path, phase_slug: str) -> Path:
    workflow_dir = spec_workflow_dir(artifacts_path, phase_slug)
    workflow_dir.mkdir(parents=True, exist_ok=True)
    return workflow_dir


def is_spec_completed(status_path: Path) -> bool:
    if not status_path.is_file():
        return False
    content = status_path.read_text(encoding="utf-8").lower()
    return "status: completed" in content
