from __future__ import annotations

from pulse.tui.palette import ACCENT_YELLOW, BG, BG_PANEL, BORDER, LIME, TEXT, TEXT_MUTED

HOME_CSS = f"""
HomeScreen {{
    background: {BG};
    align: center middle;
}}

HomeScreen #home-content {{
    width: auto;
    height: auto;
    max-width: 80%;
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
}}

HomeScreen .home-hint {{
    width: 100%;
    color: {TEXT_MUTED};
    margin-top: 1;
    text-align: center;
}}


HomeScreen #task-composer {{
    width: 96;
    max-width: 100%;
    height: auto;
}}

HomeScreen #composer-title {{
    color: {TEXT};
    text-style: bold;
    padding: 0 1;
}}

HomeScreen #composer-description {{
    color: {TEXT_MUTED};
    padding: 0 1;
}}

HomeScreen #composer-box {{
    height: auto;
    margin-top: 1;
    background: {BG};
    border: round {BORDER};
    padding: 0 1;
}}

HomeScreen #composer-box:focus-within {{
    border: round {LIME};
}}

HomeScreen .composer-glyph {{
    width: 2;
    color: {LIME};
    text-style: bold;
}}

HomeScreen TaskComposer {{
    width: 1fr;
    height: auto;
    min-height: 3;
    max-height: 12;
    padding: 0;
    background: {BG};
}}

HomeScreen TaskComposer .text-area--cursor-line {{
    background: {BG};
}}

HomeScreen TaskComposer .text-area--placeholder {{
    color: {TEXT_MUTED};
}}

HomeScreen .composer-hint {{
    color: {TEXT_MUTED};
    padding: 0 1;
}}
"""
