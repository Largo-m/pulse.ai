from __future__ import annotations

from pulse.tui.palette import BG, TEXT, TEXT_MUTED

SETTINGS_CSS = f"""
SettingsScreen {{
    background: {BG};
    layout: vertical;
}}

SettingsScreen #settings-content {{
    width: 100%;
    max-width: 120;
    height: 1fr;
    padding: 1 2 0 2;
}}

SettingsScreen #settings-header {{
    width: 100%;
    height: 1;
}}

SettingsScreen #settings-status {{
    width: 100%;
    height: auto;
    color: {TEXT_MUTED};
    margin-bottom: 1;
}}

SettingsScreen OptionList {{
    width: 100%;
    height: auto;
    max-height: 1fr;
    background: {BG};
    border: none;
    padding: 0;
    color: {TEXT};
    scrollbar-size-vertical: 1;
}}

SettingsScreen OptionList:focus {{
    border: none;
    background-tint: {BG} 0%;
}}

SettingsScreen OptionList > .option-list--option-highlighted,
SettingsScreen OptionList:focus > .option-list--option-highlighted {{
    background: {BG};
    text-style: none;
}}

SettingsScreen OptionList > .option-list--option-hover {{
    background: {BG};
}}

SettingsScreen #settings-report {{
    width: 100%;
    height: auto;
    max-height: 14;
    padding: 0 0 0 2;
    margin-top: 1;
    border-left: tall {TEXT_MUTED};
}}

SettingsScreen #settings-keys {{
    dock: bottom;
    width: 100%;
    height: 1;
    padding: 0 2;
    background: {BG};
}}
"""
