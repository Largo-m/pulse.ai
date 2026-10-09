from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.events import Click
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Markdown, Static

from pulse.tui import strings
from pulse.tui.artifacts import read_artifact_markdown
from pulse.tui.state import ArtifactItem, CockpitState

if TYPE_CHECKING:
    from typing import Unpack

    from pulse.tui.widgets.options import WidgetOptions


class ArtifactTabSelected(Message):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path


class ArtifactPaneClosed(Message):
    pass


class ArtifactPaneOpened(Message):
    pass


class ArtifactPane(Widget):
    can_focus = True

    def __init__(
        self, state: CockpitState, *, cwd: str | None = None, **kwargs: Unpack[WidgetOptions]
    ) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._cwd = cwd
        self._fingerprint: tuple[object, ...] | None = None
        self._loaded_key: tuple[str, float, bool] | None = None

    def set_cwd(self, cwd: str | None) -> None:
        """Repoint the directory where artifacts are looked up.

        The run may work in a worktree only known once `run.context` arrives.
        `_loaded_key` is reset too, since it caches the mtime of the file read
        from the old path.
        """
        if cwd == self._cwd:
            return
        self._cwd = cwd
        self._loaded_key = None
        self._fingerprint = None

    def compose(self) -> ComposeResult:
        yield Static(strings.ARTIFACT_OPEN_RAIL, id="artifact-open")
        with Horizontal(id="artifact-title-row"):
            yield Static("", id="artifact-header")
            yield Static("✕", id="artifact-close")
        yield Static("", id="artifact-meta")
        yield Horizontal(id="artifact-tabs")
        with VerticalScroll(id="artifact-body"):
            yield Markdown("", id="artifact-markdown")

    def on_mount(self) -> None:
        self.display = self._state.artifact_pane_open
        self.sync_from_state(self._state, force=True)
        self.set_interval(0.3, self._poll_file)

    def sync_from_state(self, state: CockpitState, *, force: bool = False) -> None:
        self._state = state
        expanded = state.artifact_pane_open
        collapsed = (not expanded) and state.phase_has_artifacts()
        self.display = expanded or collapsed
        self.set_class(collapsed, "-collapsed")
        self._apply_mode(expanded=expanded, collapsed=collapsed)
        if not expanded:
            self._fingerprint = None
            return
        fingerprint = self._tabs_fingerprint(state)
        if force or fingerprint != self._fingerprint:
            self._fingerprint = fingerprint
            self._refresh_chrome(state)
            self._refresh_tabs(state)
        self._load_selected(force=force)

    def _apply_mode(self, *, expanded: bool, collapsed: bool) -> None:
        try:
            self.query_one("#artifact-open", Static).display = collapsed
            self.query_one("#artifact-title-row", Horizontal).display = expanded
            self.query_one("#artifact-meta", Static).display = expanded
            self.query_one("#artifact-tabs", Horizontal).display = expanded
            self.query_one("#artifact-body", VerticalScroll).display = expanded
        except NoMatches:
            return

    def scroll_by(self, direction: int) -> None:
        try:
            body = self.query_one("#artifact-body", VerticalScroll)
        except NoMatches:
            return
        if direction < 0:
            body.scroll_up(animate=False)
        else:
            body.scroll_down(animate=False)

    def on_click(self, event: Click) -> None:
        if self.has_class("-collapsed"):
            event.stop()
            self.post_message(ArtifactPaneOpened())
            return
        try:
            close = self.query_one("#artifact-close", Static)
        except NoMatches:
            close = None
        if (
            close is not None
            and close.display
            and close.region.contains(event.screen_x, event.screen_y)
        ):
            event.stop()
            self.post_message(ArtifactPaneClosed())
            return
        try:
            row = self.query_one("#artifact-tabs", Horizontal)
        except NoMatches:
            return
        for child in row.children:
            if not isinstance(child, Static):
                continue
            if child.region.contains(event.screen_x, event.screen_y):
                path = child.name or ""
                if path:
                    event.stop()
                    self.post_message(ArtifactTabSelected(path))
                return

    def _poll_file(self) -> None:
        if not self._state.artifact_pane_open or not self.is_mounted:
            return
        self._load_selected(force=False)

    def _refresh_chrome(self, state: CockpitState) -> None:
        visible = state.visible_artifacts()
        header = self.query_one("#artifact-header", Static)
        meta = self.query_one("#artifact-meta", Static)
        header.update(
            Text(strings.ARTIFACT_HEADER.format(count=len(visible)), style="#A2D729 bold")
        )
        selected = state.selected_artifact()
        if selected is None:
            meta.update(Text(strings.ARTIFACT_NONE_IN_PHASE, style="#888888"))
            return
        name = Path(selected.path).name
        suffix = strings.ARTIFACT_LIVE if state.follow_artifact else strings.ARTIFACT_PAUSED
        if not selected.ready:
            suffix = strings.ARTIFACT_WRITING
        meta.update(Text(f"{name} · {suffix}", style="#888888"))

    def _refresh_tabs(self, state: CockpitState) -> None:
        row = self.query_one("#artifact-tabs", Horizontal)
        visible = state.visible_artifacts()
        selected = state.selected_artifact()
        selected_path = selected.path if selected is not None else ""
        children = [child for child in row.children if isinstance(child, Static)]
        by_name = {child.name: child for child in children if child.name}
        seen: set[str] = set()
        for item in visible:
            seen.add(item.path)
            active = item.path == selected_path
            child = by_name.get(item.path)
            if child is None:
                child = Static(
                    self._tab_label(item, active),
                    name=item.path,
                    classes="artifact-tab",
                )
                if active:
                    child.add_class("-active")
                row.mount(child)
                continue
            child.update(self._tab_label(item, active))
            child.set_class(active, "-active")
        for child in children:
            if child.name not in seen:
                child.remove()

    def _load_selected(self, *, force: bool) -> None:
        if not self._state.artifact_pane_open:
            return
        selected = self._state.selected_artifact()
        try:
            markdown = self.query_one("#artifact-markdown", Markdown)
        except NoMatches:
            return
        if selected is None:
            key = ("", 0.0, False)
            if force or self._loaded_key != key:
                self._loaded_key = key
                markdown.update(strings.ARTIFACT_NONE_IN_PHASE_MARKDOWN)
            return
        text, mtime, exists = read_artifact_markdown(selected.path, self._cwd)
        key = (selected.path, mtime, selected.ready)
        if not force and self._loaded_key == key:
            return
        self._loaded_key = key
        name = Path(selected.path).name
        if not exists:
            markdown.update(strings.ARTIFACT_WRITING_MARKDOWN.format(name=name))
            return
        if not text.strip():
            markdown.update(strings.ARTIFACT_EMPTY_MARKDOWN.format(name=name))
            return
        markdown.update(text)

    @staticmethod
    def _tab_label(item: ArtifactItem, active: bool) -> Text:
        name = Path(item.path).name
        prefix = "" if item.ready else "… "
        style = "#A2D729" if active else "#888888"
        return Text(f"{prefix}{name}  ", style=style)

    @staticmethod
    def _tabs_fingerprint(state: CockpitState) -> tuple[object, ...]:
        visible = state.visible_artifacts()
        selected = state.selected_artifact()
        return (
            tuple((item.path, item.ready) for item in visible),
            selected.path if selected is not None else "",
            state.follow_artifact,
            state.selected_phase_index,
            state.focus_target,
        )
