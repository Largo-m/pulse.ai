from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from cursor_task.question_handler import APPROVAL_MARKERS
from cursor_task.types import ArtifactKind


ARTIFACT_PATTERNS: dict[ArtifactKind, str] = {
    "prd": "*_prd.md",
    "techspec": "*_techspec.md",
    "tasks": "*_tasks.md",
}

ARTIFACT_LABELS: dict[ArtifactKind, str] = {
    "prd": "PRD",
    "techspec": "TechSpec",
    "tasks": "Tasks",
}


@dataclass
class ArtifactWriter:
    artifacts_path: Path
    artifact_kind: ArtifactKind = "prd"
    output_file: Path | None = None
    _started_at: float = field(default_factory=time.time)
    _assistant_segments: list[str] = field(default_factory=list)

    def track_assistant_text(self, text: str) -> None:
        cleaned = text.strip()
        if cleaned and not self._is_draft_pending_approval(cleaned):
            self._assistant_segments.append(cleaned)

    def resolve_output_path(self) -> Path:
        if self.output_file is not None:
            return self.output_file
        found = self._find_artifact_path()
        if found is not None:
            return found
        raise RuntimeError(
            f"nenhum artefato {self.artifact_kind} encontrado em .workflow/tasks/"
        )

    def write(self) -> tuple[Path, str]:
        content = self._resolve_content()
        if not content.strip():
            label = ARTIFACT_LABELS[self.artifact_kind]
            raise RuntimeError(
                f"nenhum artefato final encontrado; aprove o {label} e aguarde o agente salvar o documento"
            )
        destination = self.resolve_output_path()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content.rstrip() + "\n", encoding="utf-8")
        return destination, content

    def has_artifact_on_disk(self) -> bool:
        path = self._find_artifact_on_disk_path()
        if path is None:
            return False
        if self.artifact_kind == "tasks":
            return any(path.parent.glob("task_*.md"))
        return True

    def list_task_files(self) -> list[Path]:
        path = self._find_artifact_on_disk_path()
        if path is None:
            return []
        return sorted(path.parent.glob("task_*.md"))

    def _resolve_content(self) -> str:
        from_disk = self._find_artifact_on_disk()
        if from_disk:
            return from_disk
        return ""

    @staticmethod
    def _is_draft_pending_approval(text: str) -> bool:
        lowered = text.lower()
        return any(re.search(marker, lowered) for marker in APPROVAL_MARKERS)

    def _tasks_root(self) -> Path:
        return self.artifacts_path / ".workflow" / "tasks"

    def _find_artifact_path(self) -> Path | None:
        candidates: list[tuple[float, Path]] = []
        root = self._tasks_root()
        if not root.exists():
            return None
        pattern = ARTIFACT_PATTERNS[self.artifact_kind]
        for path in root.rglob(pattern):
            if path.is_file() and path.stat().st_mtime >= self._started_at - 5:
                candidates.append((path.stat().st_mtime, path))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _find_artifact_on_disk(self) -> str | None:
        path = self._find_artifact_on_disk_path()
        if path is None:
            return None
        return path.read_text(encoding="utf-8")

    def _find_artifact_on_disk_path(self) -> Path | None:
        if self.output_file is not None and self.output_file.exists():
            return self.output_file
        return self._find_artifact_path()
