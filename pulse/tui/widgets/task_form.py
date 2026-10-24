from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Checkbox, Input, OptionList, Static

from pulse.domain.branch_name import task_slug
from pulse.domain.git_options import GitOption, GitOptions
from pulse.domain.task_brief import TaskBrief
from pulse.tui import strings
from pulse.tui.widgets.file_mention import FileMentionList
from pulse.tui.widgets.options_toggle import OptionsToggle, key_chips
from pulse.tui.widgets.task_composer import TaskComposer

if TYPE_CHECKING:
    from typing import Unpack

    from pulse.tui.widgets.options import WidgetOptions

PROMPT_GLYPH = "›"
_GIT_LABELS = (
    (GitOption.WORKTREE, strings.TASK_GIT_WORKTREE),
    (GitOption.COMMITS, strings.TASK_GIT_COMMITS),
    (GitOption.PULL_REQUEST, strings.TASK_GIT_PULL_REQUEST),
)


@dataclass(frozen=True)
class TaskDraft:
    """A task ready to run. A plain draft is only a description: the run takes the
    project's git options, as before the form had fields.
    """

    brief: TaskBrief
    slug: str = ""
    git: GitOptions | None = None
    detailed: bool = False


class TaskForm(Vertical):
    """The run form: a description, and on demand a title, its slug and git options.

    The detailed fields are opt-in (Ctrl+O) and the choice lasts while the app
    runs. Git options start from the project's and apply to this run only;
    outside a git repository there is no branch to name, so slug and options
    are hidden.
    """

    BINDINGS = [Binding("ctrl+o", "toggle_details", strings.TASK_MORE_OPTIONS, show=False)]

    class Submitted(Message):
        def __init__(self, form: TaskForm, draft: TaskDraft) -> None:
            super().__init__()
            self.form = form
            self.draft = draft

        @property
        def control(self) -> TaskForm:
            return self.form

    def __init__(self, **kwargs: Unpack[WidgetOptions]) -> None:
        super().__init__(**kwargs)
        self._git: GitOptions | None = None
        self._project_git: GitOptions | None = None
        self._tracked: tuple[str, ...] = ()
        self._untracked: tuple[str, ...] = ()
        self._slug_follows_title = True
        self._detailed = False

    def compose(self) -> ComposeResult:
        yield Static("", id="task-heading")
        yield Static("", id="task-summary")
        yield Static(strings.TASK_TITLE_LABEL, classes="task-label task-detail")
        with Horizontal(classes="task-box task-detail", id="task-title-box"):
            yield Static(PROMPT_GLYPH, classes="task-glyph")
            yield Input(placeholder=strings.TASK_TITLE_PLACEHOLDER, id="task-title", compact=True)
        with Horizontal(id="task-slug-row", classes="task-row task-detail task-git"):
            yield Static(strings.TASK_SLUG_LABEL, classes="task-row-label")
            yield Input(id="task-slug", compact=True)
        yield Static(strings.TASK_DESCRIPTION_LABEL, classes="task-label task-detail")
        with Horizontal(classes="task-box", id="task-description-box"):
            yield Static(PROMPT_GLYPH, classes="task-glyph task-plain")
            yield TaskComposer(id="task-description", compact=True)
        yield FileMentionList(id="task-mentions")
        with Horizontal(id="task-git-row", classes="task-row task-detail task-git"):
            yield Static(strings.TASK_CONFIG_LABEL, classes="task-row-label")
            for option, label in _GIT_LABELS:
                yield Checkbox(label, id=_checkbox_id(option), compact=True)
        yield Static("", id="task-error")
        yield OptionsToggle(id="task-options")
        yield Static("", classes="task-hint")

    def on_mount(self) -> None:
        mentions = self.query_one("#task-mentions", FileMentionList)
        self.query_one("#task-description", TaskComposer).bind_mentions(mentions)

    @on(OptionList.OptionSelected, "#task-mentions")
    def _mention_clicked(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        if event.option.id is not None:
            self.query_one("#task-description", TaskComposer).insert_mention(event.option.id)

    def offer_files(self, tracked: Sequence[str], untracked: Sequence[str] = ()) -> None:
        """The workspace files `@` lists; they arrive after the form opens."""
        self._tracked = tuple(tracked)
        self._untracked = tuple(untracked)
        self.query_one("#task-description", TaskComposer).offer_files(self._mentionable())

    def _mentionable(self) -> list[str]:
        git = self._git if self._detailed else self._project_git
        if git is not None and git.use_worktree:
            return list(self._tracked)
        return sorted({*self._tracked, *self._untracked})

    def _refresh_mentionable(self) -> None:
        self.query_one("#task-mentions", FileMentionList).set_files(self._mentionable())

    def open(self, *, heading: str | Text, summary: str, git: GitOptions | None) -> None:
        """Start a blank draft; `git` is None outside a repository."""
        self.query_one("#task-heading", Static).update(heading)
        self.query_one("#task-summary", Static).update(summary)
        self._slug_follows_title = True
        self._git = git
        self._project_git = git
        for selector in ("#task-title", "#task-slug"):
            with self.query_one(selector, Input).prevent(Input.Changed):
                self.query_one(selector, Input).value = ""
        self.query_one("#task-description", TaskComposer).clear()
        self.offer_files(())
        self.set_class(git is None, "-no-repo")
        self._show_git()
        self.show_error("")
        self._show_mode()

    def action_toggle_details(self) -> None:
        """Swap between a plain description and the full form; typed text stays."""
        self._detailed = not self._detailed
        self.show_error("")
        self._show_mode()

    @on(OptionsToggle.Pressed)
    def _options_pressed(self, event: OptionsToggle.Pressed) -> None:
        event.stop()
        self.action_toggle_details()

    def _show_mode(self) -> None:
        detailed = self._detailed
        self.set_class(detailed, "-detailed")
        self._refresh_mentionable()
        self.query_one("#task-description", TaskComposer).placeholder = (
            strings.TASK_DESCRIPTION_PLACEHOLDER if detailed else strings.TASK_PLAIN_PLACEHOLDER
        )
        self.query_one("#task-options", OptionsToggle).show_state(expanded=detailed)
        self.query_one(".task-hint", Static).update(
            key_chips(strings.TASK_KEYS_DETAILED if detailed else strings.TASK_KEYS_PLAIN)
        )
        focus = self.query_one("#task-title", Input) if detailed else None
        (focus or self.query_one("#task-description", TaskComposer)).focus()

    def show_error(self, text: str) -> None:
        error = self.query_one("#task-error", Static)
        error.update(text)
        error.display = bool(text)

    @on(Input.Changed, "#task-title")
    def _title_changed(self, event: Input.Changed) -> None:
        if not self._slug_follows_title:
            return
        slug = self.query_one("#task-slug", Input)
        with slug.prevent(Input.Changed):
            slug.value = task_slug(event.value)

    @on(Input.Changed, "#task-slug")
    def _slug_changed(self, event: Input.Changed) -> None:
        """A slug the user typed stops following the title; clearing it resumes."""
        title = self.query_one("#task-title", Input).value
        self._slug_follows_title = event.value in {"", task_slug(title)}

    @on(Input.Submitted)
    def _next_field(self, event: Input.Submitted) -> None:
        event.stop()
        self.screen.focus_next()

    @on(Checkbox.Changed)
    def _git_changed(self, event: Checkbox.Changed) -> None:
        event.stop()
        if self._git is None or event.checkbox.id is None:
            return
        self._git = self._git.toggled(_option_of(event.checkbox.id))
        self._show_git()
        self._refresh_mentionable()

    @on(TaskComposer.Submitted, "#task-description")
    def _submit(self, event: TaskComposer.Submitted) -> None:
        event.stop()
        if not self._detailed:
            self._submit_plain(event.text)
            return
        brief = TaskBrief(title=self.query_one("#task-title", Input).value, description=event.text)
        if not brief.title:
            self.show_error(strings.TASK_TITLE_REQUIRED)
            self.query_one("#task-title", Input).focus()
            return
        slug = self.query_one("#task-slug", Input).value.strip()
        draft = TaskDraft(brief=brief, slug=slug, git=self._git, detailed=True)
        self.post_message(self.Submitted(self, draft))

    def _submit_plain(self, text: str) -> None:
        """A blank description keeps the box open: there is nothing to run."""
        brief = TaskBrief(description=text)
        if brief.is_empty:
            return
        self.post_message(self.Submitted(self, TaskDraft(brief=brief)))

    def _show_git(self) -> None:
        """Mirror the options on the boxes, which a toggle may have carried along."""
        if self._git is None:
            return
        for option, _label in _GIT_LABELS:
            box = self.query_one(f"#{_checkbox_id(option)}", Checkbox)
            with box.prevent(Checkbox.Changed):
                box.value = self._git.enabled(option)


def _checkbox_id(option: GitOption) -> str:
    return f"git-{option.value.replace('_', '-')}"


def _option_of(checkbox_id: str) -> GitOption:
    return next(option for option, _ in _GIT_LABELS if _checkbox_id(option) == checkbox_id)
