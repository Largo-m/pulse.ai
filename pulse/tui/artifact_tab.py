"""The cockpit's artifact tab: which files the run wrote and which one is on screen.

Lives outside [pulse.tui.state] so the cockpit state stays one reason to change
per module; `CockpitState` mixes it in and keeps the fields.
"""

from __future__ import annotations

from typing import Protocol

from pulse.history.events import ArtifactItem, PhaseItem
from pulse.tui.artifacts import artifact_key, artifact_paths_in_text, is_displayable_artifact


class _ArtifactHost(Protocol):
    """The cockpit state fields and lookups the artifact tab reads and writes."""

    artifacts: list[ArtifactItem]
    selected_artifact_path: str
    follow_artifact: bool
    artifact_pane_open: bool
    focus_target: str

    def notify(self) -> None: ...

    def selected_phase(self) -> PhaseItem | None: ...

    def _entry_phase_id(self) -> str: ...

    def visible_artifacts(self) -> list[ArtifactItem]: ...

    def displayable_artifacts(self) -> list[ArtifactItem]: ...

    def selected_artifact(self) -> ArtifactItem | None: ...


class ArtifactTab:
    """`CockpitState` mixin: the artifact list, its selection and the pane."""

    def upsert_artifact(
        self: _ArtifactHost,
        path: str,
        *,
        ready: bool,
        has_content: bool = False,
        cwd: str | None = None,
    ) -> ArtifactItem | None:
        if not is_displayable_artifact(path, cwd):
            return None
        key = artifact_key(path)
        phase_id = self._entry_phase_id()
        item = next(
            (known for known in self.artifacts if (known.path, known.phase_id) == (key, phase_id)),
            None,
        )
        if item is None:
            item = ArtifactItem(path=key, phase_id=phase_id, ready=ready, has_content=has_content)
        else:
            self.artifacts.remove(item)
            item.ready = ready
            item.has_content = item.has_content or has_content
        self.artifacts.append(item)
        if self.follow_artifact or not self.selected_artifact_path:
            self.selected_artifact_path = item.path
        self.notify()
        return item

    def visible_artifacts(self: _ArtifactHost) -> list[ArtifactItem]:
        phase = self.selected_phase()
        if phase is None:
            return list(self.artifacts)
        pid = phase.id
        return [item for item in self.artifacts if item.phase_id == pid]

    def displayable_artifacts(self: _ArtifactHost) -> list[ArtifactItem]:
        """Artifacts of the selected phase that actually have content to show."""
        return [item for item in self.visible_artifacts() if item.has_content]

    def phase_has_artifacts(self: _ArtifactHost) -> bool:
        return bool(self.displayable_artifacts())

    def selected_artifact(self: _ArtifactHost) -> ArtifactItem | None:
        visible = self.visible_artifacts()
        if not visible:
            return None
        for item in visible:
            if item.path == self.selected_artifact_path:
                return item
        return visible[-1]

    def select_artifact(self: _ArtifactHost, path: str) -> None:
        key = artifact_key(path)
        for item in self.artifacts:
            if item.path != key:
                continue
            self.selected_artifact_path = item.path
            self.follow_artifact = False
            self.notify()
            return

    def move_artifact(self: _ArtifactHost, delta: int) -> None:
        visible = self.visible_artifacts()
        if not visible:
            return
        paths = [item.path for item in visible]
        selected = self.selected_artifact()
        current = selected.path if selected is not None else paths[0]
        try:
            index = paths.index(current)
        except ValueError:
            index = 0
        index = max(0, min(index + delta, len(paths) - 1))
        self.selected_artifact_path = paths[index]
        self.follow_artifact = False
        self.notify()

    def toggle_artifact_pane(self: _ArtifactHost) -> None:
        self.artifact_pane_open = not self.artifact_pane_open
        if not self.artifact_pane_open and self.focus_target == "artifact":
            self.focus_target = "stream"
        self.notify()

    def close_artifact_pane(self: _ArtifactHost) -> None:
        if not self.artifact_pane_open:
            return
        self.artifact_pane_open = False
        if self.focus_target == "artifact":
            self.focus_target = "stream"
        self.notify()

    def open_artifact_pane(self: _ArtifactHost) -> None:
        if self.artifact_pane_open:
            return
        self.artifact_pane_open = True
        self.notify()

    def select_artifact_from_prompt(self: _ArtifactHost, text: str) -> bool:
        """Point the artifact tab at the artifact the question cites.

        Selection only; opening is left to the user (`a` key) so the stream stays
        visible while the agent asks for a decision. A question citing no artifact
        changes nothing, so `follow_artifact` stays on.
        """
        keys = artifact_paths_in_text(text, [item.path for item in self.artifacts])
        candidates = [item for item in self.artifacts if item.has_content]
        matched: ArtifactItem | None = None
        for key in keys:
            for item in candidates:
                if item.path == key or item.path.endswith(key) or key.endswith(item.path):
                    matched = item
                    break
            if matched is not None:
                break
        if matched is None:
            return False
        self.selected_artifact_path = matched.path
        self.follow_artifact = False
        self.notify()
        return True
