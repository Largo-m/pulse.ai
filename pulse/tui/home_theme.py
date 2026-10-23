from __future__ import annotations

from pulse.tui.palette import (
    ACCENT_YELLOW,
    BG,
    BG_PANEL,
    BORDER,
    ERROR,
    LIME,
    LIME_MUTED,
    TEXT,
    TEXT_MUTED,
)

HOME_CSS = f"""
HomeScreen {{
    background: {BG};
    align: center middle;
}}

HomeScreen #home-content {{
    width: auto;
    height: auto;
    max-width: 100%;
    padding: 0 2;
    align: center middle;
}}

HomeScreen .home-brand {{
    width: 100%;
    color: {LIME};
    text-style: bold;
    text-align: center;
    margin-bottom: 1;
}}

HomeScreen .home-sub {{
    width: 100%;
    color: {TEXT_MUTED};
    text-align: center;
    margin-bottom: 2;
}}

HomeScreen #home-alerts {{
    width: 60;
    max-width: 100%;
    height: auto;
    background: {BG_PANEL};
    border: solid {ACCENT_YELLOW};
    padding: 0 1;
    margin-bottom: 1;
}}

HomeScreen OptionList {{
    width: 60;
    max-width: 100%;
    height: auto;
    max-height: 16;
    background: {BG_PANEL};
    border: solid {BORDER};
    color: {TEXT};
    padding: 0 1;
}}

HomeScreen OptionList > .option-list--option {{
    padding: 0 1;
}}

HomeScreen OptionList:focus {{
    border: solid {LIME};
    background-tint: {BG} 0%;
}}

/* The `❯` pointer marks the row (MenuList); the bar would mark it twice. */
HomeScreen OptionList > .option-list--option-highlighted,
HomeScreen OptionList:focus > .option-list--option-highlighted,
HomeScreen OptionList > .option-list--option-hover {{
    background: {BG_PANEL};
    text-style: none;
}}

HomeScreen #home-header,
HomeScreen #home-keys,
HomeScreen #task-form {{
    display: none;
}}

/* New session: the agent-CLI picker layout, full width and top-left. */
HomeScreen.-picker {{
    align: left top;
}}

HomeScreen.-picker #home-content {{
    width: 100%;
    max-width: 120;
    height: 1fr;
    padding: 1 2 0 2;
    align: left top;
}}

HomeScreen.-picker .home-brand,
HomeScreen.-picker .home-sub,
HomeScreen.-picker Footer {{
    display: none;
}}

HomeScreen.-picker #home-header {{
    display: block;
    width: 100%;
    height: auto;
    margin-bottom: 1;
}}

HomeScreen.-picker #home-alerts {{
    width: 100%;
}}

HomeScreen.-picker OptionList {{
    width: 100%;
    max-height: 1fr;
    background: {BG};
    border: none;
    padding: 0;
    scrollbar-size-vertical: 1;
}}

HomeScreen.-picker OptionList:focus {{
    border: none;
}}

HomeScreen.-picker OptionList > .option-list--option {{
    padding: 0;
}}

HomeScreen.-picker OptionList > .option-list--option-highlighted,
HomeScreen.-picker OptionList:focus > .option-list--option-highlighted,
HomeScreen.-picker OptionList > .option-list--option-hover {{
    background: {BG};
}}

HomeScreen.-picker .home-hint {{
    text-align: left;
    margin-top: 1;
    padding: 0 0 0 2;
    border-left: tall {TEXT_MUTED};
}}

HomeScreen.-picker #home-keys {{
    display: block;
    dock: bottom;
    width: 100%;
    height: 1;
    padding: 0 2;
    background: {BG};
}}

/* The run form takes the picker's place and brings its own key chips. */
HomeScreen.-composing #task-form {{
    display: block;
}}

HomeScreen.-composing #home-header,
HomeScreen.-composing OptionList,
HomeScreen.-composing .home-hint,
HomeScreen.-composing #home-keys,
HomeScreen.-composing .home-brand,
HomeScreen.-composing .home-sub {{
    display: none;
}}

HomeScreen .home-hint {{
    width: 100%;
    color: {TEXT_MUTED};
    margin-top: 1;
    text-align: center;
}}


HomeScreen.-composing #task-form {{
    width: 100%;
    height: auto;
}}

TaskForm #task-heading {{
    color: {TEXT};
    text-style: bold;
    padding: 0 1;
}}

TaskForm #task-summary {{
    color: {TEXT_MUTED};
    padding: 0 1;
}}

TaskForm .task-label {{
    color: {TEXT_MUTED};
    padding: 0 1;
    margin-top: 1;
}}

TaskForm .task-box {{
    height: auto;
    background: {BG};
    border: round {BORDER};
    padding: 0 1;
}}

TaskForm .task-box:focus-within {{
    border: round {LIME};
}}

TaskForm .task-glyph {{
    width: 2;
    color: {LIME};
    text-style: bold;
}}

TaskForm Input, TaskForm Input:focus {{
    width: 1fr;
    background: {BG};
    background-tint: {BG} 0%;
    color: {TEXT};
}}

TaskForm TaskComposer {{
    width: 1fr;
    height: auto;
    min-height: 3;
    max-height: 10;
    padding: 0;
    background: {BG};
}}

TaskForm TaskComposer .text-area--cursor-line {{
    background: {BG};
}}

TaskForm TaskComposer .text-area--placeholder {{
    color: {TEXT_MUTED};
}}

TaskForm .task-row {{
    height: 1;
    padding: 0 2;
}}

TaskForm #task-slug-row {{
    margin-top: 0;
}}

TaskForm #task-git-row {{
    margin-top: 1;
}}

TaskForm .task-row-label {{
    width: 8;
    color: {TEXT_MUTED};
}}

TaskForm #task-slug {{
    color: {LIME};
}}

TaskForm Checkbox {{
    background: {BG};
    margin-right: 2;
}}

/* An off box shows no mark at all, so the state is not carried by color only. */
TaskForm Checkbox > .toggle--button {{
    color: {BG_PANEL};
    background: {BG_PANEL};
}}

TaskForm Checkbox.-on > .toggle--button {{
    color: {LIME};
}}

TaskForm Checkbox:focus > .toggle--label {{
    color: {LIME};
    background: {LIME_MUTED};
}}

TaskForm #task-error {{
    color: {ERROR};
    padding: 0 1;
    margin-top: 1;
}}

TaskForm .task-detail {{
    display: none;
}}

TaskForm.-detailed .task-detail {{
    display: block;
}}

TaskForm.-detailed .task-plain {{
    display: none;
}}

TaskForm.-no-repo .task-git {{
    display: none;
}}

TaskForm OptionsToggle {{
    width: auto;
    padding: 0 1;
    margin-top: 1;
}}

TaskForm OptionsToggle:hover {{
    background: {BG_PANEL};
}}

TaskForm OptionsToggle:focus {{
    background: {LIME_MUTED};
}}

TaskForm .task-hint {{
    color: {TEXT_MUTED};
    padding: 0 1;
    margin-top: 1;
}}
"""
