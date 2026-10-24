from __future__ import annotations

from pulse.tui.palette import BG, BORDER, LIME, TEXT, TEXT_MUTED

HISTORY_CSS = f"""
HistoryListScreen {{
    background: {BG};
    layout: vertical;
}}

HistoryListScreen #history-content {{
    width: 100%;
    max-width: 120;
    height: 1fr;
    padding: 1 2 0 2;
}}

HistoryListScreen #history-header {{
    width: 100%;
    height: 1;
    margin-bottom: 1;
}}

HistoryListScreen #history-search {{
    width: 100%;
    height: 3;
    background: {BG};
    border: round {BORDER};
    padding: 0 1;
    margin-bottom: 1;
}}

HistoryListScreen #history-search:focus {{
    border: round {LIME};
    background-tint: {BG} 0%;
}}

HistoryListScreen #history-search > .input--placeholder {{
    color: {TEXT_MUTED};
}}

HistoryListScreen OptionList {{
    width: 100%;
    height: 1fr;
    background: {BG};
    border: none;
    padding: 0;
    color: {TEXT};
    scrollbar-size-vertical: 1;
}}

HistoryListScreen OptionList:focus {{
    border: none;
    background-tint: {BG} 0%;
}}

HistoryListScreen OptionList > .option-list--option-highlighted,
HistoryListScreen OptionList:focus > .option-list--option-highlighted {{
    background: {BG};
    text-style: none;
}}

HistoryListScreen OptionList > .option-list--option-hover {{
    background: {BG};
}}

HistoryListScreen #history-empty {{
    width: 100%;
    height: auto;
    padding: 1 2;
    color: {TEXT_MUTED};
}}

HistoryListScreen #history-keys {{
    dock: bottom;
    width: 100%;
    height: 1;
    padding: 0 2;
    background: {BG};
}}
"""
